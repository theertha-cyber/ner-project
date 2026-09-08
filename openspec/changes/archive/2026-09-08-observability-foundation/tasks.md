## 1. Dependencies and configuration

- [x] 1.1 Add to `pyproject.toml`: `opentelemetry-distro`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-{fastapi,sqlalchemy,asyncpg,httpx,redis,celery}`, `prometheus-fastapi-instrumentator`, `python-json-logger`. Lock and confirm the image builds.
- [x] 1.2 Add settings to `src/shared/config.py`: `otlp_endpoint` (default empty, meaning export disabled), `telemetry_pepper` (secret-class, **no default**), `log_format` (`json` default, `console` for local), reusing the existing `log_level`.
- [x] 1.3 Add a test asserting `Settings` exposes no default for `telemetry_pepper` and that startup fails when it is absent. → verification rows 30, 31 (`tests/shared/test_config_secret_hygiene.py`)

## 2. Shared observability module

- [x] 2.1 Create `src/shared/observability/context.py` — `contextvars` for `request_id`, `tenant_id`, `user_hash`, `trace_id`, with getters returning `None` outside a request.
- [x] 2.2 Create `src/shared/observability/identity.py` — `hash_user_id()` using HMAC-SHA256 under `telemetry_pepper`, truncated to 16 hex characters.
- [x] 2.3 Add a test asserting the same user id yields the same hash under an unchanged pepper, and that neither the raw id nor an email appears in the output. → verification row 16 (`tests/shared/test_observability_identity.py`)
- [x] 2.4 Create `src/shared/observability/logging_config.py` — JSON formatter emitting `ts`, `level`, `service`, `event`, plus the four context fields, present as null when no request is active. Console formatter selected by `log_format`.
- [x] 2.5 Create the redaction `logging.Filter` in the same module: strip values for `sql`, `prompt`, `answer`, `content`, `text`, `document_text`, `entity_value`, `password`, `token`, `authorization`, `api_key`. Installed unconditionally by `init_observability`.
- [x] 2.6 Add a test asserting each prohibited field name is stripped from an emitted record. → verification row 13 (`tests/shared/test_observability_redaction.py`)
- [x] 2.7 Add a test asserting a record emitted with no active request carries all four context keys with null values. → verification rows 5, 7 (risk register) (`tests/shared/test_observability_logging.py`)
- [x] 2.8 Create `src/shared/observability/tracing.py` — OTel tracer provider, OTLP exporter with a **batch/async** span processor, no-op when `otlp_endpoint` is empty, and auto-instrumentation registration for FastAPI, SQLAlchemy, asyncpg, httpx, redis and Celery.
- [x] 2.9 Create `src/shared/observability/metrics.py` — RED metrics registry plus database pool gauges. No `tenant_id` label on any metric family.
- [x] 2.10 Create `src/shared/observability/middleware.py` — `ObservabilityMiddleware`: read or generate `X-Request-ID`, cap length and sanitize before use, set contextvars, set the response header. **Correlation and telemetry only** — no token decoding, no tenant resolution, no authorization.
- [x] 2.11 Create `src/shared/observability/__init__.py` exposing `init_observability(service_name)` wiring logging, tracing and metrics.
- [x] 2.12 Add a test asserting `logging.basicConfig` appears nowhere in `src/` outside `src/shared/observability/`. → verification row 2 (`tests/shared/test_observability_wiring.py`)

## 3. Local observability stack

- [x] 3.1 Add `otel-collector` to `docker-compose.yml` with an OTLP receiver and exporters to Prometheus, Loki and Tempo; add its config file under `deploy/observability/`.
- [x] 3.2 Add `grafana` to `docker-compose.yml` with the three datasources provisioned, plus the `prometheus`, `loki` and `tempo` containers the collector exports to.
- [x] 3.5 **Gap found after the fact.** Loki was running, provisioned and receiving
      nothing: no process exported logs over OTLP, so records reached stdout only.
      No scenario in `verification.md` covered log *delivery* — only emission — so
      nothing failed. **Resolved by adding the exporter, not by dropping Loki:** the
      trace-to-logs link is most of the reason `trace_id` is on every record, and it
      needs the records in a store beside the spans. `build_otlp_log_handler()` in
      `src/shared/observability/logging_config.py` attaches a second handler carrying
      the same context and redaction filters, batched, off when `otlp_endpoint` is
      empty. The missing scenario is now in the spec and is verification row 32
      (`tests/shared/test_observability_log_export.py`, plus live Loki evidence 13).
- [x] 3.3 Verify `docker compose up` brings the full stack healthy and the gateway health endpoint responds. → verification rows 25, 26 (manual run, transcript captured)
- [x] 3.4 Verify Grafana responds on its root URL and the collector accepts an OTLP export. → verification row 27 (manual run)

## 4. Service conversion — one service at a time

- [x] 4.1 Convert `gateway`: call `init_observability("gateway")`, mount `ObservabilityMiddleware`, remove the request-ID block from `src/gateway/middleware/tenant_context.py`, leaving token decode, tenant resolution and the exempt-path list untouched.
- [x] 4.2 Run the tenant-isolation suite against `gateway` and confirm it is green before proceeding. → verification row 11
- [x] 4.3 Convert `chat_api` the same way, removing its ad-hoc `configure_logging()`.
- [x] 4.4 Convert `document_service`, `extraction_service`, `model_serving`, `training_service`, `annotation_service`, `analytics_service` — one commit each, tenant-isolation suite green after each.
- [x] 4.5 Convert the two Celery workers: `init_observability()` in `src/training_service/celery_app.py` and `src/extraction_service/celery_app.py`, with OTLP metric export rather than an HTTP `/metrics` endpoint.
- [x] 4.6 Add a test asserting no request-identifier generation remains in any of the eight `src/*/middleware/tenant_context.py` files. → verification row 10 (`tests/shared/test_observability_wiring.py`)
- [x] 4.7 Add a test asserting a log record emitted from a service that previously had no handler now reaches stdout, and that `NER_LOG_LEVEL=DEBUG` enables DEBUG records. → verification rows 1, 3 (`tests/shared/test_observability_logging.py`)
- [x] 4.8 Add a test asserting a log record emitted during an authenticated request carries matching `request_id`, `tenant_id`, `user_hash` and `trace_id`, that `user_hash` is present, and that no raw user id, email or tenant slug appears. → verification rows 4, 15, 17 (`tests/shared/test_observability_context.py`)

## 5. Correlation propagation

- [x] 5.1 Forward `X-Request-ID` from the ambient context on every outbound `httpx` call to another platform service (shared client wrapper or event hook — one implementation, not per call site).
- [x] 5.2 Add a Celery header hook: publish the correlation identifier on enqueue, restore it into the contextvar on task start, in both workers.
- [x] 5.3 Integration test: a gateway request carrying `X-Request-ID: abc-123` triggers an onward service call; assert the outbound header and the receiving service's `request_id`. → verification row 6 (`tests/integration/test_correlation_propagation.py`)
- [x] 5.4 Integration test: a request enqueues a Celery task; assert the worker's records carry the originating `request_id`. → verification row 7 (same file)
- [x] 5.5 Test: a request with no `X-Request-ID` receives a generated one in the response header. → verification row 8
- [x] 5.6 Test: a forged inbound `X-Request-ID` does not influence tenant or user resolution, which still derive from validated JWT claims. → verification row 9 (`tests/integration/test_correlation_not_trusted.py`)

## 6. Close the sensitive-content leak

- [x] 6.1 Rewrite the `sql_attempt` log line at `src/chat_api/services/sql_generator.py:1619` to emit structured fields — `attempt`, `max_attempts`, `outcome`, `defect`, `rows`, `duration_ms`, `schema` — and drop `sql=%s`. Audit the surrounding lines (1597, 1151, 1196, 1267, 1293) for the same pattern.
- [x] 6.2 Audit `src/chat_api/graph/nodes.py`, `services/entity_resolver.py`, `services/guardrails.py` and `src/extraction_service/` for any log call carrying question text, answer text, prompts or entity values; convert to structured shape fields.
- [x] 6.3 Test: the `sql_attempt` record contains the shape fields and no SQL string. → verification row 12 (`tests/chat_api/test_sql_attempt_logging.py`)
- [x] 6.4 Integration test: run an extraction against a seeded document and assert no captured log record contains a seeded entity value. → verification row 14 (`tests/integration/test_no_pii_in_logs.py`)

## 7. Traces and metrics

- [x] 7.1 Add `/metrics` to the eight FastAPI services, exempt from tenant middleware and requiring no Authorization header.
- [x] 7.2 Test: `GET /metrics` returns HTTP 200 in Prometheus exposition format without auth, and the request counter increments across a served request. → verification rows 22, 23 (`tests/shared/test_metrics_endpoint.py`)
- [x] 7.3 Test: no metric family exposed by any service carries a `tenant_id` label. → verification row 24 (same file)
- [ ] 7.8 **Scope correction found during review of `observability-workload-instrumentation`.** Task 7.3 implemented row 24 as a blanket scan of every `/metrics` line for `tenant_id=` (`tests/shared/test_metrics_endpoint.py:113`). The requirement text was always scoped to "any metric introduced by this change"; the scenario and the test were not. That next change deliberately adds five allowlisted tenant-labelled families, which would turn this test red and invite someone to weaken it rather than fix it. Narrow the test to enumerate the families this change declares — importing them, not string-matching output — and re-collect row 24's evidence. The scenario is already reworded in the spec.
- [x] 7.4 Integration test on the running local stack: one gateway request producing spans in two processes under a single trace id. → verification row 18 (`tests/integration/test_tracing_cross_service.py`)
- [x] 7.5 Integration test: a trace extends into a Celery worker under the same trace id. → verification row 19 (same file)
- [x] 7.6 Test: a log record's `trace_id` equals the trace id of the spans from the same request. → verification row 20 (same file)
- [x] 7.7 Test: with the OTLP endpoint unreachable, requests are served normally and no unhandled exception is raised; confirm the same with `otel-collector` stopped and health checks still passing. → verification rows 21, 28 (`tests/integration/test_telemetry_failure_isolation.py`)

## 8. Documentation

- [x] 8.1 Update `AGENTS.md` and/or `docs/standards/coding-standards.md` with the telemetry rule: log the shape of data, never the data; structured fields required for anything touching sensitive values.
- [x] 8.2 Confirm the `AGENTS.md` no-hardcoded-secrets statement still holds and covers the new pepper. → verification row 29
- [x] 8.3 Update `docs/local-dev.md` with the two new containers and the Grafana URL.

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. Diff the failing-test set against the known-red baseline on `main` rather than expecting a fully green suite.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Obtain second-reviewer sign-off on the redaction and opaque-identity requirements (rows 12–17), given single-author ownership of this change.
- [ ] 9.6 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.7 Run `openspec validate observability-foundation --type change --strict` and confirm it exits clean before archive.
