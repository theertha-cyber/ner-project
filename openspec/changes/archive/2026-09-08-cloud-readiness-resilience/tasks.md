## 1. Foundations

- [x] 1.1 Add `tenacity` as a direct dependency in `pyproject.toml` (already present transitively via `poetry.lock`); run `poetry lock` / `poetry install` and confirm no version conflicts.
- [x] 1.2 Add retry-tuning settings to `src/shared/config.py`: initial delay, backoff multiplier, max delay, max total retry duration (env-overridable, defaults per design.md Decision 4: 0.5s start, x2 multiplier, 10s cap, 30s total bound).
- [x] 1.3 Add `database_ssl_mode` setting to `src/shared/config.py`, defaulting to current effective value (`disable`), and update `database_url`/`database_url_sync` construction to consume it instead of hardcoding `sslmode=disable` in the URL default.
- [x] 1.4 Create `src/shared/readiness.py` with a shared helper for probing a dependency (Postgres `SELECT 1`, MinIO `head_bucket`, Redis `PING`) and returning a per-dependency status result, so per-service `/health` handlers can compose it.

## 2. Retry on Dependency Initialization

- [x] 2.1 Wrap the Postgres engine's first-connection path in `src/shared/database.py` with a `tenacity` retry decorator using the settings from 1.2.
- [x] 2.2 Wrap MinIO client construction and bucket verification/creation in `src/document_service/services/storage.py` with a `tenacity` retry decorator using the same settings.
- [x] 2.3 If any service constructs a direct Redis client (beyond the Celery broker URL config), wrap its connection check with the same retry pattern; otherwise confirm Celery's own broker retry/connection handling is sufficient and document that no additional wrapping is needed. (Confirmed: no direct Redis client construction outside Celery config anywhere in `src/`; no additional wrapping needed.)
- [x] 2.4 Confirm retry exhaustion (bound from 1.2) results in a clear fatal startup error identifying the failed dependency, not a silent hang or generic traceback. (Verified via `tests/test_database_retry.py::test_fatal_error_raised_after_retry_bound_exhausted` and `tests/test_document_service_storage_retry.py::test_ensure_bucket_raises_after_retry_bound_exhausted` — both `reraise=True`, surfacing the original exception.)

## 3. Readiness and Liveness Endpoints

- [x] 3.1 Update `/health` in `src/chat_api/main.py` to use the shared readiness helper, checking Postgres and base model availability; return 503 with per-dependency JSON on failure, 200 with breakdown on success.
- [x] 3.2 Update `/health` in `src/extraction_service/main.py` the same way (Postgres and base model availability).
- [x] 3.3 Update `/health` in `src/gateway/main.py` to check its direct dependencies (Postgres, and any others gateway directly owns — confirm from `src/gateway/` code, do not assume Redis/MinIO unless gateway actually connects to them). (Confirmed gateway's only direct infra dependency is Postgres.)
- [x] 3.4 Update `/health` in `src/document_service/main.py` to check Postgres and MinIO.
- [x] 3.5 Update `/health` in `src/training_service/main.py` to check Postgres and its Celery/Redis broker connectivity.
- [x] 3.6 Add `/health/live` to all 5 services, returning 200 unconditionally whenever the process can handle the request (no dependency probing). (Also required adding `/health/live` to each service's `TenantContextMiddleware` exempt-path list — it was missing and initially returned 401.)

## 4. Configuration Audit

- [x] 4.1 Grep `src/**/*.py` for hardcoded `localhost`, `127.0.0.1`, and `host.docker.internal` outside of `src/shared/config.py` defaults; fix any application-level hit found (config-file defaults are expected and out of scope per design). (No stray hits found outside `src/shared/config.py` defaults.)
- [x] 4.2 Verify `cors_origins` and `cors_origin_regex` in `src/shared/config.py` are consumed via `settings` everywhere CORS middleware is configured, with no inline hardcoded origin list bypassing settings. (Confirmed across all 8 FastAPI services.)
- [x] 4.3 Verify all inter-service base URLs (`extraction_service_url`, `document_service_url`, `training_service_url`, `chat_api_url`, `model_serving_url`, `analytics_service_url`, `minio_endpoint`, `mlflow_tracking_uri`) are sourced from `settings`, not hardcoded, in every place they're used. (Confirmed.)

## 5. Docker Compose Hygiene

- [x] 5.1 Add a `healthcheck` block to the `minio` service in `docker-compose.yml` (`mc ready local`).
- [x] 5.2 Add appropriate `depends_on` entries for `model_serving` and `mlflow` in `docker-compose.yml` reflecting their actual runtime dependencies.
- [x] 5.3 Run `docker compose config` to validate the updated YAML. (Valid.)
- [x] 5.4 Verify the compose changes against the running stack: rebuilt and restarted the affected services (`minio`, `model_serving`, `mlflow`, `gateway`, `chat_api`, `extraction_service`, `document_service`, `training_service`) in place — full `down -v` was skipped by user decision to avoid wiping local dev data/volumes; all services reached healthy state with no new startup failures.
- [x] 5.5 Simulate a delayed dependency: stopped `minio` (`docker compose stop minio`), confirmed `document_service` `/health` returned 503 identifying MinIO unhealthy, restarted `minio` (`docker compose start minio`), confirmed `document_service` `/health` returned 200 healthy again within ~5s with no manual restart of `document_service`.

## 6. Scenario Verification Tests

- [x] 6.1 Postgres retry-on-slow-start (Scenario 1) — `tests/test_database_retry.py::test_retries_with_exponential_backoff_before_succeeding`; recorded in verification.md row 1.
- [x] 6.2 MinIO retry-on-slow-start for `document_service` (Scenario 2) — `tests/test_document_service_storage_retry.py::test_ensure_bucket_retries_then_succeeds_on_transient_endpoint_error`; recorded in verification.md row 2.
- [x] 6.3 Fatal failure after retry bound exhaustion (Scenario 3) — `tests/test_database_retry.py::test_fatal_error_raised_after_retry_bound_exhausted`; recorded in verification.md row 3.
- [x] 6.4 Recovery without restart once a dependency comes back (Scenario 4) — live verification via `docker compose stop/start minio` against `document_service` (task 5.5), plus `tests/test_document_service_storage_retry.py` retry-then-succeeds coverage; recorded in verification.md row 4.
- [x] 6.5 Default retry config causes no added delay when dependencies are already up (Scenario 5) — `tests/test_shared_config_ssl_and_retry.py::test_retry_defaults_present`; recorded in verification.md row 5.
- [x] 6.6 Retry env var override takes effect (Scenario 6) — `tests/test_shared_config_ssl_and_retry.py::test_retry_env_override_takes_effect`; recorded in verification.md row 6.
- [x] 6.7 `/health` with all dependencies up returns 200 with full breakdown (Scenario 7) — `tests/test_health_endpoints.py` (`test_chat_api_health_200_when_all_dependencies_healthy`, `test_extraction_service_health_200_when_healthy`, `test_gateway_health_reflects_database_state`, `test_document_service_health_checks_database_and_minio`, `test_training_service_health_checks_database_and_celery_broker`) plus live curl verification against the running stack; recorded in verification.md row 7.
- [x] 6.8 `/health` with a dependency down returns 503 with correct breakdown (Scenario 8) — same test file (503 branches of the above tests) plus live `docker compose stop minio` verification; recorded in verification.md row 8.
- [x] 6.9 `/health` on `chat_api`/`extraction_service` stays healthy independent of tenant-specific model config (Scenario 9) — `tests/test_health_endpoints.py::test_chat_api_health_stays_healthy_when_only_base_model_reachable`; recorded in verification.md row 9.
- [x] 6.10 `/health/live` returns 200 while `/health` returns 503 during a dependency outage (Scenario 10) — `tests/test_health_endpoints.py::test_extraction_service_health_live_independent_of_dependencies`; recorded in verification.md row 10.
- [x] 6.11 Default CORS/SSL/service-URL config values unchanged under default Docker Compose settings (Scenario 11) — `tests/test_shared_config_ssl_and_retry.py::test_default_ssl_mode_matches_pre_change_behavior`, `test_default_cors_and_service_urls_unchanged_without_overrides`; recorded in verification.md row 11.
- [x] 6.12 Overridden `database_ssl_mode` env var changes resolved connection SSL mode (Scenario 12) — `tests/test_shared_config_ssl_and_retry.py::test_database_ssl_mode_override_updates_default_urls_without_full_url_override`, `test_explicit_database_url_override_is_not_rewritten_by_ssl_mode`; recorded in verification.md row 12.

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. (30/30 new tests pass: `poetry run pytest tests/test_shared_readiness.py tests/test_shared_config_ssl_and_retry.py tests/test_database_retry.py tests/test_document_service_storage_retry.py tests/test_health_endpoints.py -q` → `30 passed`. Full existing suite run in parallel to confirm no regression from this change — pre-existing failures unrelated to this change's files were identified and confirmed present on `main` before this change via `git stash` comparison.)
- [x] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 7.6 Run `openspec validate cloud-readiness-resilience --type change --strict` and confirm it exits clean before archive.
