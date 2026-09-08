## Why

Every backend service (`chat_api`, `extraction_service`, `gateway`, `document_service`, `training_service`) connects to PostgreSQL, Redis, and/or MinIO eagerly at startup with no retry logic, and exposes a `/health` endpoint that always returns `{"status": "ok"}` regardless of dependency state (`src/*/main.py`, e.g. `chat_api/main.py:73-75`). This works in Docker Compose today only because `depends_on: condition: service_healthy` enforces strict startup ordering. Any environment without that guarantee — including container orchestrators that start services independently and restart them out of order — will see services crash-loop on a slow-starting dependency, and load balancers will route traffic to services that report healthy but cannot actually serve requests. This change makes the application resilient to its own dependency timing, independent of what orchestrates it.

## What Changes

- Add bounded exponential-backoff retry to all PostgreSQL, Redis, and MinIO client initialization (`src/shared/database.py`, `src/document_service/services/storage.py`, and any Redis client added for Celery broker/result backend checks), using a proper retry library (`tenacity`, promoted from transitive to direct dependency).
- Replace the trivial `{"status": "ok"}` handler in all 5 services with real readiness checks that probe each service's actual dependencies (Postgres for all; MinIO for `document_service`; Redis/Celery broker for services with async task queues; model availability for `chat_api`/`extraction_service` where applicable). Return `503` when not ready, `200` when ready, with a per-dependency breakdown in the body.
- Add a lightweight `/health/live` liveness endpoint (process is up, no dependency checks) alongside the existing `/health` readiness semantics, so orchestrators can distinguish "restart me" from "don't route to me yet."
- Externalize remaining defaults in `src/shared/config.py` that currently bake in local assumptions: add a dedicated `database_ssl_mode` setting (instead of only embedding `sslmode=disable` in the URL default), keep `cors_origins`/`cors_origin_regex` as env-overridable (already the case — verify no code path bypasses `settings` and hardcodes a value), and confirm all inter-service URLs are settings-driven, not hardcoded.
- Add MinIO bucket-init retry/backoff in `document_service/services/storage.py` so a slow-starting MinIO doesn't crash the service at import/init time.
- Add a `docker-compose.yml` healthcheck for `minio` and wire `depends_on: condition: service_healthy` for `model_serving` and `mlflow`, which currently start without waiting on their dependencies — this is Compose-local hygiene, not new app behavior, but surfaces the same gaps the app-level retries now cover.

No Azure-specific values, hostnames, secrets, or infrastructure are introduced. No breaking changes to existing environment variable names or Docker Compose service topology.

## Capabilities

### New Capabilities

- `service-readiness`: Startup dependency retry/backoff and `/health` + `/health/live` readiness/liveness endpoints, applied uniformly across `chat_api`, `extraction_service`, `gateway`, `document_service`, `training_service`.

### Modified Capabilities

(none — `openspec/specs/` currently has no promoted capability specs; this change introduces the first one covering this behavior)

## Impact

- **Code**: `src/shared/database.py`, `src/shared/config.py`, `src/document_service/services/storage.py`, `src/{chat_api,extraction_service,gateway,document_service,training_service}/main.py`, `pyproject.toml` (add `tenacity` as direct dependency).
- **Infra (local only)**: `docker-compose.yml` healthcheck additions for `minio`, `depends_on` fixes for `model_serving`/`mlflow`. No change to service names, ports, or network topology.
- **Downstream**: Any external caller polling `/health` will now see `503` during dependency outages instead of a false `200` — this is an intentional, additive behavior change to response semantics, not a route/contract removal.
- **Dependencies**: Adds `tenacity` (already present transitively via `poetry.lock`, promoted to direct).

## Open Questions

- Should `/health` (readiness) and `/health/live` (liveness) be the final naming, or should the existing `/health` route keep today's liveness-only meaning and readiness move to a new `/ready` path? Naming affects any existing external monitoring already polling `/health`. Proposal assumes `/health` becomes readiness (matches "should indicate whether the service is ready to receive traffic" in the request) and adds `/health/live` as new.
- What per-service dependency set counts as "critical" for readiness (e.g., should `gateway`'s readiness depend on downstream service reachability, or only its own direct dependencies)? Assumption: each service checks only its own direct infrastructure dependencies (DB/Redis/MinIO/model), not transitive health of other internal services, to avoid cascading false negatives.
- Retry bounds (max attempts, max backoff ceiling) need concrete defaults — proposed in design.md, open to adjustment.
