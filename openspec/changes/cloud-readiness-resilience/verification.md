# Verification Plan

**Change:** cloud-readiness-resilience
**Generated:** 2026-08-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | service-readiness | Dependency Connection Retry with Bounded Exponential Backoff | Postgres not yet ready at service startup | Given a service starting before Postgres accepts connections, when it attempts its first DB connection, then it retries with exponential backoff (start ≥0.5s, multiplier ≥2, cap ≤10s) instead of raising unhandled on first failure | `tests/test_database_retry.py::test_retries_with_exponential_backoff_before_succeeding` | - [x] |
| 2 | service-readiness | Dependency Connection Retry with Bounded Exponential Backoff | MinIO not yet ready at document_service startup | Given document_service starting before MinIO accepts connections, when it initializes its storage client, then it retries bucket verification/creation with bounded exponential backoff instead of crashing on first ClientError | `tests/test_document_service_storage_retry.py::test_ensure_bucket_retries_then_succeeds_on_transient_endpoint_error` | - [x] |
| 3 | service-readiness | Dependency Connection Retry with Bounded Exponential Backoff | Dependency never becomes available within the retry bound | Given a dependency stays unreachable past the configured max retry duration, when the bound is exhausted, then the service exits/logs a fatal error identifying the failed dependency instead of retrying forever | `tests/test_database_retry.py::test_fatal_error_raised_after_retry_bound_exhausted`, `tests/test_document_service_storage_retry.py::test_ensure_bucket_raises_after_retry_bound_exhausted` | - [x] |
| 4 | service-readiness | Dependency Connection Retry with Bounded Exponential Backoff | Dependency recovers after service process is already running | Given a running service whose dependency was unreachable, when the dependency becomes available, then the next check/query succeeds without a manual restart | Live verification: `docker compose stop minio` / `docker compose start minio` against running `document_service` — `/health` went 200→503→200 with no restart | - [x] |
| 5 | service-readiness | Retry Parameters Are Externally Configurable | No environment override present | Given no retry env vars set, when a service starts under existing Docker Compose with dependencies already up, then defaults apply and startup timing is unchanged from pre-change behavior | `tests/test_shared_config_ssl_and_retry.py::test_retry_defaults_present` | - [x] |
| 6 | service-readiness | Retry Parameters Are Externally Configurable | Environment override present | Given an operator sets a retry-tuning env var to a non-default value, when the service starts, then it uses the overridden value | `tests/test_shared_config_ssl_and_retry.py::test_retry_env_override_takes_effect` | - [x] |
| 7 | service-readiness | Readiness Endpoint Reflects Actual Dependency State | All dependencies reachable | Given all of a service's critical dependencies are reachable, when a client requests /health, then response is HTTP 200 with a JSON breakdown showing each dependency healthy | `tests/test_health_endpoints.py` (200 cases, all 5 services) + live curl against running stack (all 5 ports returned 200) | - [x] |
| 8 | service-readiness | Readiness Endpoint Reflects Actual Dependency State | A critical dependency is unreachable | Given a service's PostgreSQL connection is failing, when a client requests /health, then response is HTTP 503 with JSON identifying PostgreSQL unhealthy while other checked dependencies are still reported | `tests/test_health_endpoints.py` (503 cases, all 5 services) + live `docker compose stop minio` against `document_service` | - [x] |
| 9 | service-readiness | Readiness Endpoint Reflects Actual Dependency State | chat_api and extraction_service check base model availability | Given chat_api or extraction_service is running, when a client requests /health, then it confirms default base model availability and does not report not-ready solely due to missing tenant-specific model | `tests/test_health_endpoints.py::test_chat_api_health_stays_healthy_when_only_base_model_reachable` | - [x] |
| 10 | service-readiness | Liveness Endpoint Independent of Dependency State | Dependencies are down but the process is running | Given a service's PostgreSQL dependency is unreachable, when a client requests /health/live, then response is HTTP 200, distinct from the concurrent /health readiness response | `tests/test_health_endpoints.py::test_extraction_service_health_live_independent_of_dependencies` | - [x] |
| 11 | service-readiness | Externally Configurable Deployment Assumptions | Default configuration under Docker Compose | Given no relevant env vars overridden, when a service starts under existing docker-compose.yml, then CORS origins, CORS regex, DB SSL mode, and inter-service URLs resolve to the same effective values as before this change | `tests/test_shared_config_ssl_and_retry.py::test_default_ssl_mode_matches_pre_change_behavior`, `test_default_cors_and_service_urls_unchanged_without_overrides` | - [x] |
| 12 | service-readiness | Externally Configurable Deployment Assumptions | SSL mode overridden via environment variable | Given an operator sets the PostgreSQL SSL mode env var to a non-default value, when the service constructs its DB connection, then the connection uses the overridden SSL mode without reconstructing the full DATABASE_URL | `tests/test_shared_config_ssl_and_retry.py::test_database_ssl_mode_override_updates_default_urls_without_full_url_override`, `test_explicit_database_url_override_is_not_rewritten_by_ssl_mode` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Repurposing `/health` semantics | AI may leave `/health` always returning 200 (old behavior) while adding a separate readiness path, silently failing to meet the spec requirement that `/health` itself reflects dependency state | Curl `/health` on each of the 5 services with a dependency intentionally stopped (e.g. `docker compose stop minio`) and confirm HTTP 503 with a per-dependency body, not just a new unused endpoint |
| 2 | Shared readiness-check helper (design Decision 2 / Migration step 4) | AI may hardcode which dependencies each service checks incorrectly (e.g. checking Redis for a service that doesn't use it, or omitting MinIO for document_service), inventing a dependency set not grounded in each service's actual client usage | For each service, diff the dependencies probed in its `/health` handler against the dependencies actually instantiated in that service's code (grep for `create_async_engine`, `boto3.client`, Redis/Celery client construction) |
| 3 | Retry bound tuning (design Decision 4) | AI may implement unbounded retry or an unbounded/very large `stop_after_delay`, defeating the "fail loudly after bound exhausted" requirement, or may retry per-request instead of only at startup/connection-establishment | Read the `tenacity` decorator config in each modified file and confirm a finite `stop_after_delay`/`stop_after_attempt` is present; trigger a permanently-unreachable dependency in a test and confirm the process exits/logs fatal rather than hanging indefinitely |
| 4 | Base model availability check (ADR-008 interaction) | AI may implement the model-availability check against a per-tenant model lookup that 404s when no tenant model is configured, contradicting ADR-008's "base model always available as default" guarantee and causing false not-ready reports | Test `/health` for `chat_api`/`extraction_service` with a tenant that has no tenant-specific model configured and confirm readiness still reports healthy based on base-model availability |
| 5 | Config default preservation (Decision 3 / SSL mode) | AI may change the default value of `database_ssl_mode` or restructure `database_url` construction in a way that alters the effective connection string under default Docker Compose settings, breaking local dev | Run `docker-compose up` unmodified and confirm all services connect to Postgres successfully with no new required env vars, and inspect the resolved connection string in a debug log/test to confirm `sslmode=disable` (or equivalent) still applies by default |
| 6 | docker-compose.yml healthcheck additions | AI may add a `minio` healthcheck or `depends_on` entries for `model_serving`/`mlflow` using a wrong command/port or condition that breaks compose startup rather than fixing it | Run `docker compose config` to validate YAML, then `docker compose up` from a clean state and confirm all services reach a running/healthy state with no new startup failures |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Tenants isolated via per-tenant Postgres schemas, single DB engine | Retry/readiness logic must wrap the shared engine/session layer, not per-tenant connections | Confirm retry decorator is applied in `src/shared/database.py` at the shared engine level, and that no per-tenant-schema-specific retry code was introduced |
| ADR-003: Per-Tenant Model Serving Topology | Each tenant may have its own model-serving endpoint | Readiness must not attempt to check per-tenant model reachability in the shared `/health` endpoint | Inspect the model-availability check in `chat_api`/`extraction_service` readiness code and confirm it checks base/default model only, not iterating per-tenant endpoints |
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Training runs via async Celery-style GPU workers | `training_service` readiness should check its task-queue broker (Redis) consistent with existing dependency use, without adding new synchronous coupling to GPU worker state | Confirm `training_service`'s `/health` checks only its broker connectivity (not GPU worker liveness/state), matching its existing dependency footprint |
| ADR-008: Base Model as Default Inference Model | Base model always available as fallback (supersedes ADR-002 for default behavior) | Readiness checks must treat base-model availability as sufficient; must not report not-ready solely due to absent tenant-specific model | Covered by Hallucination Risk #4 verification step above |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (Postgres retry on slow start): `tests/test_database_retry.py::test_retries_with_exponential_backoff_before_succeeding` — 3 attempts observed with increasing inter-attempt delay before success
- [x] Scenario 2 (MinIO retry on slow start): `tests/test_document_service_storage_retry.py::test_ensure_bucket_retries_then_succeeds_on_transient_endpoint_error` — 3 attempts before success
- [x] Scenario 3 (retry bound exhausted): `tests/test_database_retry.py::test_fatal_error_raised_after_retry_bound_exhausted` and `tests/test_document_service_storage_retry.py::test_ensure_bucket_raises_after_retry_bound_exhausted` — original exception re-raised after bound, not a hang
- [x] Scenario 4 (recovery without restart): Live `docker compose stop minio` / `start minio` against `document_service` — `/health` observed 200 → 503 (minio unhealthy) → 200 (minio healthy) with no process restart
- [x] Scenario 5 (default retry config under Compose): `tests/test_shared_config_ssl_and_retry.py::test_retry_defaults_present` — defaults (0.5s/2x/10s/30s) confirmed unchanged
- [x] Scenario 6 (env override respected): `tests/test_shared_config_ssl_and_retry.py::test_retry_env_override_takes_effect` — `NER_RETRY_MAX_TOTAL_SECONDS=60` reflected in resolved settings
- [x] Scenario 7 (/health 200 all healthy): `tests/test_health_endpoints.py` + live curl — all 5 services (`localhost:8000/8001/8002/8003/8006`) returned 200 with per-dependency breakdown
- [x] Scenario 8 (/health 503 on failure): `tests/test_health_endpoints.py` + live `docker compose stop minio` — `document_service` `/health` returned 503 with `{"minio": {"status": "unhealthy", ...}}`, database still reported healthy
- [x] Scenario 9 (base model readiness): `tests/test_health_endpoints.py::test_chat_api_health_stays_healthy_when_only_base_model_reachable`
- [x] Scenario 10 (/health/live independent): `tests/test_health_endpoints.py::test_extraction_service_health_live_independent_of_dependencies` — `/health/live` 200 while `/health` 503
- [x] Scenario 11 (default config values under Compose): `tests/test_shared_config_ssl_and_retry.py::test_default_ssl_mode_matches_pre_change_behavior`, `test_default_cors_and_service_urls_unchanged_without_overrides`
- [x] Scenario 12 (SSL mode override): `tests/test_shared_config_ssl_and_retry.py::test_database_ssl_mode_override_updates_default_urls_without_full_url_override`

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `/health` verified to return conditional status (503 observed live with minio stopped, not a static 200)
- [x] Risk 2 mitigation confirmed — per-service dependency checks (gateway: DB only; document_service: DB+MinIO; training_service: DB+broker; chat_api/extraction_service: DB+model_serving) verified against each service's actual client usage in code
- [x] Risk 3 mitigation confirmed — finite `stop_after_delay` confirmed in `src/shared/database.py` and `src/document_service/services/storage.py`, and via bounded-exhaustion tests (both complete in well under 2s with tiny test bounds, not hanging)
- [x] Risk 4 mitigation confirmed — base-model readiness check hits `model_serving_url` directly (shared across tenants), independent of any tenant-model configuration
- [x] Risk 5 mitigation confirmed — default Docker Compose startup verified: all 5 services healthy after rebuild/restart, `docker compose config` valid, no `.env` changes required
- [x] Risk 6 mitigation confirmed — `docker compose config` validates; affected services rebuilt and restarted in place and reached healthy state (full `down -v` was skipped per explicit user decision to preserve local dev data — see tasks.md 5.4)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `poetry run pytest tests/test_shared_readiness.py tests/test_shared_config_ssl_and_retry.py tests/test_database_retry.py tests/test_document_service_storage_retry.py tests/test_health_endpoints.py -q` → `30 passed` | Scenarios 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12 | claude (agent) | 2026-08-03 |
| 2 | Functional | Live docker-compose verification: rebuilt/restarted `minio`, `model_serving`, `mlflow`, `gateway`, `chat_api`, `extraction_service`, `document_service`, `training_service`; curl to all 5 `/health` endpoints returned 200 with per-dependency JSON breakdown; `docker compose stop minio` then `start minio` produced `document_service` `/health` transition 200→503→200 with no restart | Scenarios 4, 7, 8 | claude (agent) | 2026-08-03 |
| 3 | Structural | `docker compose config` exits clean (valid YAML); full existing test suite run (`poetry run pytest -q --ignore=tests/test_analytics_dashboard.py`) shows 78 pre-existing failures confirmed via `git stash` comparison to be unrelated to this change's files (touch model_registry, user_auth, training_worker, entity_config, verify_schema, etc. — none of which this change modifies); `openspec validate cloud-readiness-resilience --type change --strict` passes | Structural evidence, Risk 5, Risk 6 | claude (agent) | 2026-08-03 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** cloud-readiness-resilience
**Proposal:** `openspec/changes/cloud-readiness-resilience/proposal.md`
**Spec files reviewed:**
  - specs/service-readiness/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
