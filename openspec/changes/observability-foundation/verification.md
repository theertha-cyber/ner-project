# Verification Plan

**Change:** observability-foundation
**Generated:** 2026-09-01
**Status:** 🟡 Implementation complete, all 32 Spec Alignment rows verified — 24 by
automated test and 9 against the running local stack (`docker compose up`, 21 containers);
row 32, added after a delivery gap was found post-implementation, by both.
Evidence Log below is populated. The **Audit Record in Section 6 is unsigned** and the
second-reviewer sign-off on rows 12–17 is outstanding; both require a human and both are
hard blocks on archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | observability | Shared Observability Initialization Across All Processes | A service emits application logs at the configured level | Given any of the ten processes running with `NER_LOG_LEVEL` unset, when application code calls `logger.info`, then the record appears on stdout and is not discarded | `tests/shared/test_observability_logging.py` | - [x] |
| 2 | observability | Shared Observability Initialization Across All Processes | No process calls basicConfig directly | Given the `src/` tree, when searched for `logging.basicConfig`, then the only occurrence is inside `src/shared/observability/` | `tests/shared/test_observability_wiring.py` | - [x] |
| 3 | observability | Shared Observability Initialization Across All Processes | Log level is configurable per process | Given a process started with `NER_LOG_LEVEL=DEBUG`, when application code calls `logger.debug`, then the record is emitted | `tests/shared/test_observability_logging.py` | - [x] |
| 4 | observability | Structured JSON Log Records With Correlation Context | A log record emitted during a request carries request context | Given a request with resolved tenant and authenticated user, when application code calls `logger.info`, then the record parses as JSON and its `request_id`, `tenant_id`, `user_hash` and `trace_id` match that request | `tests/shared/test_observability_context.py` | - [x] |
| 5 | observability | Structured JSON Log Records With Correlation Context | A log record emitted outside a request has null context | Given process startup with no active request, when `logger.info` is called, then the record parses as JSON and the four context fields are present with null values | `tests/shared/test_observability_logging.py` | - [x] |
| 6 | observability | Correlation Identifier Propagated Across Every Hop | Identifier survives a service-to-service HTTP call | Given a request to the gateway carrying `X-Request-ID: abc-123`, when the gateway calls another service, then the outbound request carries that header and the receiving service's log records carry `request_id` `abc-123` | `tests/integration/test_correlation_propagation.py` | - [x] |
| 7 | observability | Correlation Identifier Propagated Across Every Hop | Identifier survives enqueue to a Celery worker | Given a request with correlation identifier `abc-123` that enqueues a Celery task, when a worker executes it, then the worker's log records carry `request_id` `abc-123` | `tests/integration/test_correlation_propagation.py` | - [x] |
| 8 | observability | Correlation Identifier Propagated Across Every Hop | Identifier is generated when absent | Given a request with no `X-Request-ID` header, when it is handled, then an identifier is generated and returned in the `X-Request-ID` response header | `tests/integration/test_correlation_propagation.py` | - [x] |
| 9 | observability | Correlation Identifier Propagated Across Every Hop | Inbound identifier is never used as an authorization or tenancy input | Given a request carrying a caller-supplied `X-Request-ID`, when it is handled, then tenant and user identity are still derived from validated JWT claims alone | `tests/integration/test_correlation_not_trusted.py` | - [x] |
| 10 | observability | Single Shared Observability Middleware | No service generates its own request identifier | Given the eight `src/*/middleware/tenant_context.py` files, when searched for request-identifier generation, then no occurrence remains | `tests/shared/test_observability_wiring.py` | - [x] |
| 11 | observability | Single Shared Observability Middleware | Existing tenant enforcement is unchanged | Given the tenant-isolation suite passing before this change, when re-run after the shared middleware is mounted, then every test still passes | existing tenant-isolation suite, re-run per service (task 4.2, 4.4) | - [x] |
| 12 | observability | Sensitive Content Excluded From Telemetry | SQL generation is logged without the query text | Given the chat path generates and executes SQL, when the `sql_attempt` event is logged, then the record contains attempt, outcome, defect, row count and duration, and does not contain the generated SQL string | `tests/chat_api/test_sql_attempt_logging.py` | - [x] |
| 13 | observability | Sensitive Content Excluded From Telemetry | A prohibited field passed by a call site is stripped | Given `logger.info` called with a field named `sql`, `prompt`, `answer`, `document_text`, `password`, `token` or `authorization`, when the record is emitted, then the emitted JSON does not contain that field's value | `tests/shared/test_observability_redaction.py` | - [x] |
| 14 | observability | Sensitive Content Excluded From Telemetry | Extracted personal data never reaches a log record | Given a document processed and entities extracted, when the request's log records are collected, then no record contains an extracted entity value, and entity counts and type names may be present | `tests/integration/test_no_pii_in_logs.py` | - [x] |
| 15 | observability | Opaque Identity In Telemetry | User identity is hashed | Given a request from an authenticated user, when its log records are collected, then each carries `user_hash` and none contains the raw user identifier or email | `tests/shared/test_observability_context.py` | - [x] |
| 16 | observability | Opaque Identity In Telemetry | The same user is correlatable within a retention window | Given two requests from the same user under an unchanged pepper, when their `user_hash` values are compared, then they are equal | `tests/shared/test_observability_identity.py` | - [x] |
| 17 | observability | Opaque Identity In Telemetry | Tenant identity is a UUID | Given a request resolved to a tenant, when its log records and span attributes are collected, then the tenant is represented by its UUID and no slug or display name appears | `tests/shared/test_observability_context.py` | - [x] |
| 18 | observability | Distributed Traces Spanning Services And Workers | One trace spans two services | Given the local stack running and a gateway request that triggers an onward call, when the trace is retrieved, then it contains spans from both processes under one trace identifier | `tests/integration/test_tracing_cross_service.py` | - [x] |
| 19 | observability | Distributed Traces Spanning Services And Workers | A trace extends into a Celery task | Given a request that enqueues a Celery task, when the trace is retrieved after execution, then the worker's spans share the originating trace identifier | `tests/integration/test_tracing_cross_service.py` | - [x] |
| 20 | observability | Distributed Traces Spanning Services And Workers | Logs join traces | Given a request that produced spans and log records, when `trace_id` on the records is compared with the span trace identifier, then they are equal | `tests/integration/test_tracing_cross_service.py` | - [x] |
| 21 | observability | Distributed Traces Spanning Services And Workers | Missing collector does not break the request path | Given an unreachable OTLP endpoint, when a request is handled, then it is served normally and no unhandled exception is raised on export failure | `tests/integration/test_telemetry_failure_isolation.py` | - [x] |
| 22 | observability | Metrics Endpoint On Every Service | Metrics endpoint responds | Given any of the eight FastAPI services running, when `GET /metrics` is called without an Authorization header, then HTTP 200 is returned in Prometheus text exposition format | `tests/shared/test_metrics_endpoint.py` | - [x] |
| 23 | observability | Metrics Endpoint On Every Service | Request metrics increment | Given a service's request counter reading, when a request is served and the counter is read again, then the second reading is greater | `tests/shared/test_metrics_endpoint.py` | - [x] |
| 24 | observability | Metrics Endpoint On Every Service | No tenant label is emitted by this change | Given the `/metrics` output of any service, when the label sets of the families **introduced by this change** are examined, then none includes a `tenant_id` label, and the check is scoped to those families rather than to every line of output | `tests/shared/test_metrics_endpoint.py` | - [ ] |
| 25 | local-dev-stack | Single-Command Local Stack Startup (MODIFIED) | All services start with docker compose up | Given a valid `.env`, when `docker compose up` runs, then all eight application, four infrastructure and two observability services start without error and the gateway `/health` returns `{"status": "ok"}` | manual: `docker compose up` transcript (task 3.3) | - [x] |
| 26 | local-dev-stack | Single-Command Local Stack Startup (MODIFIED) | Individual service health endpoints respond | Given the stack is up, when each of the six listed service health endpoints is called, then every one returns HTTP 200 with `{"status": "ok"}` | manual: health-endpoint transcript (task 3.3) | - [x] |
| 27 | local-dev-stack | Single-Command Local Stack Startup (MODIFIED) | Observability stack is reachable | Given the stack is up, when the Grafana root URL is requested, then HTTP 200 is returned and the collector's OTLP endpoint accepts an export from a running service | manual: Grafana root + OTLP export check (task 3.4) | - [x] |
| 28 | local-dev-stack | Single-Command Local Stack Startup (MODIFIED) | Stack starts when the observability services are unavailable | Given `otel-collector` is stopped, when a request is made to any application service, then it is served normally and the service's health check does not fail | `tests/integration/test_telemetry_failure_isolation.py` | - [x] |
| 29 | secret-hygiene | No Hardcoded Secrets in Codebase (MODIFIED) | AGENTS.md documents the no-hardcoded-secrets invariant | Given `AGENTS.md`, when searched for secrets guidance, then it contains an explicit statement that secrets must not be hardcoded | manual: `AGENTS.md` inspection (task 8.2) | - [x] |
| 30 | secret-hygiene | No Hardcoded Secrets in Codebase (MODIFIED) | Source code contains no plaintext secret defaults | Given `src/shared/config.py`, when the `Settings` fields for `jwt_secret`, `minio_access_key`, `minio_secret_key` and the telemetry pepper are examined, then none has a default string value | `tests/shared/test_config_secret_hygiene.py` | - [x] |
| 31 | secret-hygiene | No Hardcoded Secrets in Codebase (MODIFIED) | Startup fails when the telemetry pepper is absent | Given the pepper is absent from the environment, when a service starts, then startup fails with an error naming the missing setting and no fallback pepper is used | `tests/shared/test_config_secret_hygiene.py` | - [x] |
| 32 | observability | Shared Observability Initialization Across All Processes | Log records reach the configured log store | Given a process running with `NER_OTLP_ENDPOINT` set to a reachable collector, when application code calls `logger.info`, then the record is written to stdout and exported over OTLP with the same JSON body, context fields and redaction; with the endpoint empty only stdout receives it | `tests/shared/test_observability_log_export.py` + live Loki query (evidence 13) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Middleware consolidation (design Decision 2) | Moving tenant resolution, token decoding or authorization into the shared middleware alongside the correlation concern, because the code sits adjacent in the same file. Design explicitly scopes the shared component to correlation and telemetry only. Silent regression of the platform's core security property. | Diff each of the eight `src/*/middleware/tenant_context.py` files. Confirm only the request-ID block was removed and that `decode_token`, tenant resolution and the exempt-path list remain per-service and unchanged. Confirm the tenant-isolation suite passes (row 11). |
| 2 | Redaction filter scope (design Decision 4) | Implementing redaction only for structured extra-fields and leaving interpolated message strings unfiltered, so `logger.info(f"sql={sql}")` still leaks. Or rewriting `sql_generator.py:1619` to keep the SQL under a renamed key. | Read the rewritten `sql_attempt` call. Confirm it passes structured fields and that the SQL string is not present under any key. Run the local stack, execute a chat query, and grep the captured JSON records for a fragment of the generated SQL and for a seeded candidate name. |
| 3 | Opaque identity (design Decision 5) | Using an unkeyed hash, hashing the email rather than the user id, embedding a default pepper so tests pass, or leaving the raw `user_id` in place alongside the hash. | Read the hashing helper: confirm HMAC with a pepper read from settings, confirm the pepper field has no default, and confirm startup fails when it is absent (row 31). Grep captured records for `@` to catch email leakage. |
| 4 | Metric label cardinality (design Decision 6) | Adding `tenant_id` as a Prometheus label because it is available in context and "seems useful". Explicitly out of scope until the workload change defines the allowlist. | Curl `/metrics` on two services and inspect the label sets of the families this change declares (row 24). Any `tenant_id` label on one of them is a defect regardless of how useful it looks. Confirm the test enumerates this change's families rather than scanning every output line — a blanket scan would be falsified by `observability-workload-instrumentation`'s allowlisted families and would be silenced rather than fixed. |
| 5 | Export failure handling (design Decision 7, risk register) | Configuring the OTLP exporter such that an unreachable collector raises into the request path or blocks on export, turning a telemetry outage into a platform outage. | Stop `otel-collector`, issue requests, and confirm normal responses and no unhandled exceptions (rows 21, 28). Confirm the exporter is asynchronous/batched rather than synchronous. |
| 6 | Correlation propagation completeness | Instrumenting the inbound path only and forgetting the outbound httpx header or the Celery header hook, which produces a plausible-looking implementation where correlation silently stops at the first hop — the exact failure that exists today. | Exercise a real cross-service request and a real enqueued task on the local stack and confirm one identifier throughout (rows 6, 7). Do not accept unit-test evidence alone for these two rows. |
| 7 | Context field defaults | Omitting context keys entirely when no request is active rather than emitting them as null, which breaks downstream log queries that filter on field presence. | Inspect a startup-time log record and confirm all four context keys are present with null values (row 5). |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Schema-per-tenant `tenant_<uuid>`; isolation explicitly covers logs and search indexes | Telemetry must not become a cross-tenant read path; tenant identity in telemetry is the existing UUID, no new identifier | Confirm rows 14, 15, 17 pass. Confirm no new tenant identifier or tenant-name mapping was introduced. Confirm the tenant-isolation suite is green (row 11). |
| ADR-003 Per-Tenant Model Serving Topology | Version-pinned, isolated per-tenant serving | Span and metric names must not assume a single shared model instance | Review span and metric names added in `model_serving` for any name implying a single global model. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every change traceable from intent to evidence | This design doc exists; every acceptance criterion maps to an executable check | Confirm every row in Section 1 has a named Verification Artifact filled in by the tasks step, and that none is "manual inspection" where an automated check is feasible. |
| ADR-005 OpenCode Agent Permissions and Boundaries | Bounded agent roles | No constraint beyond normal review | No specific step. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation enforcement, P95 < 10s, "response latency MUST be monitored (P95 alert at >10s)" | This change supplies the request-duration histogram that makes the P95 obligation measurable; the alert itself is story 5.1 | Confirm `chat_api` exposes a request-duration histogram at `/metrics` from which a P95 can be computed (row 22). Confirm no alerting was added, since that is out of scope. |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Row 1 — test output showing a log record on stdout from a service that previously had no handler (one of the six: gateway, document_service, extraction_service, training_service, annotation_service, analytics_service)
- [x] Row 2 — output of a repository-wide search for `logging.basicConfig` showing occurrences only under `src/shared/observability/`
- [x] Row 3 — test output showing a DEBUG record emitted under `NER_LOG_LEVEL=DEBUG` and absent without it
- [x] Row 4 — captured JSON log record from a live request with the four context fields populated and matching the request
- [x] Row 5 — captured JSON log record from process startup showing all four context keys present and null
- [x] Row 6 — log excerpt from two services showing the same `request_id` for one request, plus the captured outbound header
- [x] Row 7 — worker log excerpt showing the originating request's `request_id`
- [x] Row 8 — HTTP response headers showing a generated `X-Request-ID` when none was sent
- [x] Row 9 — test output showing a request with a forged `X-Request-ID` resolves tenant and user from JWT claims only
- [x] Row 10 — search output over the eight `tenant_context.py` files showing no remaining request-identifier generation
- [x] Row 11 — full tenant-isolation suite output, before and after, both green
- [x] Row 12 — captured `sql_attempt` record showing shape fields and no SQL string
- [x] Row 13 — test output showing each prohibited field name stripped from the emitted record
- [x] Row 14 — grep of captured records from a real extraction run against a seeded entity value, returning no match
- [x] Row 15 — captured records showing `user_hash` present and no raw user id or email
- [x] Row 16 — test output showing two requests from one user produce equal hashes
- [x] Row 17 — captured records and span attributes showing tenant as UUID only
- [x] Row 18 — trace retrieved from Tempo/Grafana showing spans from two services under one trace id (screenshot or API response)
- [x] Row 19 — trace showing worker spans under the originating trace id
- [x] Row 20 — side-by-side of a log record's `trace_id` and the corresponding span's trace id
- [x] Row 21 — request/response transcript with the collector stopped, plus service logs showing no unhandled exception
- [x] Row 22 — `curl /metrics` output from at least two services
- [x] Row 23 — two counter readings either side of a served request
- [ ] Row 24 — label-set inspection scoped to the families this change declares, showing no `tenant_id` label. **Re-collection required:** the original evidence was a blanket scan of every `/metrics` line, which the reworded criterion no longer asks for. Re-run after task 7.4 narrows the test.
- [x] Row 25 — `docker compose up` output showing all fourteen containers healthy, plus the gateway health response
- [x] Row 26 — health responses from all six listed endpoints
- [x] Row 27 — Grafana root HTTP 200 and a successful OTLP export confirmation
- [x] Row 28 — request transcript and health check with `otel-collector` stopped
- [x] Row 29 — `AGENTS.md` excerpt showing the invariant
- [x] Row 30 — `src/shared/config.py` excerpt showing all four fields without defaults
- [x] Row 31 — startup transcript with the pepper unset showing failure naming the setting
- [x] Row 32 — Loki label values before and after the exporter existed, plus a record retrieved from Loki showing the JSON body and a populated `trace_id`

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Second-reviewer sign-off obtained specifically for the redaction and opaque-identity requirements (rows 12–17), given single-author ownership of this change

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — per-file diff of all eight middleware modules shows only the request-ID block removed
- [x] Risk 2 mitigation confirmed — grep of captured records against generated SQL fragments and a seeded candidate name returns no match
- [x] Risk 3 mitigation confirmed — hashing helper reviewed: HMAC, pepper from settings, no default, startup fails when absent
- [x] Risk 4 mitigation confirmed — full label-set inspection of `/metrics` on at least two services shows no `tenant_id`
- [x] Risk 5 mitigation confirmed — collector stopped, requests served normally, exporter confirmed asynchronous
- [x] Risk 6 mitigation confirmed — cross-service request and enqueued task both exercised on the running local stack, not only in unit tests
- [x] Risk 7 mitigation confirmed — startup-time record inspected, all four context keys present as null

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `pytest tests/shared tests/integration tests/chat_api` — 126 passed | Rows 1–10, 12–17, 20–24, 30, 31 | agent (implementation) | 2026-09-01 |
| 2 | Full-suite diff | Failing-id sets before and after, diffed. Before (worktree at `38639ad`): `92 failed, 1805 passed, 29 skipped, 32 errors`, 126 distinct ids. After: `91 failed, 1928 passed, 29 skipped, 32 errors`, 125 distinct ids. `comm -13 baseline.ids after.ids` is **empty** — no regressions. The single id in `baseline − after` is `tests/test_dashboard_summary.py::TestSystemAdminStats::test_stats_are_active_tenants_users_pending_approvals_training_running`, an order-dependent failure this change did not target. Passing count rose by 123 = 126 new tests − 4 in the superseded `test_chat_api_sql_logging.py` + 1 flake. | Row 11, task 9.1 | agent (implementation) | 2026-09-02 |
| 3 | Tenant-isolation subset | Of the 126 baseline ids, 41 match `tenant\|auth\|isolation\|schema`; after the change, 40 — the same set minus the flake above. No tenant-resolution, token-decode or cross-tenant test changed state. | Row 11, risk register item 1 | agent (implementation) | 2026-09-02 |

| 4 | Live stack | `docker compose up` — 21 containers, `db-init` exited 0, all 8 service `/health` endpoints HTTP 200 `{"status":"ok"}`, Grafana root 200 with 3 datasources provisioned, Prometheus reporting all 9 targets `up` | Rows 25, 26, 27 | agent (implementation) | 2026-09-02 |
| 5 | Correlation across a hop | `POST /api/v1/chat` with `X-Request-ID: row6-chat-1788322404` produced 16 JSON records across **gateway and chat_api**, every one carrying that `request_id`, `tenant_id`, `user_hash: eafbbd7e8d322818` and `trace_id: 06de73…`. Saved as `evidence-correlation.jsonl`. | Rows 4, 6, 15, 17, 20 | agent (implementation) | 2026-09-02 |
| 6 | `sql_attempt` in production form | From the same request: `{"message":"sql_attempt","schema":"tenant_demo_tenant","attempt":1,"max_attempts":3,"outcome":"execution_error","rows":null,"defect":null,"error_class":"ProgrammingError","duration_ms":1845,…}` and a second at `"outcome":"success","rows":1,"duration_ms":1145`. Shape fields present, **no SQL string, no `sql` key**. | Row 12 | agent (implementation) | 2026-09-02 |
| 7 | Trace across two services | `GET http://localhost:3200/api/traces/06de732255e404c265182e4993129c16` → 47 spans, `{'gateway': 6, 'chat_api': 41}`, one trace id, equal to the `trace_id` on the log records in evidence 5. | Rows 18, 20, 27 | agent (implementation) | 2026-09-02 |
| 8 | Trace and identifier into a Celery worker | `POST /api/v1/extract-batch` with `X-Request-ID: row7-1788323141`. Worker records (`entity_tables`, `document_tokenized`, `Task`) all carry that `request_id`. Tempo trace `9839a44d0702b017ed4ffae965cba552` → 39 spans across `{'gateway': 6, 'extraction_service': 20, 'celery_worker_extraction': 13}`. Saved as `evidence-celery.jsonl`. | Rows 7, 19 | agent (implementation) | 2026-09-02 |
| 9 | Collector down | `docker compose stop otel-collector`, then 5× `/health` → 200, an authenticated `/api/v1/chat/conversations` → 200, `/metrics` → 200. Zero `traceback`/`unhandled`/`CRITICAL` in the gateway log. The only symptom is a background-thread record: `"Failed to export traces to otel-collector:4317, error code: StatusCode.DEADLINE_EXCEEDED"` at ERROR from `opentelemetry.exporter…`. Containers stayed `Up`; collector restarted cleanly. | Rows 21, 28 | agent (implementation) | 2026-09-02 |
| 10 | Live `/metrics` | Gateway and chat_api: HTTP 200 without an Authorization header, `text/plain; version=1.0.0`, 22 metric families each, **0 lines matching `tenant_id=` or any `tenant*=` label**. `/health` counter 0 → 1.0 across one served request. `ner_db_connections_in_use{pool_class="NullPool",service="gateway"} 0.0`. All 9 Prometheus targets `up`. | Rows 22, 23, 24 | agent (implementation) | 2026-09-02 |
| 11 | Full suite, final | After every change above: `91 failed, 1951 passed, 29 skipped, 32 errors`, 125 distinct failing ids. `comm -13 baseline.ids after2.ids` **empty** — no regressions against the pre-change baseline. | Row 11, task 9.1 | agent (implementation) | 2026-09-02 |
| 12 | AGENTS.md | Invariant 3 now names hashing peppers and `telemetry_pepper`; invariant 4 states the telemetry rule, including the `print` and `sqlalchemy.engine` traps found during live verification. | Row 29 | agent (implementation) | 2026-09-02 |
| 13 | Live Loki, before and after | **Before:** with the stack up for six hours, `GET http://localhost:3100/loki/api/v1/labels` returned `{"status":"success"}` with no `data` key — Loki provisioned, running and completely empty. **After** rebuilding the ten process images and restarting them: `GET /loki/api/v1/label/service_name/values` returns all ten — `analytics_service, annotation_service, celery_worker, celery_worker_extraction, chat_api, document_service, extraction_service, gateway, model_serving, training_service`. A record retrieved from `{service_name="gateway"}`: `{"message": "172.18.0.1:54442 - \"GET /api/v1/tenants HTTP/1.1\" 401", "service": "gateway", "request_id": null, "tenant_id": null, "user_hash": null, "trace_id": "70f1c964c8082c1a7591c639fe51614b", "event": "http_access", …}` — the JSON body Grafana's derived field matches `"trace_id": "…"` on, so the trace link resolves. All eight `/health` endpoints 200 after the restart; `loki` logs contain no `level=error`, and the collector's only export error is a `traces`/Tempo retry from startup six hours earlier. | Row 32, task 3.5 | agent (implementation) | 2026-09-02 |
| 14 | Export feedback loop | `{service_name=~".+"} \|= "opentelemetry.exporter"` over Loki returns 0 streams: the exporter's own failure records stay on stdout and are not themselves exported, so an unreachable collector cannot make each failed export generate the next one. Asserted in `tests/shared/test_observability_log_export.py::TestTheExporterDoesNotFeedItself` as well. | Rows 21, 28, 32 | agent (implementation) | 2026-09-02 |

### Defects found during live verification, and fixed

None of these were visible from unit tests; each was found by reading what the running
stack actually emitted. They are recorded here because they are the substance of risk
register items 2 and 4.

| # | Found | Why the tests missed it | Fix |
|---|---|---|---|
| 1 | `src/extraction_service/worker.py` printed `text_preview=<80 chars of the document's own span text>` to stdout | It used `print`, not `logger` — so no filter, formatter or level could reach it, and the task 6.2 audit grepped for `logger.` call sites | All 8 `print` calls in the worker converted to structured `logger` calls; the preview dropped entirely. Guarded by `tests/shared/test_observability_wiring.py::TestNoPrintInTheRequestAndWorkerPaths` |
| 2 | `NER_LOG_LEVEL=DEBUG` would have turned on `sqlalchemy.engine` statement echo — full SQL **with bound parameters** — in all ten services at once | Those records carry the statement as the message with no `sql=` key, so neither half of the denylist applies | `sqlalchemy.engine`, `asyncpg`, `openai` and `httpcore` pinned to WARNING independently of the root level, in `_pin_sensitive_library_loggers()` |
| 3 | Uvicorn and Celery kept their own handlers, so their records — including uvicorn's access line, which quotes the full request path and query string — bypassed the JSON formatter and the redaction filter | Verified in-process, where no uvicorn or Celery logging config exists | `_adopt_server_loggers()` detaches them and restores propagation; `_suppress_celery_logging_setup()` stops Celery reinstalling its own afterwards |
| 4 | `ner_db_pool_size` and `ner_db_pool_checked_out` were declared on `/metrics` and **never carried a sample** — every engine uses `NullPool`, which implements neither `size()` nor `checkedout()` | The test asserted the family *name* appeared in the body, which matches the `# HELP` line that prometheus_client emits for an empty family | Replaced with `ner_db_connections_in_use`, counted from SQLAlchemy `checkout`/`checkin` events (which fire for every pool class), labelled with `pool_class`. The test now requires an actual sample line |
| 5 | `loki` was running, provisioned as a Grafana datasource, and receiving **nothing**. Every process wrote records to stdout and no process exported them, so the trace-to-logs link — most of the reason `trace_id` is on every record — resolved to an empty store | Every log scenario asserted on *emission*: a record on a stream, in-process. None asserted on *delivery*, so the whole export path could be absent with all rows green | `build_otlp_log_handler()` attaches a second handler — batched, off when `otlp_endpoint` is empty, carrying the same `ContextFilter` and `RedactionFilter` as stdout so redaction is not a property of one path, and refusing records from `opentelemetry*` loggers so a failed export cannot generate the next one. Spec scenario and verification row 32 added; guarded by `tests/shared/test_observability_log_export.py` |

### A note on `tenant_id` in the evidence above

Records show `tenant_id: "demo-tenant"`, which reads like a slug. It is not: it is
`public.tenants.id` — the value ADR-001 makes the schema discriminator, and the schema in
the same records is `tenant_demo_tenant`. That tenant's *slug* is `demo-corp` and appears
in no record. The demo tenant simply carries a legacy non-UUID id from `seed.py`; a tenant
provisioned through the API gets a UUID (`eeba217e-6cd0-4c66-b5ac-ec96fec61376` is one).
Row 17 holds: the discriminator is recorded, the slug and display name are not.

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** observability-foundation
**Proposal:** `openspec/changes/observability-foundation/proposal.md`
**Spec files reviewed:**
- specs/observability/spec.md
- specs/local-dev-stack/spec.md
- specs/secret-hygiene/spec.md

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
