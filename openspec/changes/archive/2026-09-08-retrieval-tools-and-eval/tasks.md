## 1. Retrieval configuration override (retrieval-core)

- [x] 1.1 Add a `RetrievalConfig` model (`top_k`, `reranker_enabled`, `rerank_candidate_count`, all optional) in `src/shared/retrieval/config.py` with a `resolve()` helper implementing precedence: explicit call argument → instance config → global `settings`.
- [x] 1.2 Accept an optional `config: RetrievalConfig | None` at construction on `DenseRetriever`, `SparseRetriever`, `HybridRetriever`, and `RerankingRetriever`; replace every direct `settings.` read in `src/shared/retrieval/retriever.py` with a `resolve()` call whose final fallback is `settings`.
- [x] 1.3 Unit tests in `tests/test_retrieval_config.py`: per-instance override wins over global (row 50), absent override falls back to global (row 51), two retrievers with different overrides leave global `settings` unchanged (row 52).
- [x] 1.4 Regression run: `tests/test_retrieval_foundation.py`, `test_hybrid_retrieval.py`, `test_reranking_retriever.py` unmodified — covers rows 47, 48, 49, 53.

## 2. Tool layer foundation (retrieval-tools)

- [x] 2.1 Create `src/shared/retrieval/tools/base.py`: `ToolContext` (frozen dataclass — `tenant_id`, `schema`, `session`, `retriever`, `jwt_token`, `max_top_k`), `ToolResult` (`tool_name`, `results`, `latency_ms`, `degraded`, `error`), and the `RetrievalTool` protocol (`name`, `description`, `args_schema`, `async call`).
- [x] 2.2 Implement shared argument validation: validate `args` against `args_schema`, reject unknown keys, and return an error `ToolResult` without executing. No tool may declare `schema`, `tenant_id`, `tenant`, or `purpose` in `args_schema`.
- [x] 2.3 Implement `ToolRegistry` in `src/shared/retrieval/tools/registry.py`: `register` (rejecting duplicate names), `get` (explicit error on unknown name), `list`, and `export_schemas()` emitting `{"type": "function", "function": {name, description, parameters}}`.
- [x] 2.4 Unit tests in `tests/test_retrieval_tools.py` using a fake tool and fake retriever — no database: contract shape (row 1), invalid argument type (row 2), unknown argument key (row 3), no-tenancy-parameters assertion across all registered tools (row 7), registry resolve / unknown / duplicate / export shape (rows 17–20).

## 3. Document retrieval tools (retrieval-tools)

- [x] 3.1 Implement `search_documents` in `src/shared/retrieval/tools/document_tools.py`: args `{query, top_k?}`, delegates to `context.retriever.retrieve`, clamps `top_k` to `context.max_top_k`, returns `RetrievalResult` list. No SQL, ranking, or fusion logic in this module.
- [x] 3.2 Implement `lookup_document`: args `{query, document_id, top_k?}`, delegates with `metadata_filter={"document_id": ...}`.
- [x] 3.3 Populate `ToolResult` metadata: measure `latency_ms`, set `degraded` when a `RerankingRetriever` fell back, catch retriever exceptions into `error` without raising.
- [x] 3.4 Unit tests (spy retriever, no database) in `tests/test_retrieval_tools.py`: single delegation with correct query (row 10), `top_k` bound (row 12), `top_k` clamp (row 13), success metadata (row 4), exception-to-error (row 5), degraded flag (row 6).
- [x] 3.5 Integration tests in `tests/test_retrieval_tools_integration.py` against a seeded tenant schema: `document_id` restriction (row 11), two-schema isolation (row 8), `purpose='training'` exclusion (row 9).

## 4. Entity retrieval tool (retrieval-tools)

- [x] 4.1 Extract the SQL generation + validated execution body of `RAGOrchestrator._sql_source` into a shared service (`src/shared/retrieval/entity_search.py`) as a pure move; leave `_sql_source` as a delegating wrapper. If the extraction proves non-mechanical, fall back to design.md Decision 4's injected-callable alternative and record the deviation.
- [x] 4.2 Implement `search_entities` in `src/shared/retrieval/tools/entity_tools.py` calling that service; args `{query}` only.
- [x] 4.3 Test: structured rows returned against a seeded schema (row 14); rejected-SQL guardrail leaves SQL unexecuted and sets `error` (row 16).
- [x] 4.4 Import-isolation test asserting the entity tool module's transitive imports never reach `src.chat_api` (row 15).
- [x] 4.5 Parity run: `tests/test_chat_api_rag.py`, `test_chat_api_sql.py`, `test_langgraph_parity.py` unmodified (row 21); confirm `src/chat_api/graph/nodes.py` neither imports nor invokes the tool layer (row 22).

## 5. Golden set and corpus fixtures (retrieval-eval)

- [x] 5.1 Author a synthetic corpus at `tests/fixtures/retrieval_eval/corpus.jsonl` (documents + chunks with stable `document_id` / `chunk_index`) and record its provenance in a `README.md` beside it (row 26).
- [x] 5.2 Author `golden_set.jsonl` — 30–50 queries with graded judgments `{query_id, query, relevant: [{document_id, chunk_index, grade}], notes}`.
- [x] 5.3 Implement `src/shared/retrieval/eval/golden_set.py`: strict loader validating record shape and grade range (row 23), rejecting duplicate `query_id` (row 24), and cross-referencing every judgment against the corpus (row 25).
- [x] 5.4 Generate `embeddings.json` once via the opt-in live embedding path, tagged with the embedding model name, and commit it; implement the fixture embedding service that reads it and the model-name mismatch check (row 46).
- [x] 5.5 Tests in `tests/test_retrieval_eval.py` for loader validation, duplicate rejection, corpus cross-reference, and mismatch failure.

## 6. Metrics (retrieval-eval)

- [x] 6.1 Implement `src/shared/retrieval/eval/metrics.py` as pure functions over `(ranked_results, judgments, k)`: `recall_at_k`, `precision_at_k`, `mrr_at_k`, `ndcg_at_k` (graded gains, normalized against the ideal ranking), plus an aggregator that excludes zero-judgment queries and reports them as skipped.
- [x] 6.2 Unit tests (no infrastructure) in `tests/test_retrieval_metrics.py`: perfect ranking scores 1.0 (row 27), empty results score 0.0 without raising (row 28), rank sensitivity for MRR/nDCG but not recall (row 29), graded nDCG ordering (row 30), zero-judgment query excluded and reported skipped (row 31).
- [x] 6.3 Hand-verify `nDCG@5` for one graded fixture query against an independent calculation and record the check (Risk 5).

## 7. Eval runner, matrix, and report (retrieval-eval)

- [x] 7.1 Implement `src/shared/retrieval/eval/runner.py`: seed the corpus into a disposable test schema, build a `ToolContext` per configuration, and execute every golden-set query through the `search_documents` tool from the registry.
- [x] 7.2 Implement the configuration matrix — named configurations (dense-only, hybrid, hybrid+rerank, `top_k` / `rerank_candidate_count` variants) applied via `RetrievalConfig`, never by mutating global `settings`.
- [x] 7.3 Record per-query `ToolResult` errors and `degraded` flags; a failed query must not abort the run.
- [x] 7.4 Implement `src/shared/retrieval/eval/report.py`: JSON report with `run_timestamp`, `golden_set`, `query_count`, `configurations`, `per_query`, `aggregate` (stable, sorted keys), plus a Markdown summary that ranks configurations by `nDCG@5` and labels degraded configurations.
- [x] 7.5 Add `scripts/run_retrieval_eval.py` CLI (select golden set, configurations, `k`, output path, live-embeddings opt-in flag).
- [x] 7.6 Tests: spy-registry invocation count equals query count per configuration (row 32), failed query recorded not fatal (row 33), one aggregate block per configuration (row 34), global settings unchanged across configurations and reranking actually applied (row 35), per-query blocks keyed by `query_id` and aggregates reproducible from them (row 36), JSON report field completeness (row 37), Markdown summary ranking (row 38).
- [x] 7.7 Determinism tests: run with network disabled and assert no embedding provider call (row 44); run twice and assert identical aggregates (row 45).

## 8. Baseline and regression gate (retrieval-eval)

- [x] 8.1 Execute the full matrix, choose the default configuration, and commit its aggregate metrics as `tests/fixtures/retrieval_eval/baseline.json`.
- [x] 8.2 Implement the gate comparing a fresh run's aggregate `recall@5` and `nDCG@5` against the baseline with a configured tolerance; failure message names metric, baseline, and observed value.
- [x] 8.3 Refuse to source a baseline from a run whose configuration was flagged `degraded` (Risk 7).
- [x] 8.4 Register a pytest marker for the eval gate in `pytest.ini` and confirm the default `pytest` invocation neither executes the eval nor makes a database or embedding call (row 42).
- [x] 8.5 Tests in `tests/test_retrieval_eval_gate.py`: below-tolerance failure (row 39), within-tolerance pass (row 40), improvement passes and reports deltas (row 41), missing baseline fails with generation instructions (row 43).
- [x] 8.6 Set the tolerance from observed run-to-run variance across at least three consecutive runs; record the observed variance next to the baseline.

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 9.2 Collect functional evidence (test output / report excerpt / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register, including the offline-reranker degraded run and the tools-package SQL grep.
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (ADR-001, ADR-003, ADR-004, ADR-007).
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate retrieval-tools-and-eval --type change --strict` and confirm it exits clean before archive.
