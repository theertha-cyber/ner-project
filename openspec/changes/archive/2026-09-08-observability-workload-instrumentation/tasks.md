## 1. Declarations and enforcement — land first, gate everything after

- [x] 1.1 Create `src/shared/observability/domain_metrics.py`. Declare every metric family this change introduces: name, instrument type, description, exact label keys, and the closed value set for each label. Export named recorder functions (`record_sql_attempt`, `record_guardrail_decision`, `record_entity_resolution`, …) taking typed arguments. No call site outside this module constructs a metric or names a label. → design Decision 1
- [x] 1.2 Import the measured code's own constants rather than restating them: `SQLAttemptOutcome` and `_defect_class` from `src/chat_api/services/sql_generator.py`, `UNRESOLVED`/`UNIQUE`/`AMBIGUOUS`/`OVER_CAP` from `src/chat_api/services/entity_resolver.py`, the guardrail rule identifiers from `src/chat_api/services/guardrails.py`. A rename upstream must break the import, not silently emit a stale label. → design Decision 2, risk 2
- [x] 1.3 Define `TENANT_LABEL_ALLOWLIST` as an explicit `frozenset` of five family names — chat requests, LLM tokens, LLM cost, extraction jobs, rate-limit rejections. No prefix, pattern or wildcard. → design Decision 10
- [x] 1.4 Add `assert_tenant_schema(schema, code_path)`: validate against `^tenant_[0-9A-Za-z_-]{1,56}$`; on mismatch increment the violation counter and log at ERROR with the code path and a truncated, character-restricted rendering of the value; return either way. It must not raise. → design Decision 5, risk 5
- [x] 1.5 Test: an allowlisted family may carry `tenant_id`; a family not on the list carrying it fails the check and the failure names the family; the allowlist enumerates its members explicitly with no pattern. → verification rows 34, 35, 36 (`tests/shared/test_domain_metrics_declarations.py`)
- [x] 1.6 Test: every declared label has a finite, non-empty enumerated value set, so the series count per family is computable before shipping. → verification structural evidence (`tests/shared/test_domain_metrics_declarations.py`)
- [x] 1.7 Test: no declared family carries an entity-type label. Entity types are tenant-configured (`src/gateway/api/v1/entity_types.py`), so they are neither enumerable at declaration nor safe in a store shared across tenants. → design Decision 12, verification row 41 (`tests/shared/test_domain_metrics_declarations.py`)
- [x] 1.8 Narrow `tests/shared/test_metrics_endpoint.py` from `observability-foundation` before landing the allowlist. It currently scans every `/metrics` line for `tenant_id=` and will go red the moment 1.3's families ship. Change it to enumerate the foundation's own families, and re-collect that change's row 24 evidence. → `observability-foundation` task 7.8. **Do this first — a red test at this point invites weakening the assertion rather than scoping it.**

## 2. Tenant-safety counters — smallest diff, highest gate value

- [x] 2.1 Increment the tenant-mismatch counter inside `TenantMismatchError.__init__` in `src/shared/exceptions.py`, not at the raise site in `src/gateway/dependencies.py:60`. Import observability function-locally and guard it, so `exceptions.py` stays importable before `init_observability` runs. → design Decision 4, risk 3
- [x] 2.2 Confirm the mismatch also produces a WARNING-or-higher log record carrying the request's correlation context, and that the counter carries no tenant label.
- [x] 2.3 Call `assert_tenant_schema` immediately before each of the nine `SET search_path TO {schema}` interpolations: `src/chat_api/services/sql_generator.py` (lines 1127, 1197, 1283, 1418, 1467), `src/analytics_service/dependencies.py:15`, `src/analytics_service/worker.py:36`, `src/extraction_service/dependencies.py:17`, `src/shared/tenant_context.py:35`. → risk 4
- [x] 2.4 Add the auth-failure counter with an enumerated reason — missing header, malformed token, expired token, invalid signature — at the token-validation paths. No token value or fragment in any label.
- [x] 2.5 Add the rejection counter to `SlidingWindowRateLimiter.check` in `src/chat_api/services/rate_limiter.py`, on the branch that returns `False`.
- [x] 2.6 Test: a tenant mismatch increments its counter and emits the WARNING record with correlation context; a mismatch and an invalid-token rejection increment different counters; the mismatch counter's label set on `/metrics` carries no tenant identifier. → verification rows 27, 28, 29 (`tests/shared/test_tenant_safety_counters.py`)
- [x] 2.7 Test: a well-formed tenant schema passes with the violation counter unchanged; a malformed name increments it, logs at ERROR naming the code path, and records the value in a sanitised form. → verification rows 30, 31 (`tests/shared/test_search_path_assertion.py`)
- [x] 2.8 Test: missing header, malformed token and expired token each increment under a distinct reason with no token fragment in any label; a caller over its rate limit increments the rejection counter. → verification rows 32, 33 (`tests/shared/test_tenant_safety_counters.py`)

## 3. Chat path — guardrails, resolution, retrieval

- [x] 3.1 Instrument `src/chat_api/services/guardrails.py`: count every decision by rule identifier, including the block paths in `check_blocked_question_type` and the fallback in `enforce_sources`.
- [x] 3.2 Count the fail-open path at `guardrails.py:102-107` on a dedicated counter, separate from the normal admit, and count the two-classification split in `classify_domain` as its own outcome. Behaviour is unchanged — this task measures only. → design non-goals
- [x] 3.3 Instrument `src/chat_api/services/entity_resolver.py`: record the outcome constant and `mentions_checked` as a span attribute and a counter label. No mention text anywhere.
- [x] 3.4 Instrument the catalogue slice retrieval with the slice size as a span attribute.
- [x] 3.5 Instrument `src/shared/retrieval/{retriever,reranker,orchestrator}.py` and `src/chat_api/services/rag_orchestrator.py`: result count, zero-result counter, hit rate and rerank duration.
- [x] 3.6 Test: a blocked question increments its rule's counter; a raised classifier increments the fail-open counter and is distinguishable from an admit; the empty-sources fallback increments its rule's counter. → verification rows 7, 8, 9 (`tests/chat_api/test_guardrail_metrics.py`)
- [x] 3.7 Test: each of the four resolver outcomes is recorded with mentions checked, and no mention text appears in span attributes or labels. → verification row 10 (`tests/chat_api/test_entity_resolution_metrics.py`)
- [x] 3.8 Test: a retrieval returning nothing records a result count of zero and increments the zero-result counter. → verification row 4 (`tests/chat_api/test_retrieval_metrics.py`)

## 4. Chat path — SQL generation, execution and LLM usage

- [x] 4.1 Instrument the attempt loop in `src/chat_api/services/sql_generator.py`: `attempts`, `repair_depth` (attempts minus one), outcome from `SQLAttemptOutcome`, and defect class through `_defect_class()` — never the raw `defect`, which carries `filename:<literal>` and `scope:<relations>` payloads drawn from tenant data. → design Decision 2, risk 1
- [x] 4.2 Record a repair-depth histogram observation per completed generation.
- [x] 4.3 Record the abandon reason on `SQLGenerationFailed`, distinguishing attempt exhaustion from the `deadline_exhausted` branch at `sql_generator.py:1645`, plus the coverage-probe `reason` path.
- [x] 4.4 Instrument SQL execution: duration, row count and whether the result was truncated.
- [x] 4.5 Instrument LLM calls: input tokens, output tokens, cost, provider latency, outcome, and an enumerated error class on failure — `type(e).__name__` or a mapped class, never the provider's message text.
- [x] 4.6 Instrument answer composition: confidence, citation count, and whether the answer was hedged.
- [x] 4.7 Add one span per stage in `src/chat_api/graph/nodes.py` carrying the node's outcome only — no duplicate of the service-layer measurements. → design Decision 3
- [x] 4.8 Test: a first-invalid/second-valid question records `attempts` 2, `repair_depth` 1, an enumerated defect class on attempt 1, and a histogram observation. → verification row 2 (`tests/chat_api/test_sql_generation_metrics.py`)
- [x] 4.9 Test: attempt exhaustion and deadline exhaustion both yield outcome `abandoned` with distinct enumerated reasons. → verification row 3 (`tests/chat_api/test_sql_generation_metrics.py`)
- [x] 4.10 Test: each LLM call records tokens in and out, provider latency and an outcome; a failed call records an enumerated error class and no provider message text. → verification row 5 (`tests/chat_api/test_llm_usage_metrics.py`)
- [x] 4.11 Integration test on the running stack: one answered chat question produces a span per executed stage, each carrying a duration and an outcome attribute. → verification row 1 (`tests/integration/test_chat_stage_spans.py`)
- [x] 4.12 Integration test: collect every span attribute, metric label and log record from one chat request and assert none contains the question text, answer text, generated SQL, a retrieved passage or an entity value. → verification row 6 (`tests/integration/test_no_pii_in_chat_telemetry.py`)

## 5. Extraction, projection and the Celery queues

- [x] 5.1 Instrument `src/extraction_service/worker.py`: per-run stage reached and per-stage duration, retry count, partial-failure count, pages processed, model version. Per-type entity counts go on the run's **span**, preserving ADR-010's granularity where it is queried; the **metric** is an aggregate count with no entity-type label. → ADR-010, design Decision 12
- [x] 5.2 Add a failure counter labelled by `type(e).__name__` on the extraction failure paths, with the failing stage identifiable from the span.
- [x] 5.3 Instrument `src/extraction_service/services/relational_projection.py`: projection duration and a drift indicator distinguishing a clean projection from one where source and projected row counts disagree. Audit `services/entity_postprocessor.py` for the same.
- [x] 5.4 Add the queue-depth observable gauge, read at scrape time from the broker's list length for both configured queues, registered on the producer side and not in the worker processes. → design Decision 6
- [x] 5.5 Extend the existing Celery header hook to stamp an enqueue timestamp; compute wait time at `task_prerun` against it, clamp a negative value to zero and count the clamp as clock skew. → design Decision 7
- [x] 5.6 Add per-task execution duration, retry count, failure counter labelled by exception class, and worker liveness for both queues.
- [x] 5.7 Test: a successful extraction run reports per-stage durations, pages processed, model version and per-type entity counts; a failed run identifies the failing stage and increments a failure counter labelled by exception class. → verification rows 11, 12 (`tests/extraction_service/test_extraction_metrics.py`)
- [x] 5.8 Test: the projection records duration and a drift indicator, with a mismatched-count case producing the drift value. → verification row 13 (`tests/extraction_service/test_projection_metrics.py`)
- [x] 5.9 Integration test: extract a document with known seeded entity values and assert no span attribute, metric label or log record from that run contains one. → verification row 14 (`tests/integration/test_no_pii_in_extraction_telemetry.py`)
- [x] 5.10 Test: backed-up tasks produce a non-zero queue depth; wait time and execution duration are separate observations; a raising task increments the failure counter under its exception class with no message text in the label. → verification rows 15, 16, 17 (`tests/shared/test_celery_queue_metrics.py`)

## 6. Model serving and training

- [x] 6.1 Instrument `src/model_serving/services/inference_service.py`: inference duration, window and batch geometry from `_window_geometry`/`_build_windows`, and the active model version as a span attribute. → ADR-003
- [x] 6.2 Record which path executed at `infer()` (line 354) — tenant ONNX via `_infer_with_onnx` or base model via `_infer_with_base_model`. The base-model path is a success under ADR-008, not a failure; the error-triggered fallback at line 366 is recorded separately from the no-promoted-model path.
- [x] 6.3 Record a model-load event with its duration in `_load_model_for_tenant`, distinguishing a cold start from a cache hit.
- [x] 6.4 Instrument `src/model_serving/services/rerank_service.py` with rerank duration.
- [x] 6.5 Instrument `src/training_service/worker.py`: job state transitions, total duration, epoch progress, and a failure counter under an enumerated cause. Job identity derives from the `training_jobs` row, not a request payload. → ADR-009
- [x] 6.6 Do not mirror MLflow's evaluation metrics. F1, precision, recall and loss stay in MLflow and are not registered as platform metric families. → design Decision 9, risk 7
- [x] 6.7 Test: an inference for a tenant with a promoted model records duration, active version and the tenant-model path; one for a tenant without records the base-model path as a success; a first load records a model-load event with duration. → verification rows 18, 19, 20 (`tests/model_serving/test_inference_metrics.py`)
- [x] 6.8 Test: a completed job records each state transition and total duration; a failed job increments a failure counter under an enumerated cause and records its final state. → verification rows 21, 22 (`tests/training_service/test_training_metrics.py`)
- [x] 6.9 Test: walk the live metric registry and assert no family exposes F1, precision, recall or loss. Registry walk, not a source grep — a dynamically registered family must not slip past. → verification row 23 (`tests/training_service/test_training_metrics.py`)

## 7. LangSmith correlation

- [x] 7.1 At the two `wrap_openai` sites — `src/chat_api/services/rag_orchestrator.py:5` and `src/chat_api/services/sql_generator.py:6` — attach the ambient OTel trace id to the LangSmith run as metadata, and set the LangSmith run id as an attribute on the enclosing span. → design Decision 8
- [x] 7.2 Wrap each correlation operation in its own try/except that logs at DEBUG and continues. LangSmith is off by default, configured by bare environment variables read by its own SDK (`.env.example:69-74`), and must never fail a chat request. → risk 6
- [x] 7.3 Test: with LangSmith enabled, the run carries the OTel trace identifier and the span carries the LangSmith run identifier. → verification rows 24, 25 (`tests/integration/test_langsmith_correlation.py`)
- [x] 7.4 Test: with LangSmith disabled or unreachable, the request is answered normally and the OTel spans are still emitted. → verification row 26 (`tests/integration/test_langsmith_correlation.py`)

## 8. Release-gate telemetry scan

- [x] 8.1 Write `scripts/telemetry_scan.py`: seed a tenant with known sentinel entity values, drive one chat request and one extraction end to end against the running compose stack, then query Loki, Tempo and Prometheus for the telemetry that flow produced. → design Decision 11
- [x] 8.2 Assert a minimum expected record count across all three backends **before** any content check, and exit non-zero when it is not met. An empty capture is a failure, never a clean result. → risk 8
- [x] 8.3 Fail on any sentinel entity value or personal-data pattern match found in a log record, a span attribute or a metric label, and print the offending record or attribute.
- [x] 8.4 Verify the scan by deliberately reintroducing a leak — a log line carrying a seeded entity value — confirming it fails and names the record, then reverting.
- [x] 8.5 Verify the scan fails on an empty capture by stopping `otel-collector` and running it.
- [x] 8.6 Verify the scan catches a sentinel present only in a span attribute, and separately only in a metric label, with no log record carrying it.
- [x] 8.7 The repository has no CI configuration (no `.github/`, no `Makefile`, no `tox.ini`). Add `.github/workflows/telemetry-scan.yml` bringing up the compose stack and running the scan, and record the runtime so the merge-versus-release gating question in design.md § Open Questions can be answered with a real number.
- [x] 8.8 Test wrapper covering the four scan behaviours so they are re-runnable outside the pipeline. → verification rows 37, 38, 39, 40 (`tests/integration/test_telemetry_scan.py`)

## 9. Documentation

- [x] 9.1 Document the metric contract in `docs/` — every family, its labels and each label's enumerated values — as the input story 5.1's dashboards build against.
- [x] 9.2 Extend the telemetry rule in `AGENTS.md` added by `observability-foundation`: new metrics are declared in `domain_metrics.py`, label values are enumerated, and a `tenant_id` label requires amending the allowlist under review.
- [x] 9.3 Document the release-gate scan in `docs/local-dev.md` — how to run it against the local stack and how to read its output.

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 10.5 Measure chat request P95 on the local stack before and after instrumentation and record the delta as structural evidence.
- [ ] 10.6 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.7 Run `openspec validate observability-workload-instrumentation --type change --strict` and confirm it exits clean before archive.
