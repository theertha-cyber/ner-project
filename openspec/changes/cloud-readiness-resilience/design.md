## Context

All five backend services (`chat_api`, `extraction_service`, `gateway`, `document_service`, `training_service`) are FastAPI apps sharing one `pyproject.toml`/`poetry.lock` and a common `src/shared/config.py` (Pydantic `BaseSettings`, `env_prefix="NER_"`). Today, startup ordering correctness is enforced entirely by Docker Compose (`depends_on: condition: service_healthy`) rather than by the application itself:

- `src/shared/database.py` builds a `create_async_engine` lazily but with no retry — first query against a not-yet-ready Postgres raises uncaught.
- `src/document_service/services/storage.py` constructs a `boto3` S3/MinIO client eagerly in `__init__` and calls `head_bucket`/`create_bucket` synchronously — a slow MinIO start crashes `document_service` at import time.
- Every service's `/health` (e.g. `chat_api/main.py:73-75`) unconditionally returns `{"status": "ok"}`, so it cannot distinguish "up but dependencies unreachable" from "actually ready."
- `docker-compose.yml` has healthchecks only for `postgres-test` and `redis`; `minio` has none, and `model_serving`/`mlflow` have no `depends_on` at all.
- No retry library is a direct dependency; `tenacity` exists only transitively via `poetry.lock`.

Constraint from the requesting task: this must work identically under Docker Compose today and be equally correct under any future orchestrator that starts/restarts containers independently — no Azure-specific behavior.

## Goals / Non-Goals

**Goals:**
- Every service tolerates its dependencies (Postgres, Redis where used, MinIO for `document_service`) becoming available after the service process starts, via bounded exponential-backoff retry.
- `/health` on every service reflects actual dependency reachability (`200` only when ready, `503` otherwise), with a per-dependency breakdown in the JSON body.
- A separate liveness signal (`/health/live`) exists so "process is alive" and "process is ready for traffic" are distinguishable.
- All retry/timeout/backoff parameters and previously-implicit host/SSL assumptions are environment-configurable with defaults that reproduce current Docker Compose behavior unchanged.

**Non-Goals:**
- No Azure Container Apps probe config, Bicep/Terraform, Key Vault integration, or managed-service-specific connection logic.
- No change to which services depend on which infra (no new Redis usage where none exists today; `training_service`/`gateway` etc. keep their current dependency set).
- No circuit breakers, service mesh, or retry logic for calls *between* internal services (gateway → extraction_service, etc.) — scope is limited to infra dependency startup (DB/Redis/MinIO) and health reporting, per the proposal's Open Question resolution that readiness checks only cover a service's own direct dependencies.
- No change to Docker Compose service topology, ports, or network names — only healthcheck/depends_on additions that are inert if unused elsewhere.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Tenants isolated via per-tenant Postgres schemas, single DB engine | Retry/readiness logic must wrap the shared engine/session layer in `src/shared/database.py`, not per-tenant connections — one retry policy covers all schemas. |
| ADR-003: Per-Tenant Model Serving Topology | Each tenant may have its own model-serving endpoint | `chat_api`/`extraction_service` readiness checks for "model availability" must be scoped correctly — non-goal to check per-tenant model health in a shared `/health`; global readiness checks only the service's own baseline dependencies (DB/Redis/MinIO), not per-tenant model reachability. |
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Training runs via async Celery-style GPU workers | `training_service` readiness should check its task-queue broker dependency (Redis) consistent with how it already depends on it, not add new synchronous coupling to GPU worker state. |
| ADR-008: Base Model as Default Inference Model | Base model always available as fallback (supersedes ADR-002's 404 behavior) | `chat_api`/`extraction_service` "model availability" check in readiness should treat base-model availability as the minimum bar, consistent with the always-available-default guarantee — must not report not-ready solely because a tenant-specific model isn't loaded. |

## Decisions

### Decision 1: Use `tenacity` for retry/backoff, applied at the client-construction boundary

**Choice:** Add `tenacity` as a direct `pyproject.toml` dependency and wrap Postgres engine first-connection, MinIO client bucket-init, and any Redis connection checks with `tenacity.retry(wait=wait_exponential(...), stop=stop_after_delay(...))`.

**Rationale:** `tenacity` is already present transitively (pulled in by another dependency), so it adds no new supply-chain surface. It's the standard Python retry library, supports async, and keeps retry policy declarative and testable in isolation from business logic.

**Alternatives considered:**
- Hand-rolled retry loops — ruled out: reimplements what `tenacity` already does correctly (jitter, max delay, stop conditions) and is easy to get subtly wrong (e.g. thundering herd without jitter).
- `backoff` library — ruled out: also viable, but not already present even transitively, adding a genuinely new dependency versus promoting an existing transitive one.

### Decision 2: Split `/health` into readiness (`/health`) and liveness (`/health/live`)

**Choice:** `/health` becomes a true readiness check (probes DB, and MinIO/Redis/model where applicable, per service; `200` if all pass, `503` with a per-dependency JSON breakdown if any fail). `/health/live` is new — always `200` if the process can respond at all, no dependency probing.

**Rationale:** The proposal's explicit requirement is that "the endpoint should accurately indicate whether the service is ready to receive traffic" — that's a readiness semantic, and `/health` is the path already being polled, so preserving that path avoids a breaking route change for anything monitoring it today. Liveness needs a distinct signal so a transient DB blip doesn't cause an orchestrator to kill and restart an otherwise-healthy process (which would only compound a dependency outage with restart storms).

**Alternatives considered:**
- Keep `/health` as liveness-only, add `/ready` for readiness — ruled out: existing external monitoring/compose healthchecks already target `/health`; repurposing it to mean readiness (superset of current always-`200` behavior, now conditionally `503`) better matches "accurately indicate whether ready to receive traffic" without requiring every caller to learn a new path.
- Single endpoint doing both — ruled out: conflates two different orchestration signals (restart vs. don't-route), which is the exact ambiguity the proposal asks to resolve.

### Decision 3: Externalize DB SSL mode as a dedicated setting instead of only via the URL string

**Choice:** Add `database_ssl_mode: str = "disable"` (or equivalent) to `src/shared/config.py`, defaulting to today's Compose-local behavior, and have `database_url` construction consume it rather than hardcoding `sslmode=disable` in the default URL.

**Rationale:** The current default bakes `sslmode=disable` directly into the URL default in `src/shared/config.py`; any deployment needing SSL (any managed Postgres, not just Azure) has to override the entire URL rather than toggling one flag. A dedicated setting is a strict generalization — Compose keeps working via the same default value.

**Alternatives considered:**
- Leave SSL mode embedded only in `DATABASE_URL` — ruled out: forces every non-Compose environment to reconstruct the whole URL instead of setting one env var, which is exactly the "hardcoded deployment assumption" the task calls out.

### Decision 4: Retry defaults are conservative and bounded, tuned for "seconds to low tens of seconds" dependency startup delay

**Choice:** Default retry policy: exponential backoff starting at 0.5s, multiplier 2, capped at 10s between attempts, giving up after 30s total (configurable via `NER_DB_RETRY_MAX_SECONDS` etc.). This applies at process-startup connection time, not per-request.

**Rationale:** Matches typical container dependency startup variance (Postgres/MinIO/Redis usually ready within single-digit seconds; 30s covers slow cold starts without masking a genuinely down dependency for minutes). Bounded stop condition avoids infinite retry masking a misconfiguration (wrong host/credentials) as a "still starting" state forever — after the bound is exhausted, the service should fail startup loudly (current behavior), or, for `/health` probes issued after startup, simply report `503` and keep retrying in the background on next poll rather than crashing the process.

**Alternatives considered:**
- Unbounded retry — ruled out: turns a real misconfiguration into a silent hang with no operator signal.
- Fixed-interval retry (no backoff) — ruled out: doesn't reduce load on a struggling dependency during an actual outage; explicitly asked for in the task ("bounded exponential backoff").

## Risks / Trade-offs

- [Repurposing `/health` from always-`200` to conditional `503` could trip existing Compose `depends_on: condition: service_healthy` for any service that currently depends on another service's `/health`] → Audit `docker-compose.yml` `depends_on` graph during implementation; today only `postgres-test` and `redis` have healthchecks (not the FastAPI services), so no existing Compose healthcheck currently targets a FastAPI `/health` — risk is contained to *external* monitoring, which is expected to want this improved accuracy.
- [Retry at startup extends worst-case container startup time by up to the configured max (default 30s) if a dependency is genuinely slow] → Bounded and configurable; Compose already tolerates slow-start via `service_healthy` waits, so this is not a regression, just makes the same tolerance work without Compose's help.
- [Adding readiness checks that hit the DB/MinIO/Redis on every `/health` poll adds load if polled very frequently] → Document a reasonable poll interval (e.g. ≥5s) in the spec; checks are lightweight (`SELECT 1`, `head_bucket`, `PING`), not full queries.
- [MinIO bucket-init retry changes `document_service` startup from "crash immediately" to "retry then crash" — could mask a real misconfiguration for longer during debugging] → Bounded retry (Decision 4) keeps this to tens of seconds, and the final failure still logs the underlying error, not just "not ready."

## Migration Plan

1. Add `tenacity` to `pyproject.toml` direct dependencies (already resolvable from lockfile, no version conflict expected).
2. Add `database_ssl_mode` and retry-tuning settings to `src/shared/config.py` with defaults matching current behavior — no `.env` changes required for existing Compose setups.
3. Wrap `src/shared/database.py` engine first-use and `src/document_service/services/storage.py` MinIO init with retry decorators.
4. Implement per-service readiness logic in each `main.py`, reusing a shared readiness-check helper (new, e.g. `src/shared/readiness.py`) to avoid duplicating the DB/MinIO/Redis probe code five times.
5. Add `/health/live` route alongside updated `/health` in each service.
6. Add `minio` healthcheck and missing `depends_on` entries to `docker-compose.yml`.
7. Run full `docker-compose up` locally and verify: (a) normal startup still succeeds with all services reporting ready, (b) manually delaying a dependency (e.g. `docker compose up` without `minio` initially, then starting it) demonstrates a service recovering to ready without manual restart.
8. Rollback: every change is additive/config-defaulted; reverting is a straight `git revert` with no data migration involved (no schema or persisted-data changes).

## Open Questions

- Confirm acceptable default retry bound (30s total) is right for all services, or whether `training_service` (GPU worker coordination) needs a longer bound given ADR-006's async worker model — flagging for review rather than deciding unilaterally.
- Should the shared readiness-check helper live in `src/shared/` (new `readiness.py`) or be duplicated per-service for independence? Design assumes shared helper for consistency; revisit if services' dependency sets diverge enough to make a shared abstraction awkward.
- No in-force ADR requires revisiting — this design is additive to ADR-001/003/006/008's existing commitments, not in conflict with them.
