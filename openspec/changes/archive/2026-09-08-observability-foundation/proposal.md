## Why

The platform is ten independently deployed processes — eight FastAPI services and two Celery workers — plus Postgres, Redis, MinIO and MLflow, and a failure that crosses a service boundary cannot currently be followed. `logging.basicConfig` is called only in `src/chat_api/main.py` and `src/model_serving/main.py`, so the other eight processes leave the root logger at WARNING with no handler and discard every `logger.info` call they make. Each of the eight `middleware/tenant_context.py` copies generates its own `X-Request-ID` and no service forwards it on an outbound call, so nothing correlates across a hop.

At the same time the platform logs tenant personal data today: `src/chat_api/services/sql_generator.py:1619` writes the generated SQL at INFO, and that SQL carries the literal filter values extracted from resumes. Exit Gate 3 requires "no sensitive content in telemetry" verified by an automated scan, and the code fails that gate as it stands.

This change establishes the instrumentation foundation every later observability change builds on, and closes the leak.

## What Changes

- New `src/shared/observability/` package exposing a single `init_observability(service_name)` entry point, called once from each of the ten service entry points.
- Request context (`request_id`, `tenant_id`, `user_hash`, `trace_id`) held in `contextvars` so any code in a service can read it without threading it through call signatures.
- **BREAKING (internal)**: one shared `ObservabilityMiddleware` replaces the request-ID block duplicated across all eight `src/*/middleware/tenant_context.py` files. Tenant and auth resolution stays in each service's existing middleware; only the correlation and telemetry concern moves.
- Correlation ID propagated end to end: inbound `X-Request-ID` header → contextvar → outbound `httpx` request header → Celery task payload → worker contextvar.
- Structured JSON logging configured in all ten processes, replacing the two ad-hoc `basicConfig` calls. Every record carries `service`, `event`, `tenant_id`, `user_hash`, `request_id` and `trace_id`.
- Redaction filter applied to every log record, dropping SQL text, prompts, answers, document content, extracted entity values, and credentials. Includes rewriting the `sql_attempt` log line at `sql_generator.py:1619` to record query shape (attempt, outcome, defect, row count, duration) instead of query text.
- Opaque identity in all telemetry: tenant as UUID, user as a truncated HMAC-SHA256 of the user id under an environment-sourced pepper. Raw `user_id` and email never appear in a log record or span.
- OpenTelemetry auto-instrumentation for FastAPI, SQLAlchemy, asyncpg, httpx, redis and Celery, producing spans without per-route code.
- `/metrics` endpoint on every service exposing RED metrics (request count, error count, duration histogram) and database pool metrics.
- OTel Collector and Grafana added to `docker-compose.yml` so the acceptance criteria are verifiable on a laptop, independent of the cloud cluster that story 4.5 waits on.

Non-goals, deliberately excluded and covered by later changes: workload-specific span fields and security counters (`observability-workload-instrumentation`), production backends on the cluster (story 4.5), dashboards and alerting (story 5.1), Mimir, Pyroscope, and per-tenant quotas or rate-limit policy.

## Capabilities

### New Capabilities

- `observability`: how the platform emits telemetry — structured logging, trace and metric instrumentation, request correlation across services and workers, and the privacy rules that govern what may appear in telemetry.

### Modified Capabilities

- `local-dev-stack`: the "Single-Command Local Stack Startup" requirement enumerates eight application services and four infrastructure services. Adding the OTel Collector and Grafana changes that enumeration and its startup scenario.
- `secret-hygiene`: the new telemetry HMAC pepper is a secret-class setting and SHALL have no default value in `Settings`, matching the existing treatment of `jwt_secret`, `minio_access_key` and `minio_secret_key`.

## Impact

**Code**
- New: `src/shared/observability/` (`__init__.py`, `context.py`, `logging_config.py`, `metrics.py`, `tracing.py`, `middleware.py`).
- Modified: ten service entry points (`src/{gateway,chat_api,document_service,extraction_service,model_serving,training_service,annotation_service,analytics_service}/main.py`, `src/training_service/celery_app.py`, `src/extraction_service/celery_app.py`).
- Modified: eight `src/*/middleware/tenant_context.py` files, losing their duplicated request-ID block.
- Modified: `src/chat_api/services/sql_generator.py` — the `sql_attempt` log line.
- Modified: outbound HTTP call sites that reach other services, to forward the correlation header.
- Modified: `docker-compose.yml`, `pyproject.toml`, `src/shared/config.py`.

**Dependencies added**: `opentelemetry-distro`, `opentelemetry-exporter-otlp`, instrumentation packages for FastAPI, SQLAlchemy, asyncpg, httpx, redis and Celery, `prometheus-fastapi-instrumentator`, `python-json-logger`.

**Operational**: log output format changes from plain text to JSON, which affects anyone reading `docker logs` directly. Two new containers in the local stack.

**Downstream**: `observability-workload-instrumentation` depends on this change's context and module. Exit Gate 2 ("logs, metrics and traces from every service queryable in one place") and Exit Gate 3 ("no sensitive content in telemetry") both depend on it.

## Open Questions

- Sampling rate for traces in local development. Assumption: sample everything locally, revisit when the production backends land in story 4.5.
- Whether `X-Request-ID` supplied by an external caller should be trusted or always regenerated at the gateway. Assumption: accept it at the gateway edge for support workflows, but treat it as an opaque correlation value only — never as an authorization or tenancy input.
- Whether the HMAC pepper rotates, and what happens to correlation across a rotation. Assumption: no rotation in this change; a rotation breaks historical user correlation by design, which is acceptable.
- Whether the two Celery workers expose `/metrics` over a side HTTP port or push to the collector. Assumption: push, since the workers have no HTTP server today.
