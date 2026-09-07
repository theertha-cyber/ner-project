## Why

`observability-foundation` gave the platform pipes: correlation across ten processes, structured JSON logs, auto-instrumented spans for HTTP, database, Redis and Celery, and RED metrics. What comes out of those pipes today is generic. It describes a Python microservice — who called whom, how long it took — and knows nothing about what this platform actually does. No signal distinguishes a slow answer caused by retrieval from one caused by the model retrying its SQL three times.

Two consequences.

First, the Phase 1 bet is unmeasured. The execution plan argues that a normalized schema and a retrieved schema slice make text-to-SQL reliable, and that repair loops fall as a result. Nothing counts repair loops. Gate 1 checks this with a question suite run by hand, once — which cannot show whether the loop got shorter in production or stayed the same.

Second, Exit Gate 3 asserts three things nothing builds: an automated telemetry scan in the release pipeline, evidence that no cross-tenant access is occurring, and per-tenant attribution. `guardrails.py:103` fails open when the domain classifier errors and logs a warning nobody aggregates. `dependencies.py:60` raises `TenantMismatchError` — the signal that a token's tenant did not match the requested tenant — and no counter records it.

This change makes the platform's own behaviour observable, and supplies the tenant-safety controls the gate depends on.

## What Changes

**Chat and retrieval path** — span attributes and metrics at each stage: guardrail rule and outcome including the fail-open case; entity-resolution outcome (`unresolved`, `unique`, `ambiguous`, `over_cap`) and mentions checked; catalogue slice size; SQL generation attempts, repair depth, defect category, abandon reason and deadline exhaustion; SQL execution duration, row count and truncation; retrieval hit rate, zero-result rate and rerank latency; LLM tokens in and out, cost, provider latency and error class; answer confidence, citation count and whether the answer was hedged.

**Extraction and projection** — per-run stage reached, duration, retries, partial failures, pages processed, entity counts by type (counts and type names only, never values), model version used, and EAV-to-normalized projection duration and drift detection. Celery queue depth, wait time, task duration, failures by exception class and worker liveness for both queues.

**Model serving** — inference latency distribution, batch and window geometry, model load and cold-start events, active version per tenant as a span attribute, rerank latency, ONNX versus base-model path.

**Training** — job state transitions, duration, failure cause, epoch progress, and the metrics already sent to MLflow mirrored as gauges keyed by job and model version.

**LangSmith correlation** — the OTel trace identifier is attached to LangSmith runs and the LangSmith run identifier to the corresponding span, so prompt-level detail and service-level path are one click apart instead of two disconnected systems.

**Security and tenant-safety counters** — `tenant_mismatch_total` incremented where `TenantMismatchError` is raised; a search-path assertion that the schema matches `^tenant_[0-9A-Za-z_-]{1,56}$` before query execution, with violations counted; authentication failures by reason; rate-limit rejections by tenant.

**Cardinality allowlist** — a single enumerated list of the metric families permitted to carry a `tenant_id` label. `observability-foundation` shipped none deliberately; this change opens a small fixed set for consumption attribution and enforces the boundary with a test, so the list cannot grow by habit.

**Release-gate telemetry scan** — an automated check that exercises a seeded flow against the running stack and fails when captured telemetry contains seeded entity values or matches personal-data patterns. This is the artifact Exit Gate 3 names.

Non-goals: production backends on the cluster (story 4.5), dashboards, alert rules and runbooks (story 5.1), per-tenant quotas or any change to rate-limit policy, log retention policy, Mimir, Pyroscope.

## Capabilities

### New Capabilities

- `workload-telemetry`: what each of the platform's four workloads reports about itself — chat and retrieval, extraction and projection, model serving, and training — plus correlation between OpenTelemetry and LangSmith.
- `telemetry-tenant-safety`: the controls that keep telemetry from becoming a cross-tenant or privacy exposure — security counters, the metric-label cardinality allowlist, and the automated release-gate scan.

### Modified Capabilities

None. The `observability` capability introduced by `observability-foundation` is not yet archived into `openspec/specs/`, and this change adds new concerns rather than altering that capability's requirements. `observability` remains the mechanism — how telemetry is emitted and correlated; the two capabilities here are the platform-specific signal contract and the safety controls over it.

## Impact

**Code — chat path**
- `src/chat_api/services/sql_generator.py` — attempt loop, execution, coverage probe
- `src/chat_api/services/guardrails.py` — block decisions and the fail-open path at line 103
- `src/chat_api/services/entity_resolver.py` — resolution outcomes
- `src/chat_api/services/rag_orchestrator.py`, `src/shared/retrieval/{retriever,reranker,orchestrator}.py` — retrieval and rerank
- `src/chat_api/graph/nodes.py` — planner and per-node spans
- `src/chat_api/services/rate_limiter.py` — rejection counter

**Code — other workloads**
- `src/extraction_service/worker.py`, `services/entity_postprocessor.py`, `services/relational_projection.py`
- `src/model_serving/services/{inference_service,rerank_service}.py`
- `src/training_service/worker.py`
- Both `celery_app.py` modules — queue metrics

**Code — tenant safety**
- `src/gateway/dependencies.py` — `TenantMismatchError` counter
- `src/chat_api/services/sql_execution_role.py`, `src/*/dependencies.py` — search-path assertion
- `src/shared/observability/metrics.py` — allowlist definition and enforcement helper

**Tests**: new domain-metric tests per workload, an allowlist enforcement test, and the release-gate scan wired into CI.

**Dependencies**: none new expected; LangSmith and the OTel SDK are already present.

**Downstream**: story 5.1's dashboards consume every metric defined here. Exit Gate 1's repair-loop claim, and Exit Gate 3's telemetry scan, cross-tenant evidence and per-tenant attribution all depend on this change.

## Open Questions

- Which metric families join the cardinality allowlist. Assumption: chat request count, LLM tokens, LLM cost, extraction jobs, and rate-limit rejections — five, no more, changed only by amending the enumerated list under review.
- Whether the release-gate scan runs against the full local stack in CI or against captured telemetry from a lighter harness. Assumption: full stack, since a lighter harness would not exercise the exporters where a leak could reappear.
- Whether search-path violations should raise or only count. Assumption: count and log at ERROR in this change; converting to a hard failure is a behavioural change to the query path and belongs to its own change.
- Whether MLflow training metrics should be mirrored as Prometheus gauges at all, given MLflow already stores them. Assumption: mirror only job state, duration and failure cause; leave F1, precision and recall in MLflow to avoid two sources of truth for model quality.
- Whether `guardrails.py:103` should keep failing open once it is measured. Assumption: unchanged in this change — measure first, then decide with evidence. Flagged because a silently degrading security control is a risk the counter only reveals, not fixes.
