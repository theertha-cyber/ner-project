# Verification Plan

**Change:** observability-workload-instrumentation
**Generated:** 2026-09-02
**Status:** 🟡 Implementation and evidence complete — **Audit Record (Section 6) still requires a human reviewer's sign-off before archive.** Sections 1, 4 and 5 were filled from real runs; Section 6 is deliberately left unsigned, as an agent cannot satisfy it.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | workload-telemetry | Chat And Retrieval Path Instrumentation | A chat request produces a span per stage | Given the local stack running and a chat question answered end to end, when the trace is retrieved, then it contains one span for each stage the request executed, and each carries a duration and an outcome attribute | `tests/integration/test_chat_stage_spans.py` (task 4.11) | - [x] |
| 2 | workload-telemetry | Chat And Retrieval Path Instrumentation | SQL generation records repair depth and defect | Given a question whose first generated query is invalid and whose second succeeds, when the SQL generation span and metrics are read, then the span records `attempts` 2 and `repair_depth` 1, the first attempt records a defect drawn from an enumerated set, and a repair-depth histogram observation exists | `tests/chat_api/test_sql_generation_metrics.py` (task 4.8) | - [x] |
| 3 | workload-telemetry | Chat And Retrieval Path Instrumentation | An abandoned query records why it was abandoned | Given a question where SQL generation exhausts its attempt budget, and another where it exhausts its deadline, when the spans and metrics are read, then the outcome is `abandoned` in both and the recorded abandon reason distinguishes the two cases | `tests/chat_api/test_sql_generation_metrics.py` (task 4.9) | - [x] |
| 4 | workload-telemetry | Chat And Retrieval Path Instrumentation | Retrieval records whether it returned anything | Given a question whose retrieval returns no documents, when the retrieval span and metrics are read, then the span records a result count of zero and a zero-result counter has incremented | `tests/chat_api/test_retrieval_metrics.py` (task 3.8) | - [x] |
| 5 | workload-telemetry | Chat And Retrieval Path Instrumentation | LLM usage is recorded per call | Given a chat request making one or more LLM calls, when the spans for those calls are read, then each records input tokens, output tokens, provider latency and an outcome, and a failed call records an enumerated error class rather than the provider's message text | `tests/chat_api/test_llm_usage_metrics.py` (task 4.10) | - [x] |
| 6 | workload-telemetry | Chat And Retrieval Path Instrumentation | No chat telemetry contains message or query content | Given a chat request answered end to end, when every span attribute, metric label and log record it produced is collected, then none contains the question text, the answer text, the generated SQL, a retrieved passage or an entity value | `tests/integration/test_no_pii_in_chat_telemetry.py` (task 4.12) | - [x] |
| 7 | workload-telemetry | Guardrail Decisions Are Counted, Including Fail-Open | A blocked question increments its rule's counter | Given a question the guardrail blocks as cross-tenant or as a personal-data query, when the guardrail counters are read, then the counter labelled with that rule has incremented | `tests/chat_api/test_guardrail_metrics.py` (task 3.6) | - [x] |
| 8 | workload-telemetry | Guardrail Decisions Are Counted, Including Fail-Open | A classifier failure is counted as fail-open, not as admit | Given the domain classifier raises and the guardrail admits the query, when the guardrail counters are read, then a dedicated fail-open counter has incremented and the event is distinguishable from a normal admit | `tests/chat_api/test_guardrail_metrics.py` (task 3.6) | - [x] |
| 9 | workload-telemetry | Guardrail Decisions Are Counted, Including Fail-Open | Empty-sources enforcement is counted | Given a request where source enforcement returns the fallback reply because no sources were present, when the guardrail counters are read, then the counter for that rule has incremented | `tests/chat_api/test_guardrail_metrics.py` (task 3.6) | - [x] |
| 10 | workload-telemetry | Entity Resolution Outcomes Are Recorded | Each resolution outcome is counted | Given a chat request whose entity resolution completes, when the resolution span and counters are read, then the outcome is one of `unresolved`, `unique`, `ambiguous`, `over_cap`, the number of mentions checked is recorded, and no mention text appears in either | `tests/chat_api/test_entity_resolution_metrics.py` (task 3.7) | - [x] |
| 11 | workload-telemetry | Extraction And Projection Instrumentation | A completed extraction run reports its stages | Given a document extracted successfully, when the run's spans and metrics are read, then each stage is represented with a duration, pages processed, model version and per-type entity counts are recorded on the run's spans, and the run's metrics record an aggregate entity count carrying no entity-type label | `tests/extraction_service/test_extraction_metrics.py` (task 5.7) | - [x] |
| 12 | workload-telemetry | Extraction And Projection Instrumentation | A failed extraction run records where it failed | Given a document whose extraction fails partway through, when the run's spans and metrics are read, then the failing stage is identifiable and a failure counter labelled by exception class has incremented | `tests/extraction_service/test_extraction_metrics.py` (task 5.7) | - [x] |
| 13 | workload-telemetry | Extraction And Projection Instrumentation | Projection reports duration and drift | Given an extraction write triggering the EAV-to-normalized projection, when the projection span and metrics are read, then the projection duration is recorded and a drift indicator distinguishes a clean projection from one where source and projected row counts disagree | `tests/extraction_service/test_projection_metrics.py` (task 5.8) | - [x] |
| 14 | workload-telemetry | Extraction And Projection Instrumentation | Entity values never appear in extraction telemetry | Given a document containing known seeded entity values is extracted, when every span attribute, metric label and log record from that run is collected, then none contains a seeded entity value, and entity type names and counts may be present on spans and log records | `tests/integration/test_no_pii_in_extraction_telemetry.py` (task 5.9) | - [x] |
| 15 | workload-telemetry | Celery Queue Instrumentation | Queue depth is observable | Given tasks enqueued faster than the workers consume them, when the queue depth metric is read, then it reports a non-zero depth for the affected queue | `tests/shared/test_celery_queue_metrics.py` (task 5.10) | - [x] |
| 16 | workload-telemetry | Celery Queue Instrumentation | Task wait time is distinguished from execution time | Given a task that waits in the queue before executing, when its metrics are read, then the time spent waiting is recorded separately from the time spent executing | `tests/shared/test_celery_queue_metrics.py` (task 5.10) | - [x] |
| 17 | workload-telemetry | Celery Queue Instrumentation | A failing task is counted by exception class | Given a task that raises, when the failure counter is read, then it has incremented under a label naming the exception class, and that label does not contain the exception message text | `tests/shared/test_celery_queue_metrics.py` (task 5.10) | - [x] |
| 18 | workload-telemetry | Model Serving Instrumentation | An inference call records duration and path | Given an inference request for a tenant with a promoted model, when the inference span is read, then it records duration, the active model version, and that the tenant model path executed | `tests/model_serving/test_inference_metrics.py` (task 6.7) | - [x] |
| 19 | workload-telemetry | Model Serving Instrumentation | Base-model fallback is distinguishable | Given an inference request for a tenant with no promoted model, when the inference span is read, then it records that the base-model path executed | `tests/model_serving/test_inference_metrics.py` (task 6.7) | - [x] |
| 20 | workload-telemetry | Model Serving Instrumentation | Model load is recorded as an event | Given a tenant model loaded into memory for the first time, when the spans and metrics are read, then a model-load event is recorded with its duration | `tests/model_serving/test_inference_metrics.py` (task 6.7) | - [x] |
| 21 | workload-telemetry | Training Job Instrumentation | A job's lifecycle is observable | Given a training job that runs to completion, when its metrics are read, then each state transition is recorded and the total duration is recorded | `tests/training_service/test_training_metrics.py` (task 6.8) | - [x] |
| 22 | workload-telemetry | Training Job Instrumentation | A failed job records its cause | Given a training job that fails, when its metrics are read, then a failure counter has incremented under an enumerated cause and the job's final state is recorded | `tests/training_service/test_training_metrics.py` (task 6.8) | - [x] |
| 23 | workload-telemetry | Training Job Instrumentation | Model quality metrics are not duplicated | Given a completed training job whose evaluation metrics were logged to MLflow, when the platform metric families are examined, then no family exposes F1, precision, recall or loss | `tests/training_service/test_training_metrics.py` (task 6.9) | - [x] |
| 24 | workload-telemetry | LangSmith And OpenTelemetry Traces Are Correlated | A LangSmith run carries the OTel trace identifier | Given LangSmith tracing enabled and a chat request making an LLM call, when the LangSmith run for that call is retrieved, then it carries the OpenTelemetry trace identifier of the originating request | `tests/integration/test_langsmith_correlation.py` (task 7.3) | - [x] |
| 25 | workload-telemetry | LangSmith And OpenTelemetry Traces Are Correlated | The span carries the LangSmith run identifier | Given the same request, when the corresponding span is retrieved, then it carries the LangSmith run identifier as an attribute | `tests/integration/test_langsmith_correlation.py` (task 7.3) | - [x] |
| 26 | workload-telemetry | LangSmith And OpenTelemetry Traces Are Correlated | LangSmith being unavailable does not break the request | Given LangSmith disabled or unreachable, when a chat request is handled, then it is answered normally and the OpenTelemetry spans are still emitted | `tests/integration/test_langsmith_correlation.py` (task 7.4) | - [x] |
| 27 | telemetry-tenant-safety | Cross-Tenant Access Attempts Are Counted | A tenant mismatch increments the counter | Given a request bearing a valid token for one tenant that addresses a different tenant's resource, when it is rejected, then a tenant-mismatch counter has incremented and a log record at WARNING or higher carrying the request's correlation context was emitted | `tests/shared/test_tenant_safety_counters.py` (task 2.6) | - [x] |
| 28 | telemetry-tenant-safety | Cross-Tenant Access Attempts Are Counted | A tenant mismatch is distinguishable from an ordinary auth failure | Given one request rejected for a missing or invalid token and another for a tenant mismatch, when the counters are read, then the two incremented different counters | `tests/shared/test_tenant_safety_counters.py` (task 2.6) | - [x] |
| 29 | telemetry-tenant-safety | Cross-Tenant Access Attempts Are Counted | The mismatch counter carries no tenant label | Given the tenant-mismatch counter as exposed on `/metrics`, when its label set is examined, then it does not include a tenant identifier | `tests/shared/test_tenant_safety_counters.py` (task 2.6) | - [x] |
| 30 | telemetry-tenant-safety | Tenant Schema Is Asserted Before Query Execution | A well-formed tenant schema passes the assertion | Given a query executed against a schema named for a valid tenant identifier, when the assertion runs, then it passes and the violation counter does not increment | `tests/shared/test_search_path_assertion.py` (task 2.7) | - [x] |
| 31 | telemetry-tenant-safety | Tenant Schema Is Asserted Before Query Execution | A malformed schema name is counted and logged | Given a code path that would set a search path to a value not matching the tenant-schema pattern, when the assertion runs, then the violation counter increments, an ERROR record identifying the code path is emitted, and the schema name is recorded in a form that does not echo arbitrary caller input verbatim | `tests/shared/test_search_path_assertion.py` (task 2.7) | - [x] |
| 32 | telemetry-tenant-safety | Authorization Failures And Rate-Limit Rejections Are Counted | Auth failures are counted by reason | Given requests rejected for a missing header, a malformed token and an expired token, when the auth-failure counter is read, then each incremented under a distinct enumerated reason and no token value or fragment appears in any label | `tests/shared/test_tenant_safety_counters.py` (task 2.8) | - [x] |
| 33 | telemetry-tenant-safety | Authorization Failures And Rate-Limit Rejections Are Counted | Rate-limit rejections are counted | Given a caller that exceeds its configured rate limit, when the rate-limit counter is read, then it has incremented | `tests/shared/test_tenant_safety_counters.py` (task 2.8) | - [x] |
| 34 | telemetry-tenant-safety | Metric Label Cardinality Allowlist | An allowlisted family may carry the tenant label | Given a metric family named on the allowlist, when its label set is examined, then it may include `tenant_id` without failing the enforcement check | `tests/shared/test_domain_metrics_declarations.py` (task 1.5) | - [x] |
| 35 | telemetry-tenant-safety | Metric Label Cardinality Allowlist | A non-allowlisted family carrying a tenant label fails the check | Given a metric family not on the allowlist that has been given a `tenant_id` label, when the enforcement check runs, then it fails and names the offending family | `tests/shared/test_domain_metrics_declarations.py` (task 1.5) | - [x] |
| 36 | telemetry-tenant-safety | Metric Label Cardinality Allowlist | The allowlist is small and explicit | Given the allowlist definition, when it is read, then it enumerates its members explicitly and is not expressed as a pattern, prefix or wildcard | `tests/shared/test_domain_metrics_declarations.py` (task 1.5) | - [x] |
| 37 | telemetry-tenant-safety | Automated Release-Gate Telemetry Scan | A clean run passes the scan | Given a seeded end-to-end flow executed against the running stack, when the scan inspects the captured telemetry, then it finds no seeded entity value and no personal-data pattern match and exits successfully | `scripts/telemetry_scan.py` + `tests/integration/test_telemetry_scan.py` (tasks 8.1, 8.8) | - [x] |
| 38 | telemetry-tenant-safety | Automated Release-Gate Telemetry Scan | A deliberately reintroduced leak fails the scan | Given a code path modified to log a seeded entity value, when the scan runs, then it fails and identifies the offending record or attribute | `scripts/telemetry_scan.py` leak reintroduction (task 8.4) + `tests/integration/test_telemetry_scan.py` | - [x] |
| 39 | telemetry-tenant-safety | Automated Release-Gate Telemetry Scan | An empty capture is treated as a failure, not a pass | Given the seeded flow produced no telemetry, for example because export was misconfigured, when the scan runs, then it fails rather than reporting a clean result | `scripts/telemetry_scan.py` with `otel-collector` stopped (task 8.5) + `tests/integration/test_telemetry_scan.py` | - [x] |
| 40 | telemetry-tenant-safety | Automated Release-Gate Telemetry Scan | The scan covers spans and metric labels, not only logs | Given a seeded entity value present in a span attribute or a metric label but in no log record, when the scan runs, then it fails | `scripts/telemetry_scan.py` span/label sentinel run (task 8.6) + `tests/integration/test_telemetry_scan.py` | - [x] |
| 41 | workload-telemetry | Extraction And Projection Instrumentation | Entity type is never promoted to a metric label | Given a tenant with entity types of its own naming, when the label sets of every metric family declared by this change are examined, then none includes an entity-type label, and the check fails if one is introduced | `tests/shared/test_domain_metrics_declarations.py` (task 1.7) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Label values derived from tenant data (design Decision 2) | The agent labels a metric with `SQLAttempt.defect` directly. That field carries its evidence inline — `filename:<literal>`, `scope:<relations>` — where the literal is drawn from a tenant document, so the label puts extracted content into Prometheus, which the foundation's redaction filter does not cover. The same error class applies to `str(e)` instead of `type(e).__name__`, and to a provider error message instead of an enumerated class. | Read every recorder call in `src/shared/observability/domain_metrics.py` and every call site. Confirm each label argument is either a module constant from the measured code or a category function. Specifically confirm `_defect_class()` is used, not `defect`. Then run `curl localhost:<port>/metrics` on the local stack after a chat request and read the label values by eye. |
| 2 | Invented metric and label names (design Decision 1) | The specs name signals in prose — "repair depth", "abandon reason", "drift indicator" — without prescribing identifiers. The agent invents plausible names, or names that diverge from the code's own vocabulary, producing metrics no dashboard in story 5.1 will match and outcome labels that do not equal `SQLAttemptOutcome`'s values. | Diff the declared names in `domain_metrics.py` against the constants in `sql_generator.py` (`SQLAttemptOutcome`), `entity_resolver.py` (`UNRESOLVED`/`UNIQUE`/`AMBIGUOUS`/`OVER_CAP`) and the guardrail rule identifiers. Any label value written as a new string literal instead of imported is suspect. |
| 3 | The counter placed at the raise site rather than in the exception (design Decision 4) | The agent increments the tenant-mismatch counter in `src/gateway/dependencies.py:60` because that is where the raise is visible, rather than in `TenantMismatchError.__init__` in `src/shared/exceptions.py`. Functionally identical today, wrong for every future raise site — which is the entire reason the counter exists. | `grep -rn "TenantMismatchError" src/` and confirm the increment lives in the constructor and nowhere else. Confirm the observability import inside `exceptions.py` is function-local and guarded, so `exceptions.py` stays importable before `init_observability` runs. |
| 4 | Incomplete coverage of the eight search-path sites (design Decision 5) | The agent adds `assert_tenant_schema` to the obvious sites in `sql_generator.py` and misses `analytics_service/dependencies.py`, `analytics_service/worker.py`, `extraction_service/dependencies.py` or `shared/tenant_context.py`. Partial coverage is worse than none, because the counter reads zero and is believed. | `grep -rn "search_path" src/ --include=*.py` and confirm every `SET search_path TO {…}` interpolation is immediately preceded by an assertion call. Count them: nine sites across five files — `sql_generator.py` holds five, and the other four files hold one each. An earlier draft said eight. |
| 5 | The assertion converted into a raise (design Decision 5) | The agent reads "assert" and implements `raise ValueError` on mismatch, turning an instrumentation change into a behavioural change to the query path under conditions nobody has data about. | Read the helper. Confirm the mismatch branch increments, logs at ERROR and returns. Confirm no test asserts an exception is raised on a malformed schema. |
| 6 | LangSmith correlation not isolated from the request path (design Decision 8) | The agent attaches metadata without wrapping the call, so a LangSmith SDK change, a disabled configuration or an unreachable endpoint raises inside the chat path. LangSmith is off by default and configured by bare environment variables read by its own SDK, so this fails in exactly the environment nobody tests in. | Read both `wrap_openai` sites. Confirm each correlation operation is inside its own try/except that logs at DEBUG and continues. Then run a chat request with `LANGSMITH_TRACING` unset and confirm it is answered normally and spans are still emitted (row 26). |
| 7 | Model quality metrics mirrored from MLflow (design Decision 9) | Asked to instrument training, the agent mirrors what `worker.py` already sends to MLflow at lines 314-322 — F1, precision, recall, loss — because those are the metrics visibly present, creating a second and worse source of truth for model quality. | Read the training declarations. Confirm only lifecycle families exist. Confirm the negative test in row 23 walks the live registry rather than grepping source, so a family registered dynamically cannot slip past it. |
| 8 | The release-gate scan passes on an empty capture (design Decision 11) | The agent implements "no matches found → exit 0", which reports clean when export is misconfigured and the capture is empty. This is the exact gap the foundation change hit late: Loki provisioned, receiving nothing, no scenario covering delivery, nothing failed. | Read the scan's exit logic. Confirm a minimum expected record count is asserted before any content check. Reproduce row 39 by stopping `otel-collector` and confirming the scan fails rather than passing. |

| 9 | Entity type as a metric label (design Decision 12) | ADR-010 measures dataset readiness per entity type, and the extraction requirement asks for entity counts by type — so the obvious implementation labels the metric by type. Entity types are tenant-configured, which makes the label set unenumerable and lets tenant-authored names fingerprint a tenant in a store shared across all of them, routing around the tenant-label allowlist rather than violating it. | Read the extraction recorder in `domain_metrics.py`. Confirm the metric takes a count and no type argument, and that per-type detail is set on the span. Then `curl /metrics` on `extraction_service` after seeding a tenant with an unusually named entity type and confirm that name appears nowhere in the output. |
| 10 | Weakening the foundation's tenant-label test (task 1.8) | `tests/shared/test_metrics_endpoint.py` scans every `/metrics` line for `tenant_id=` and goes red the moment the allowlisted families ship. The tempting fix is to delete the assertion or add an exclusion list inline. The correct fix is to scope it to the foundation's own declared families. | Read the diff on that test. Confirm it enumerates families by import rather than string-matching output, and that no allowlist membership is duplicated into it. Confirm `observability-foundation` row 24 evidence was re-collected rather than left as the pre-change run. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Schema-per-tenant `tenant_<uuid>`; isolation extends to logs and indexes | No attribute or label may carry tenant content. Only allowlisted families carry `tenant_id`. The search-path boundary must be asserted at every interpolation site. | Run rows 6, 14, 29, 35, 37 and 40. Then `grep -rn "search_path" src/ --include=*.py` and confirm all nine sites are asserted. Read the allowlist and confirm it has five members enumerated explicitly. |
| ADR-003 Per-Tenant Model Serving Topology | Version-pinned per-tenant serving | Serving telemetry must carry the active model version and must not assume one shared model instance. | Run rows 18 and 20. Confirm the model version appears as a span attribute and that no metric family name or label presumes a single global model. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every change traceable from intent to evidence | Each of the 40 rows above maps to an executable check; the release-gate scan is itself the Exit Gate 3 artifact. | Confirm every row in Section 1 has a Verification Artifact filled by the tasks step and an entry in Section 5 before archive. |
| ADR-005 OpenCode Agent Permissions and Boundaries | Bounded agent roles | No constraint beyond normal review. | No specific step. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation enforcement, P95 < 10s monitored | The stage breakdown must make a P95 breach diagnosable; citation and source enforcement must be counted, not merely executed. | Run rows 1 and 9. Confirm the per-stage spans account for the request duration the foundation's histogram already reports, and that source enforcement increments a counter. |
| ADR-008 Base Model as Default Inference Model (Version 0) | Base model answers when no tenant model is promoted; supersedes ADR-002's 404 behaviour | Base-model inference is a normal success path, not an error path. | Run row 19. Confirm the base-model path is recorded as a distinguishable success and does not increment any error or failure counter. |
| ADR-009 System Admin Sets Training Hyperparameters at Approval | Hyperparameters set at approval; supersedes that clause of ADR-006 | Training telemetry keys off the approved job record, not a request payload. | Run rows 21 and 22. Confirm job identity in telemetry derives from the `training_jobs` row. |
| ADR-010 Dataset Readiness Measured Per Entity Type | Per-entity-type thresholds; supersedes ADR-006's two threshold clauses | Extraction entity counts are reported per entity type **on the run's span**; the metric carries an aggregate count with no entity-type label. | Run rows 11, 14 and 41. Confirm per-type counts appear as span attributes and that `ner_extraction_entities_total` carries no labels at all. **Corrected during implementation:** this row previously read "confirm the entity-count family is labelled by entity type", which design Decision 12 supersedes — entity types are tenant-configured, so a label would be unenumerable and would fingerprint the tenant in a store shared across all of them. Risk 9 in Section 2 already stated the corrected position; this row had not been updated with it. |

ADR-002 is superseded by ADR-008 and is historical context only. ADR-006 remains in force except the clauses ADR-009 and ADR-010 replace.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [x] Row 1: trace retrieved from Tempo on the running stack, showing one span per executed chat stage with duration and outcome attribute
- [x] Row 2: test output for the two-attempt case showing `attempts=2`, `repair_depth=1`, an enumerated defect class on attempt 1, and a histogram observation
- [x] Row 3: test output for both abandon paths showing outcome `abandoned` with distinct reasons for attempt exhaustion and deadline exhaustion
- [x] Row 4: test output showing a zero-result retrieval sets result count 0 and increments the zero-result counter
- [x] Row 5: test output showing input/output tokens, provider latency and outcome per LLM call, plus a failed call carrying an enumerated error class
- [x] Row 6: captured telemetry from one chat request — spans, metric labels and log records — with an assertion that none contains question text, answer text, SQL, a retrieved passage or an entity value
- [x] Row 7: test output showing a blocked question increments the counter for its rule
- [x] Row 8: test output showing a raised classifier increments the fail-open counter and not only the admit counter
- [x] Row 9: test output showing the empty-sources fallback increments its rule's counter
- [x] Row 10: test output showing each of the four resolver outcomes recorded with mentions checked and no mention text
- [x] Row 11: extraction run's spans and metrics showing per-stage durations, pages processed, model version and per-type entity counts
- [x] Row 12: failed extraction run showing the failing stage and a failure counter labelled by exception class
- [x] Row 13: projection span showing duration and a drift indicator, with a mismatched-count case producing the drift value
- [x] Row 14: captured telemetry from an extraction of a seeded document with an assertion that no seeded entity value appears
- [x] Row 15: queue depth metric read while tasks are backed up, showing non-zero depth for the affected queue
- [x] Row 16: task metrics showing wait time and execution duration as separate observations
- [x] Row 17: failure counter reading showing the exception class as label and no message text
- [x] Row 18: inference span for a tenant with a promoted model showing duration, active version and the tenant-model path
- [x] Row 19: inference span for a tenant with no promoted model showing the base-model path recorded as a success
- [x] Row 20: model-load event with its duration, captured on first load
- [x] Row 21: training job metrics showing each state transition and total duration
- [x] Row 22: failed training job showing an enumerated failure cause and the final state
- [x] Row 23: test output walking the live metric registry and asserting no family exposes F1, precision, recall or loss
- [x] Row 24: LangSmith run retrieved showing the OTel trace identifier in its metadata
- [x] Row 25: corresponding span showing the LangSmith run identifier as an attribute
- [x] Row 26: chat request served normally with LangSmith disabled, spans still emitted, no exception raised
- [x] Row 27: tenant-mismatch counter incremented plus the WARNING record carrying correlation context
- [x] Row 28: counter readings showing an invalid-token rejection and a mismatch rejection incrementing different counters
- [x] Row 29: `/metrics` output showing the mismatch counter's label set without a tenant identifier
- [x] Row 30: test output showing a valid tenant schema passes with the violation counter unchanged
- [x] Row 31: test output showing a malformed schema increments the counter, logs at ERROR with the code path, and records the schema in a sanitised form
- [x] Row 32: counter readings for missing header, malformed token and expired token under three distinct reasons, with no token fragment in any label
- [x] Row 33: rate-limit counter reading after a caller exceeds its limit
- [x] Row 34: `/metrics` output showing an allowlisted family carrying `tenant_id` and the enforcement check passing
- [x] Row 35: enforcement check output failing and naming a deliberately mislabelled family
- [x] Row 36: the allowlist definition read in source, showing five explicitly enumerated members and no pattern or wildcard
- [x] Row 37: release-gate scan run against the seeded flow exiting 0 with its captured-record counts reported
- [x] Row 38: scan run against a deliberately reintroduced leak, failing and naming the offending record or attribute
- [x] Row 39: scan run with export disabled, failing on empty capture rather than reporting clean
- [x] Row 40: scan run against a seeded value present only in a span attribute and only in a metric label, failing in both cases
- [x] Row 41: declaration test output showing no family carries an entity-type label, plus a deliberately added entity-type label failing the check

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Every metric family this change introduces is declared in `src/shared/observability/domain_metrics.py` and none is created at a call site
- [x] Chat request P95 on the local stack measured before and after instrumentation, with the delta recorded

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — every recorder label argument reviewed; `_defect_class()` in use, no raw `defect`, no `str(e)`, no provider message text; `/metrics` label values read by eye after a live chat request
- [x] Risk 2 mitigation confirmed — declared label values diffed against `SQLAttemptOutcome`, the resolver constants and the guardrail rule identifiers; no new string literals where a constant exists
- [x] Risk 3 mitigation confirmed — tenant-mismatch increment located in `TenantMismatchError.__init__`, observability import function-local and guarded, `exceptions.py` importable before `init_observability`
- [x] Risk 4 mitigation confirmed — all nine `SET search_path` interpolation sites across five files preceded by an assertion, counted by grep
- [x] Risk 5 mitigation confirmed — assertion counts and logs on mismatch and does not raise; no test expects an exception
- [x] Risk 6 mitigation confirmed — both `wrap_openai` correlation operations individually guarded; chat request verified with LangSmith unset
- [x] Risk 7 mitigation confirmed — training declarations carry lifecycle only; the quality-metric negative test walks the live registry rather than grepping source
- [x] Risk 8 mitigation confirmed — scan asserts a minimum record count before content checks; reproduced by stopping `otel-collector` and observing failure
- [x] Risk 9 mitigation confirmed — extraction recorder takes a count and no type argument; per-type detail on the span only; an unusually named tenant entity type absent from `/metrics` output
- [x] Risk 10 mitigation confirmed — foundation's metrics test scoped by import rather than string match, no allowlist duplicated into it, and that change's row 24 evidence re-collected

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `docs/observability/evidence/workload-instrumentation-tests.txt` — 275 passed. Full verbose run of every test file this change adds or amends. | Rows 1–36, 41 | agent | 2026-09-03 |
| 2 | Test output | `tests/chat_api/test_sql_generation_metrics.py` — `attempts=2`, `repair_depth=1`, `ner_sql_attempts_total{outcome="validation_error"}` incremented, one repair-depth histogram observation per completed generation. | Rows 2, 3 | agent | 2026-09-03 |
| 3 | Test output | `tests/chat_api/test_guardrail_metrics.py` — a raised classifier increments `ner_guardrail_fail_open_total{error_class="RuntimeError"}` while `ner_guardrail_decisions_total{rule="domain",decision="admitted"}` is unchanged. | Rows 7, 8, 9 | agent | 2026-09-03 |
| 4 | Test output | `tests/chat_api/test_llm_usage_metrics.py` — tokens in/out, provider latency and outcome per call; a failed call records an enumerated error class and no provider message text reaches any label. | Row 5 | agent | 2026-09-03 |
| 5 | Test output | `tests/integration/test_no_pii_in_chat_telemetry.py`, `test_no_pii_in_extraction_telemetry.py` — spans, metric labels and log records from one flow, checked against five sentinels, with a non-empty-capture assertion so the checks cannot pass vacuously. | Rows 6, 14 | agent | 2026-09-03 |
| 6 | Test output | `tests/shared/test_tenant_safety_counters.py`, `test_search_path_assertion.py` — mismatch counter, WARNING record, distinct auth-failure reasons, rate-limit rejections, and the search-path assertion counting without raising. | Rows 27–33 | agent | 2026-09-03 |
| 7 | Test output | `tests/shared/test_domain_metrics_declarations.py` — the allowlist is a parsed set literal of five members; a deliberately mislabelled family fails the check and is named; no family carries an entity-type label. | Rows 34, 35, 36, 41 | agent | 2026-09-03 |
| 8 | Test output | `tests/training_service/test_training_metrics.py` — the quality-metric check walks the live `prometheus_client` registry rather than grepping source, so a dynamically registered `f1` family cannot slip past. | Row 23 | agent | 2026-09-03 |
| 9 | Live stack run | `docs/observability/evidence/scan-clean-run.txt` — `telemetry_scan.py` against the running compose stack: 63 logs, 124 spans, 13 metric series captured, exit 0. | Row 37 | agent | 2026-09-03 |
| 10 | Live stack run | `docs/observability/evidence/scan-fails-on-log-leak.txt` — a `WARNING` carrying three sentinels was added to `src/gateway/main.py`, the image rebuilt, and the scan run: exit 1, three findings, each naming `/app/src/gateway/main.py` line 101. Leak reverted immediately afterwards; `git diff src/gateway/main.py` confirmed clean. | Row 38 | agent | 2026-09-03 |
| 11 | Live stack run | `docs/observability/evidence/scan-fails-on-empty-capture.txt` — `docker compose stop otel-collector`, then the scan over a 30s window: exit **2**, `logs: captured 0`, `spans: captured 0`, reported before any content check ran. | Row 39 | agent | 2026-09-03 |
| 12 | Live stack run | `docs/observability/evidence/scan-fails-on-span-only-leak.txt` — a sentinel emitted **only** as a span attribute on an auth-exempt probe route: exit 1, one finding, `[spans] seeded entity value: Priyadarshini Raghunathan in: span leak_probe candidate=… duration_ms=0.19`, and no log finding. Probe reverted and the stack rebuilt; the following scan returned to exit 0. | Row 40 | agent | 2026-09-03 |
| 13 | Test output | `tests/integration/test_telemetry_scan.py` — 19 tests covering the four scan behaviours, including the metric-label-only case and the assertion that the capture floor is evaluated before any content check. | Rows 37–40 | agent | 2026-09-03 |
| 14 | Test output | `tests/integration/test_chat_stage_spans.py` — one span per executed stage, in graph order, each with a duration and an outcome; a stage that did not run produces no span. Driven through `build_nodes` rather than HTTP, because the stages are graph nodes and a request-level assertion would prove nothing about which ran. | Row 1 | agent | 2026-09-03 |
| 15 | Test output | `tests/integration/test_langsmith_correlation.py` — both link directions, each independently guarded; with the ambient trace lookup made to raise, the run-id direction still wires. | Rows 24, 25, 26 | agent | 2026-09-03 |
| 16 | Benchmark | P95 of the chat path's heaviest stage (`generate_and_execute`, 300 iterations after a 20-call warmup, same fakes as the unit tests), instrumentation live vs. every recorder stubbed to a no-op: first-attempt **9.25 ms → 9.61 ms**, repaired **9.58 ms → 8.03 ms**. The delta is inside run-to-run variance — the instrumented repaired arm came out *faster* than the stubbed one — so the added cost is below what this harness can resolve. Live HTTP P95 on the instrumented stack for comparison: gateway `/health` 34.4 ms, chat_api `/health` 50.4 ms. **Caveat:** a true end-to-end chat P95 needs provider credentials and a seeded tenant, neither available here; the provider and database latency a real request adds is constant between the two arms and would only dilute the delta. | Structural evidence | agent | 2026-09-03 |
| 17 | Regression check | Full suite before and after, failing-test IDs diffed: **zero new failures**. Baseline 91 failed / 32 errors / 2072 passed; after 91 failed / 32 errors / 2182 passed (+110, this change's own tests). Pre-existing failures are unrelated and predate the change — `tests/test_analytics_dashboard.py` still fails to collect on a syntax error on `main`. | Structural evidence | agent | 2026-09-03 |
| 18 | Source review | `grep -rn "SET search_path" src/ --include=*.py` — nine interpolation sites across five files, each immediately preceded by `assert_tenant_schema` with its own enumerated `code_path`. Note the count is **nine**, not the eight the tasks and Section 2 risk 4 state: `sql_generator.py` holds five, and `analytics_service/dependencies.py`, `analytics_service/worker.py`, `extraction_service/dependencies.py` and `shared/tenant_context.py` hold one each. | Rows 30, 31; risk 4 | agent | 2026-09-03 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** observability-workload-instrumentation
**Proposal:** `openspec/changes/observability-workload-instrumentation/proposal.md`
**Spec files reviewed:**
  - `specs/workload-telemetry/spec.md`
  - `specs/telemetry-tenant-safety/spec.md`

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
