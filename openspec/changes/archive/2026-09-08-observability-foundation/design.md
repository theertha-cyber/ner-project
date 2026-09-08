## Context

The platform runs as ten independent processes — eight FastAPI services and two Celery workers — against shared Postgres, Redis, MinIO and MLflow. Today:

- `logging.basicConfig` is called in `src/chat_api/main.py` and `src/model_serving/main.py` only. The other eight processes leave the root logger at WARNING with no handler, so every `logger.info` they emit is discarded before reaching stdout.
- Eight near-identical `src/*/middleware/tenant_context.py` files each generate their own `X-Request-ID` and set it on the response. None forwards it on an outbound call, so an identifier does not survive a single hop.
- No process exposes metrics, and no process emits traces. Diagnosis requires knowing which service to open first.
- `src/chat_api/services/sql_generator.py:1619` logs generated SQL at INFO. That SQL carries literal filter values drawn from extracted resume data — tenant personal data, in an application log, today.

Constraints shaping the design:

- Schema-per-tenant isolation is the platform's security model, and telemetry is a new central collection point that must not become the place it leaks.
- The production cluster does not exist yet; the change that stands it up (story 4.5) is blocked on an external cloud approval. This change must be independently verifiable without it.
- Sprint capacity is one developer, and spec review — not build effort — is the stated bottleneck.

## Goals / Non-Goals

**Goals:**

- One shared instrumentation module, imported by all ten processes, replacing per-service logging and correlation code.
- A correlation identifier that survives HTTP hops and Celery enqueues.
- Structured JSON logs carrying tenant, user-hash, request and trace context automatically.
- Redaction enforced at the logging layer, not by call-site discipline, with the existing `sql_generator` leak closed.
- Traces and RED metrics via auto-instrumentation, with no per-route code.
- A local collector and Grafana so every acceptance criterion is verifiable on a laptop.

**Non-Goals:**

- Workload-specific span fields (`repair_depth`, `defect`, guardrail rules, confidence, retrieval hit rate, token counts) and security counters — `observability-workload-instrumentation`.
- Production backends on the cluster — story 4.5.
- Dashboards, alert rules, per-tenant consumption attribution — story 5.1.
- Mimir, Pyroscope, log-retention policy, per-tenant quotas or rate-limit policy changes.
- Replacing LangSmith or MLflow. Both stay; linking their traces to OTel is the next change's work.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Schema-per-tenant `tenant_<uuid>`, prefix-isolated object storage; isolation explicitly covers logs and search indexes | Telemetry is a shared store and must not become a cross-tenant read path. Tenant identity in telemetry stays the UUID already used as the schema discriminator; no new tenant identifier is introduced. |
| ADR-003 Per-Tenant Model Serving Topology | Version-pinned, isolated per-tenant serving | Span and metric names must not assume a single shared model instance. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every change traceable from intent to evidence | This design exists because the change is cross-cutting; acceptance criteria map to executable checks in `verification.md`. |
| ADR-005 OpenCode Agent Permissions and Boundaries | Bounded agent roles | No constraint on this design beyond normal review. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation enforcement, P95 < 10s, "response latency MUST be monitored (P95 alert at >10s)" | The P95 latency obligation is currently unmet — nothing measures it. This change supplies the request-duration histogram that makes it measurable; the alert itself belongs to story 5.1. |

ADR-002 and ADR-006 are partially superseded by ADR-008, ADR-009 and ADR-010 respectively; none of the superseded or superseding clauses bear on this design.

## Decisions

### Decision 1: OpenTelemetry as the sole instrumentation boundary

**Choice:** Application code emits OTel spans, metrics and log correlation. Backends are selected by exporter configuration, not by code.

**Rationale:** The production backend decision is blocked behind story 4.5's cloud approval and may change again at the SaaS migration. Committing to a vendor-neutral instrumentation layer makes that a change of exporter rather than a re-instrumentation. It is also the platform's stated stack choice in the execution plan.

**Alternatives considered:**
- Direct Prometheus client plus a logging library, no tracing — ruled out because tracing is the signal that solves the ten-process problem, and retrofitting it later means touching every service twice.
- Vendor SDK (Datadog, New Relic) — ruled out on lock-in and because telemetry containing tenant data leaving the network is an unresolved question at the cloud move.

### Decision 2: One shared module, not per-service instrumentation

**Choice:** `src/shared/observability/` with `init_observability(service_name)`; each service adds one call.

**Rationale:** The repository already demonstrates the failure mode of the alternative. Eight copies of `tenant_context.py` each generate a request identifier, and because they were written independently, none forwards it. Correlation is a property of the whole system, so it must have exactly one implementation.

**Alternatives considered:**
- Per-service instrumentation following a documented convention — ruled out; a convention is what produced the eight divergent copies.
- A separate installable package — ruled out as premature for a single repository.

### Decision 3: Context carried in `contextvars`, not function arguments

**Choice:** `request_id`, `tenant_id`, `user_hash` and `trace_id` are stored in `contextvars` set by middleware, read by the log formatter and span processor.

**Rationale:** Threading context through every call signature would touch hundreds of functions and be silently forgotten in new code. `contextvars` is asyncio-safe and propagates into tasks spawned from the request. The existing `request.state` mechanism works only where a `Request` object is in scope, which excludes service-layer and worker code.

**Alternatives considered:**
- Keep using `request.state` — ruled out; unavailable in Celery workers and in service-layer functions, which is exactly where the interesting logs are.
- Thread-locals — ruled out; incorrect under asyncio.

### Decision 4: Redaction as a mandatory logging filter, backed by a test

**Choice:** A `logging.Filter` installed by `init_observability` strips a denylist of sensitive keys and is not optional or bypassable by call sites. A test asserts prohibited content cannot reach a record.

**Rationale:** ADR-001 extends tenant isolation to logs, and Exit Gate 3 requires an automated scan rather than review. A filter that call sites must remember to use will be forgotten; the `sql_generator` line is proof that it already was. Making the filter unconditional means a future `logger.info(f"...{sql}")` is contained by default.

**Alternatives considered:**
- Documented convention plus code review — ruled out; the current leak passed review.
- Redaction only at the collector — ruled out as the sole control, because sensitive data would still exist in container stdout and in `docker logs`. Collector-side allowlisting is a second layer and belongs to the production-stack change.

Note that a denylist filter contains structured fields reliably and interpolated message strings only partially. The `sql_attempt` line is therefore rewritten to pass structured fields rather than an interpolated string, and the same pattern applies to any future call site handling sensitive values.

### Decision 5: Users identified by a keyed hash, tenants by UUID

**Choice:** `user_hash = HMAC-SHA256(user_id, pepper)[:16]`, pepper from the environment with no default. Tenants appear as the UUID already used for schema naming.

**Rationale:** Support needs to follow one person's session through a trace; nobody needs to read who that person is from a log store. A keyed hash gives correlation without identity. An unkeyed hash would be trivially reversible over a small user set. Tenant UUIDs are already the discriminator under ADR-001, so reusing them adds no new identifier and no new mapping to protect.

**Alternatives considered:**
- Raw `user_id` — ruled out; it is a direct identifier in a store with broader read access than the database.
- Omitting user identity entirely — ruled out; "which user hit this" is a first-order support question.

### Decision 6: No `tenant_id` metric label in this change

**Choice:** `tenant_id` goes on spans and log records. No metric introduced here carries it as a label.

**Rationale:** Prometheus label cardinality multiplies by tenant count, and metric labels are visible to everyone with dashboard access, which makes per-tenant consumption figures commercially sensitive. The four consumption metric families that legitimately need the label arrive with the workload-instrumentation change, where the allowlist governing them is also defined. Starting with none and adding deliberately is easier than removing labels later.

**Alternatives considered:**
- Label everything by tenant now — ruled out on cardinality and on disclosure.

### Decision 7: Local collector and Grafana in `docker-compose.yml`

**Choice:** Add `otel-collector` and `grafana` to the local stack as part of this change.

**Rationale:** Four acceptance criteria — trace spans two services, trace extends into a worker, logs join traces, collector-down does not break requests — are not verifiable without somewhere for telemetry to land. Including the local stack also decouples this change entirely from story 4.3's cloud approval, which is the tracker's only external blocker.

**Alternatives considered:**
- Wait for the production backends — ruled out; it makes unblocked work depend on a blocked approval.
- Assert only on captured log records and in-memory span exporters — ruled out as insufficient for the cross-process criteria, though in-memory exporters are still used for the fast unit-level checks.

### Decision 8: Correlation identifier accepted at the edge but never trusted

**Choice:** An inbound `X-Request-ID` is adopted for correlation. It is never read as tenant, user or authorization input.

**Rationale:** Accepting a caller-supplied identifier makes support workflows possible. Treating it as anything but an opaque correlation value would introduce a client-controlled input into a security decision, which ADR-001's model forbids.

**Alternatives considered:**
- Always regenerate at the gateway — ruled out; loses the ability to correlate with a caller's own logs.
- Validate it as a UUID and reject otherwise — deferred; length-capped and sanitized on write is sufficient, and rejection would break callers for no security gain.

## Risks / Trade-offs

- [Log format changes from plain text to JSON, and anyone reading `docker logs` directly loses readability] → Console rendering stays human-readable in local development via an environment-selected formatter; JSON is the default everywhere else.
- [Auto-instrumentation adds per-request overhead across ten services] → Measure request latency before and after on the local stack; sampling is configurable, and the span exporter is asynchronous so export never blocks the request path.
- [Removing the request-ID block from eight `tenant_context.py` files risks disturbing tenant enforcement, which is the platform's core security property] → Tenant resolution, token decoding and authorization stay in the per-service middleware and are not moved. The existing tenant-isolation suite is re-run as a gate on this change.
- [A denylist redaction filter cannot catch a sensitive value interpolated into an arbitrary message string] → Structured-field logging is the required pattern for anything touching sensitive values; the collector-side allowlist in the production-stack change is the second layer; the release-gate scan in the workload change is the third.
- [The pepper has no rotation story, so rotating it breaks historical user correlation] → Accepted deliberately. Rotation is a privacy feature, not a defect, and correlation windows are shorter than log retention.
- [Ten processes changed at once is a wide blast radius for one change] → The module is additive and the per-service edit is a single call; services are converted and verified incrementally within the change, and the middleware consolidation is the only subtractive step.
- [Telemetry export failures could surface as request failures] → Explicitly specified otherwise: export failure must not raise into the request path, and is verified by a scenario with the collector stopped.

## Migration Plan

1. Add dependencies and the `src/shared/observability/` module with no call sites. No behavioural change.
2. Add `otel-collector` and `grafana` to `docker-compose.yml`, and the OTLP endpoint plus pepper settings to `src/shared/config.py`.
3. Convert services one at a time: add `init_observability()`, mount the shared middleware, remove that service's duplicated request-ID block. Run the tenant-isolation suite after each.
4. Forward the correlation header on outbound service-to-service calls; add the Celery header hook on both workers.
5. Rewrite the `sql_attempt` log line to structured fields and enable the redaction filter with its test.
6. Add `/metrics` to the eight FastAPI services and OTLP metric export on the two workers.

**Rollback:** Steps 1, 2 and 6 are additive and revert cleanly. Step 3 is the only one that removes existing code; it is per-service, so a revert of a single service's commit restores its previous middleware. Setting the OTLP endpoint to empty disables export without a code change, which is the fast mitigation if telemetry overhead or export failure causes a production problem.

## Open Questions

- Trace sampling rate. Assumption: sample everything locally; the production rate is chosen with the backends in story 4.5, since it is a cost decision against retention.
- Whether the two Celery workers should expose `/metrics` over a side HTTP port instead of pushing over OTLP. Assumption: push, since neither worker runs an HTTP server and adding one widens their attack surface for no operational gain.
- Whether `X-Request-ID` should be length-capped and character-restricted on ingest. Assumption: yes, capped and sanitized before it reaches a log field, to prevent log injection via a caller-supplied value. Flagged for review because it is a security decision rather than a convenience one.
- No in-force ADR needs revisiting for this change. ADR-007's unmet P95 monitoring obligation is satisfied progressively — the histogram here, the alert in story 5.1 — and does not require a superseding ADR.
