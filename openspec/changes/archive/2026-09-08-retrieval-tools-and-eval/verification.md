# Verification Plan

**Change:** retrieval-tools-and-eval
**Generated:** 2026-07-28
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | retrieval-tools | Retrieval tool contract | Tool exposes a complete contract | Given any registered tool, when its contract fields are read, then `name` is non-empty snake_case, `description` is non-empty, and `args_schema` is a JSON Schema object with `type: "object"` and a `properties` map | unit test: `tests/test_retrieval_tools.py::test_tool_contract_shape` (task 2.4) | - [ ] |
| 2 | retrieval-tools | Retrieval tool contract | Invalid arguments are rejected before execution | Given a tool requiring a string `query`, when called with `query=123`, then a `ToolResult` with `error` set and empty `results` is returned and no database query executes | unit test: `tests/test_retrieval_tools.py::test_invalid_arg_type_rejected_without_query` (task 2.4) | - [ ] |
| 3 | retrieval-tools | Retrieval tool contract | Unknown argument keys are rejected | Given a tool declaring only `query` and `top_k`, when called with an extra `schema` key, then a `ToolResult` with `error` set is returned and no database query executes | unit test: `tests/test_retrieval_tools.py::test_unknown_arg_key_rejected` (task 2.4) | - [ ] |
| 4 | retrieval-tools | Tool result envelope | Successful invocation reports metadata | Given a seeded tenant schema with matching chunks, when `search_documents` completes, then `error is None`, `degraded is False`, `latency_ms > 0`, and every item in `results` is a `RetrievalResult` | unit test: `tests/test_retrieval_tools.py::test_result_envelope_success_metadata` (task 3.4) | - [ ] |
| 5 | retrieval-tools | Tool result envelope | Retrieval failure returns an error result rather than raising | Given the underlying retriever raises, when the tool is invoked, then a `ToolResult` with non-empty `error` and empty `results` is returned and no exception propagates | unit test: `tests/test_retrieval_tools.py::test_retriever_exception_returns_error_result` (task 3.4) | - [ ] |
| 6 | retrieval-tools | Tool result envelope | Degraded retrieval is flagged | Given a `RerankingRetriever` whose reranker is unavailable, when the tool is invoked, then `degraded is True` and `results` contains the fallback candidates | unit test: `tests/test_retrieval_tools.py::test_degraded_flag_on_reranker_fallback` (task 3.4) | - [ ] |
| 7 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied | Tool schemas expose no tenancy parameters | Given every registered tool, when `args_schema.properties` keys are inspected, then none is `schema`, `tenant_id`, `tenant`, or `purpose` | unit test: `tests/test_retrieval_tools.py::test_no_tenancy_params_in_any_args_schema` (task 2.4) | - [ ] |
| 8 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied | Tool queries the context's schema only | Given two tenant schemas with matching chunks, when a tool runs with a `ToolContext` for the first, then every result originates from the first schema and none from the second | integration test: `tests/test_retrieval_tools_integration.py::test_two_schema_isolation` (task 3.5) | - [ ] |
| 9 | retrieval-tools | Tenant scope is caller-supplied, never argument-supplied | Purpose restriction survives the tool layer | Given a schema with `purpose='training'` and `purpose='query'` chunks matching the query, when any document tool is invoked with any argument values, then no result comes from a `purpose='training'` chunk | integration test: `tests/test_retrieval_tools_integration.py::test_training_purpose_excluded` (task 3.5) | - [ ] |
| 10 | retrieval-tools | Document retrieval tools | search_documents delegates to the configured retriever | Given a spy `Retriever` in the context, when `search_documents.call({"query": "q"})` runs, then the spy's `retrieve` is called exactly once with `query == "q"` and its results are returned | unit test: `tests/test_retrieval_tools.py::test_search_documents_delegates_once` (task 3.4) | - [ ] |
| 11 | retrieval-tools | Document retrieval tools | lookup_document restricts results to one document | Given chunks from two documents both matching, when `lookup_document` is called with `document_id` of the first, then every result has that `document_id` | integration test: `tests/test_retrieval_tools_integration.py::test_lookup_document_restricts_to_document_id` (task 3.5) | - [ ] |
| 12 | retrieval-tools | Document retrieval tools | top_k argument bounds the result count | Given more matching chunks than requested, when `search_documents` is called with `top_k=3`, then at most 3 results are returned | unit test: `tests/test_retrieval_tools.py::test_top_k_bounds_result_count` (task 3.4) | - [ ] |
| 13 | retrieval-tools | Document retrieval tools | top_k is capped against caller-supplied inflation | Given a configured maximum tool `top_k`, when a tool is called with a larger `top_k`, then the effective `top_k` is clamped to the maximum and the call does not fail | unit test: `tests/test_retrieval_tools.py::test_top_k_clamped_to_max` (task 3.4) | - [ ] |
| 14 | retrieval-tools | Entity retrieval tool | Entity tool returns structured rows | Given a tenant schema with extracted entities, when `search_entities` is invoked with a natural-language query, then `results` is a list of row mappings and `error is None` | integration test: `tests/test_retrieval_tools_integration.py::test_search_entities_returns_rows` (task 4.3) | - [ ] |
| 15 | retrieval-tools | Entity retrieval tool | Entity tool is importable from shared code | Given the codebase after this change, when the module defining `search_entities` is imported, then `src.chat_api` is not transitively imported | import-isolation test: `tests/test_retrieval_tools.py::test_entity_tool_does_not_import_chat_api` (task 4.4) | - [ ] |
| 16 | retrieval-tools | Entity retrieval tool | Entity tool preserves SQL guardrails | Given a query whose generated SQL is rejected by the existing validation layer, when `search_entities` runs, then the SQL is not executed and `error` is set | unit test: `tests/test_retrieval_tools.py::test_rejected_sql_not_executed` (task 4.3) | - [ ] |
| 17 | retrieval-tools | Tool registry and schema export | Registry resolves tools by name | Given a registry containing the three tools, when `get("search_documents")` is called, then the registered `search_documents` tool is returned | unit test: `tests/test_retrieval_tools.py::test_registry_get_by_name` (task 2.4) | - [ ] |
| 18 | retrieval-tools | Tool registry and schema export | Unknown tool name is an explicit error | Given a populated registry, when `get("delete_documents")` is called, then an explicit lookup error naming the unknown tool is raised | unit test: `tests/test_retrieval_tools.py::test_registry_unknown_name_raises` (task 2.4) | - [ ] |
| 19 | retrieval-tools | Tool registry and schema export | Duplicate registration is rejected | Given a registry already containing `search_documents`, when another tool with the same name is registered, then registration fails with an explicit error | unit test: `tests/test_retrieval_tools.py::test_registry_duplicate_rejected` (task 2.4) | - [ ] |
| 20 | retrieval-tools | Tool registry and schema export | Exported schemas are tool-calling shaped | Given a populated registry, when `export_schemas()` is called, then each entry has `type == "function"` and `function.name` / `.description` / `.parameters` match the tool's `name` / `description` / `args_schema` | unit test: `tests/test_retrieval_tools.py::test_export_schemas_tool_calling_shape` (task 2.4) | - [ ] |
| 21 | retrieval-tools | Chat runtime behaviour is unchanged by the tool layer | Existing chat tests pass unmodified | Given the codebase after this change, when the existing chat and retrieval suites run unmodified, then they pass | regression run: `tests/test_chat_api_rag.py`, `test_chat_api_sql.py`, `test_langgraph_parity.py` unmodified (task 4.5) | - [ ] |
| 22 | retrieval-tools | Chat runtime behaviour is unchanged by the tool layer | Graph nodes do not depend on the tool layer | Given the codebase after this change, when `src/chat_api/graph/nodes.py` is inspected, then it neither imports nor invokes the tool layer | code inspection: `src/chat_api/graph/nodes.py` imports (task 4.5) | - [ ] |
| 23 | retrieval-eval | Versioned golden set | Golden set loads and validates | Given the committed golden-set JSONL, when the loader reads it, then every record has a non-empty `query_id`, non-empty `query`, and a `relevant` list whose entries each have `document_id`, integer `chunk_index`, and `grade` in `0..3` | unit test: `tests/test_retrieval_eval.py::test_golden_set_loads_and_validates` (task 5.5) | - [ ] |
| 24 | retrieval-eval | Versioned golden set | Duplicate query ids are rejected | Given a golden-set file with two records sharing a `query_id`, when it is loaded, then loading fails with an error naming the duplicated `query_id` | unit test: `tests/test_retrieval_eval.py::test_duplicate_query_id_rejected` (task 5.5) | - [ ] |
| 25 | retrieval-eval | Versioned golden set | Judgments reference the committed corpus | Given the committed golden set and corpus, when every `relevant` entry is resolved, then each referenced `(document_id, chunk_index)` exists in the corpus | unit test: `tests/test_retrieval_eval.py::test_judgments_resolve_against_corpus` (task 5.5) | - [ ] |
| 26 | retrieval-eval | Versioned golden set | Golden set contains no tenant or production data | Given the committed corpus, when its provenance is inspected, then every document is synthetic content authored for evaluation and none originates from a live tenant schema | provenance review: `tests/fixtures/retrieval_eval/README.md` + corpus inspection (task 5.1) | - [ ] |
| 27 | retrieval-eval | Retrieval metrics | Perfect ranking scores 1.0 | Given a query with three relevant chunks returned at ranks 1–3 in grade order, when metrics are computed at `k=5`, then `recall@5 == 1.0`, `nDCG@5 == 1.0`, and `MRR@5 == 1.0` | unit test: `tests/test_retrieval_metrics.py::test_perfect_ranking_scores_one` (task 6.2) | - [ ] |
| 28 | retrieval-eval | Retrieval metrics | Empty result set scores zero without error | Given a query with at least one relevant chunk and zero results, when metrics are computed, then `recall@k`, `precision@k`, `MRR@k`, and `nDCG@k` are all `0.0` and no exception is raised | unit test: `tests/test_retrieval_metrics.py::test_empty_results_score_zero` (task 6.2) | - [ ] |
| 29 | retrieval-eval | Retrieval metrics | Rank position affects MRR and nDCG but not recall | Given the same single relevant chunk at rank 1 in one list and rank 4 in another, when metrics are computed at `k=5`, then `recall@5` is equal and `MRR@5` / `nDCG@5` are strictly greater for the rank-1 list | unit test: `tests/test_retrieval_metrics.py::test_rank_position_affects_mrr_ndcg_only` (task 6.2) | - [ ] |
| 30 | retrieval-eval | Retrieval metrics | Graded relevance is honoured by nDCG | Given two equal-length lists, one ranking a `grade=3` chunk above a `grade=1` chunk and the other reversed, when `nDCG@k` is computed, then the first scores strictly higher | unit test: `tests/test_retrieval_metrics.py::test_graded_relevance_ordering` (task 6.2) | - [ ] |
| 31 | retrieval-eval | Retrieval metrics | A query with no judgments is excluded, not scored as zero | Given a golden-set record with an empty `relevant` list, when aggregates are computed, then that query is excluded from the means and recorded as skipped with a reason | unit test: `tests/test_retrieval_metrics.py::test_zero_judgment_query_skipped` (task 6.2) | - [ ] |
| 32 | retrieval-eval | Evaluation executes through the tool layer | Eval run invokes the tool layer | Given a run configured with a spy tool registry over N queries, when the run completes, then `search_documents` was invoked exactly N times per configuration | unit test: `tests/test_retrieval_eval_runner.py::TestRunnerInvokesToolLayer::test_runner_invokes_tool_per_query` (task 7.6) | - [ ] |
| 33 | retrieval-eval | Evaluation executes through the tool layer | Tool errors are recorded, not fatal | Given N queries where one tool invocation returns `error`, when the run completes, then the other `N-1` queries are evaluated and the report lists the failed query with its error | unit test: `tests/test_retrieval_eval_runner.py::TestToolErrorNotFatal::test_tool_error_recorded_not_fatal` (task 7.6) | - [ ] |
| 34 | retrieval-eval | Configuration matrix comparison | Matrix run produces per-configuration metrics | Given a matrix of three named configurations, when the golden set is executed, then the report contains one aggregate block per configuration, each labelled with its name and parameter values | unit test: `tests/test_retrieval_eval_runner.py::TestMatrixPerConfigAggregates::test_matrix_produces_per_config_aggregates` (task 7.6) | - [ ] |
| 35 | retrieval-eval | Configuration matrix comparison | Configurations do not leak between runs | Given a matrix with reranking-disabled followed by reranking-enabled, when the run completes, then global settings equal their pre-run values and the reranking-enabled results reflect reranking having been applied | unit test: `tests/test_retrieval_eval_runner.py::TestConfigDoesNotLeakToGlobalSettings::test_config_does_not_leak_and_reranking_applies` (task 7.6) | - [ ] |
| 36 | retrieval-eval | Configuration matrix comparison | Per-query results are retained alongside aggregates | Given a completed matrix run, when the JSON report is inspected, then per-query metrics keyed by `query_id` exist per configuration and aggregates are reproducible from them | unit test: `tests/test_retrieval_eval_runner.py::TestPerQueryReproducesAggregate::test_per_query_blocks_reproduce_aggregate` (task 7.6) | - [ ] |
| 37 | retrieval-eval | Report output | JSON report is complete and machine-readable | Given a completed run, when the JSON report is parsed, then it contains `run_timestamp`, `golden_set`, `query_count`, `configurations`, `per_query`, and `aggregate` | unit test: `tests/test_retrieval_eval_runner.py::TestJsonReportFields::test_json_report_fields_complete` (task 7.6) | - [ ] |
| 38 | retrieval-eval | Report output | Markdown summary ranks configurations | Given a matrix run over more than one configuration, when the Markdown summary is read, then it presents aggregate metrics per configuration and identifies the highest `nDCG@5` | unit test: `tests/test_retrieval_eval_runner.py::TestMarkdownSummaryRanksConfigs::test_markdown_summary_ranks_configurations` (task 7.6) | - [ ] |
| 39 | retrieval-eval | Baseline regression gate | Regression below tolerance fails the gate | Given baseline `nDCG@5 = 0.80` and tolerance `0.02`, when a run produces `0.70`, then the gate fails and the message names the metric, baseline, and observed value | unit test: `tests/test_retrieval_eval_gate.py::test_regression_below_tolerance_fails` (task 8.5) | - [ ] |
| 40 | retrieval-eval | Baseline regression gate | Movement within tolerance passes | Given baseline `nDCG@5 = 0.80` and tolerance `0.02`, when a run produces `0.79`, then the gate passes | unit test: `tests/test_retrieval_eval_gate.py::test_within_tolerance_passes` (task 8.5) | - [ ] |
| 41 | retrieval-eval | Baseline regression gate | Improvement passes and is reported | Given a committed baseline, when a run scores above it on both gated metrics, then the gate passes and the summary reports the deltas as improvements | unit test: `tests/test_retrieval_eval_gate.py::test_improvement_reported` (task 8.5) | - [ ] |
| 42 | retrieval-eval | Baseline regression gate | Gate is excluded from the default test run | Given the codebase after this change, when default `pytest` runs without the eval marker, then no golden-set evaluation executes and the eval modules make no embedding or database call | marker check: default `pytest` run collects no eval gate; no DB/embedding call (task 8.4) | - [ ] |
| 43 | retrieval-eval | Baseline regression gate | Missing baseline is an explicit failure | Given no committed baseline file, when the gate is invoked, then it fails with a message explaining how to generate and commit a baseline, and does not silently pass | unit test: `tests/test_retrieval_eval_gate.py::test_missing_baseline_fails_explicitly` (task 8.5) | - [ ] |
| 44 | retrieval-eval | Deterministic offline evaluation | Default run makes no embedding API call | Given committed precomputed embeddings and no opt-in flag, when an eval run executes, then no request is made to the embedding provider | offline run: eval executed with network disabled (task 7.7) | - [ ] |
| 45 | retrieval-eval | Deterministic offline evaluation | Repeated runs are identical | Given an unchanged golden set, corpus, and configuration, when the run executes twice, then the aggregate metrics of both runs are identical | determinism test: `tests/test_retrieval_eval_runner.py::TestDeterminism::test_repeated_runs_are_identical` (task 7.7) | - [ ] |
| 46 | retrieval-eval | Deterministic offline evaluation | Stale precomputed embeddings are detected | Given embeddings recorded against one model name and a configuration naming another, when a run starts, then it fails with an explicit mismatch error naming both models and does not score against the wrong vectors | unit test: `tests/test_retrieval_eval.py::test_embedding_model_mismatch_fails` (task 5.4) | - [ ] |
| 47 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Default configuration matches prior hardcoded behavior | Given no retrieval env vars, when configuration loads, then chunk size is 512, overlap 128, top-k 5, embedding model `text-embedding-3-small` | regression run: `tests/test_retrieval_foundation.py` unmodified (task 1.4) | - [ ] |
| 48 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Configuration is overridable via environment variable | Given `NER_RETRIEVAL_TOP_K=8`, when configuration loads, then `DenseRetriever` uses `top_k=8` when no explicit `top_k` is passed | regression run: `tests/test_retrieval_foundation.py` env-var override case (task 1.4) | - [ ] |
| 49 | retrieval-core | Centralized retrieval configuration (MODIFIED) | HybridRetriever's per-source candidate count is bounded | Given `retrieval_top_k = 20`, when `HybridRetriever.retrieve` fetches fusion candidates, then the per-source count does not exceed the fixed cap | regression run: `tests/test_hybrid_retrieval.py` candidate-cap case (task 1.4) | - [ ] |
| 50 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Per-instance override takes precedence over global settings | Given `settings.reranker_enabled is True` and a `RerankingRetriever` built with an override disabling reranking, when `retrieve` runs, then the reranker is not invoked and the wrapped retriever's ordering is returned | unit test: `tests/test_retrieval_config.py::test_instance_override_wins` (task 1.3) | - [ ] |
| 51 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Absent override falls back to global settings | Given a retriever built with no override, when `retrieve` runs with no explicit `top_k`, then effective `top_k`, `reranker_enabled`, and `rerank_candidate_count` come from global `settings` | unit test: `tests/test_retrieval_config.py::test_absent_override_falls_back_to_settings` (task 1.3) | - [ ] |
| 52 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Overrides do not mutate global settings | Given recorded pre-run global settings, when two retrievers with different overrides each retrieve, then each uses its own values and global settings are unchanged afterwards | unit test: `tests/test_retrieval_config.py::test_overrides_do_not_mutate_global_settings` (task 1.3) | - [ ] |
| 53 | retrieval-core | Centralized retrieval configuration (MODIFIED) | Existing call sites are unaffected | Given the codebase after this change, when existing retrieval and chat suites run unmodified, then they pass | regression run: full retrieval + chat suites unmodified, exit 0 (task 1.4 / 4.5) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Tenant scoping in tool argument schemas (design Decision 2, ADR-001) | Adds a convenience `schema`, `tenant_id`, or `purpose` argument to `args_schema` "for testability", reintroducing an LLM-influenceable tenancy parameter | Read every `args_schema` in `src/shared/retrieval/tools/` and confirm the property set is a subset of `{query, top_k, document_id}`; confirm a test asserts the exclusion rather than only the happy path |
| 2 | Tool layer reimplementing retrieval (design Decision 1) | Writes its own SQL, its own RRF, or its own top-k slicing inside a tool rather than delegating to the composed `Retriever`, creating a second path that drifts from the chat path | Grep the tools package for `text(`, `SELECT`, `rrf`, `embedding` — there should be none; confirm `search_documents` calls the context's retriever exactly once |
| 3 | `RetrievalConfig` resolution order (design Decision 3) | Reverses precedence (global `settings` winning over an explicit override), or reads `settings` mid-call in one branch and the override in another, so a matrix configuration silently does not apply | Trace every `settings.` read remaining in `retriever.py`; each must be the final fallback. Confirm rows 50–52 have real tests, and that the reranking-enabled matrix run actually shows different results from the reranking-disabled one |
| 4 | SQL path extraction (design Decision 4, ADR-007) — implemented via the injected-callable fallback, not a physical move (see design.md Decision 4 implementation note) | `entity_tools.py` reimplements or bypasses SQL generation/validation instead of delegating entirely to the caller-supplied `sql_search` callable | Confirm `entity_tools.py` contains no SQL construction of its own; confirm `RAGOrchestrator._sql_source` and `SQLGenerator` are byte-identical to before this change; confirm `test_chat_api_sql.py` passes unmodified |
| 5 | Metric formulas (design Decision 6) | Implements `nDCG` with binary gains (dropping graded relevance), or normalizes against the retrieved list instead of the ideal ranking, producing plausible-looking but wrong numbers | Hand-verify `nDCG@5` for one fixture query against an independent calculation; confirm rows 30 and 27 are covered by tests using different grades, not just grade 1 |
| 6 | Determinism and embedding provenance (design Decision 5) | Falls back to live embedding calls when a query is missing from `embeddings.json`, or skips the model-name check, silently making runs non-reproducible | Run the eval with network disabled and confirm it either passes or fails loudly; confirm the mismatch check (row 46) raises rather than warns |
| 7 | Degraded runs scored as healthy (design Risks) | Treats a `degraded=True` result the same as a healthy one, so a reranking configuration that silently fell back to unranked candidates is reported (and baselined) as reranked | Take the reranker offline, run the reranking configuration, and confirm the report labels it degraded and refuses to update the baseline from it |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant PostgreSQL schemas with `search_path` enforcement | `schema` and `tenant_id` reach tools only via `ToolContext` from authenticated request state; eval fixtures seed a disposable test schema only | Inspect all `args_schema` property sets for tenancy keys (none permitted); run the two-schema isolation test (row 8); confirm the eval runner creates and drops its own schema and never targets a schema outside the test database |
| ADR-003 Per-Tenant Model Serving Topology | Shared serving pool, tenant-aware routing, on-demand loading | Reranking is reached over HTTP via `model_serving`; a failed reranker must surface as `degraded`, never as a silent healthy result | Stop `model_serving`, invoke `search_documents` with a reranking-composed retriever, and confirm `ToolResult.degraded is True` and the eval report labels the configuration degraded |
| ADR-004 OpenSpec SDD Governance | Proposal → design → spec → tasks → evidence gates | Report and baseline formats must be durable and diffable so they can serve as evidence for future retrieval changes | Confirm `baseline.json` and the JSON report are committed as stable-key JSON (sorted keys, no run-varying fields inside the compared block) and that a re-run produces a diff limited to timestamps |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG; SQL validation layer; citation enforcement; P95 < 10s | `search_entities` must route through the existing validated SQL path; the tool layer must not become a fourth source or bypass guardrails | Confirm `search_entities` only ever calls the `sql_search` callable supplied via `ToolContext` (never constructs SQL itself); confirm the caller-supplied callable in tests/eval is `SQLGenerator().generate_and_execute`, unchanged; confirm no tool constructs SQL directly; confirm `src/chat_api/graph/` is unmodified (row 22) |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Rows 1–3 (tool contract): test output showing contract-shape and argument-validation tests pass, including the no-database-call assertion for both rejection cases
- [ ] Rows 4–6 (result envelope): test output for success metadata, error-not-raised, and degraded-flag cases
- [ ] Row 7 (no tenancy parameters): test output asserting the property-set exclusion across all registered tools
- [ ] Row 8 (schema isolation): integration test output over two seeded schemas showing zero cross-schema results
- [ ] Row 9 (purpose restriction): integration test output showing no `purpose='training'` chunk returned via any tool
- [ ] Rows 10–13 (document tools): test output for spy delegation, `document_id` restriction, `top_k` bound, and `top_k` clamp
- [ ] Rows 14–16 (entity tool): test output for structured rows, the import-isolation assertion, and the rejected-SQL guardrail case
- [ ] Rows 17–20 (registry): test output for resolve, unknown-name error, duplicate rejection, and exported schema shape
- [ ] Rows 21–22 (chat unchanged): full run of `tests/test_chat_api_rag.py`, `test_chat_api_sql.py`, `test_langgraph_parity.py`, `test_hybrid_retrieval.py`, `test_reranking_retriever.py` unmodified, plus the `nodes.py` import inspection
- [ ] Rows 23–26 (golden set): loader validation output, duplicate-id failure output, corpus cross-reference check output, and a written provenance statement for the corpus
- [ ] Rows 27–31 (metrics): unit test output covering perfect ranking, empty results, rank sensitivity, graded nDCG, and the skipped-query case
- [ ] Rows 32–33 (tool-layer execution): spy-registry invocation count output and a report excerpt listing a failed query with its error
- [ ] Rows 34–36 (config matrix): report excerpt showing one aggregate block per configuration with parameters, a before/after settings comparison, and per-query blocks keyed by `query_id`
- [ ] Rows 37–38 (report output): parsed JSON report field listing and the Markdown summary excerpt naming the best `nDCG@5` configuration
- [ ] Rows 39–43 (regression gate): gate output for a below-tolerance failure, a within-tolerance pass, an improvement, a default-`pytest` run showing no eval executed, and a missing-baseline failure message
- [ ] Rows 44–46 (determinism): network-disabled run output, two identical consecutive run aggregates, and the model-mismatch failure message
- [ ] Rows 47–49 (existing retrieval-core scenarios): test output for defaults, env-var override, and candidate cap
- [ ] Rows 50–52 (config override): test output for precedence, fallback, and the unchanged-global-settings assertion
- [ ] Row 53 (call sites unaffected): full unmodified retrieval and chat suite run with exit 0

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] `src/shared/retrieval/` has no import path reaching `src.chat_api` (Decision 4)
- [ ] `src/chat_api/graph/` is unchanged in the diff (Decision 1 / row 22)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — every tool `args_schema` property set inspected; no tenancy or purpose key present
- [ ] Risk 2 mitigation confirmed — tools package grepped for SQL/fusion/embedding code; delegation to the composed retriever verified
- [ ] Risk 3 mitigation confirmed — every remaining `settings.` read in `retriever.py` traced as final fallback; matrix run shows reranking-on and reranking-off producing different results
- [ ] Risk 4 mitigation confirmed — extracted SQL service diffed against the original `_sql_source`; validation layer and read-only execution intact
- [ ] Risk 5 mitigation confirmed — `nDCG@5` hand-verified against an independent calculation for at least one graded fixture query
- [ ] Risk 6 mitigation confirmed — eval executed with network disabled; missing-embedding and model-mismatch paths both fail loudly rather than falling back
- [ ] Risk 7 mitigation confirmed — reranker taken offline; degraded configuration labelled in the report and rejected as a baseline source

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** retrieval-tools-and-eval
**Proposal:** `openspec/changes/retrieval-tools-and-eval/proposal.md`
**Spec files reviewed:**
  - specs/retrieval-tools/spec.md
  - specs/retrieval-eval/spec.md
  - specs/retrieval-core/spec.md

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
