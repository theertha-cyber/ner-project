## Why

Retrieval quality is now the product's main lever — hybrid search (`HybridRetriever`, RRF) and cross-encoder reranking (`RerankingRetriever`) both landed, and `agentic-retrieval-loop` is next — yet there is no way to answer "did that make retrieval better?" Every retrieval change to date has been justified by argument, not measurement: the existing tests (`test_hybrid_retrieval.py`, `test_reranking_retriever.py`) assert mechanics (RRF fuses, fallback returns candidates) and say nothing about whether the right chunk comes back for a real question. Tuning `retrieval_top_k`, `rerank_candidate_count`, `RRF_K`, or the reranker model is currently blind.

The agentic loop makes this worse in two ways. It needs retrieval exposed as *tools* — named, self-describing, argument-validated units an LLM can choose between and call repeatedly — which today does not exist: `retrieval_node` (`src/chat_api/graph/nodes.py:87`) calls `retriever.retrieve` directly with a fixed signature and no tool contract. And it multiplies the number of retrieval calls per question, so an unmeasured regression gets amplified. Both the tool layer and the measurement harness are prerequisites for the agentic loop, and the harness is the natural first consumer of the tool layer.

## What Changes

- Add a retrieval **tool layer** in `src/shared/retrieval/tools/`: a `RetrievalTool` protocol (`name`, `description`, `args_schema`, `async call(args, context) -> ToolResult`), a `ToolResult` envelope carrying results plus execution metadata (latency, candidate counts, degraded flag, error), and a `ToolRegistry` for name-based lookup and schema export.
- Ship three tools over existing services — no new retrieval logic:
  - `search_documents` — wraps the configured `Retriever` (dense / hybrid / reranking, whatever is composed), returns `RetrievalResult` objects.
  - `search_entities` — wraps the extracted-entity SQL path (`RAGOrchestrator._sql_source` / `SQLGenerator`), returns structured entity rows.
  - `lookup_document` — metadata-filtered retrieval within a single `document_id` (uses the existing `metadata_filter` support), for follow-up questions scoped to one document.
- Tenant scoping is enforced **inside** each tool: `schema` and `tenant_id` arrive via a `ToolContext` the caller constructs from request state, never via LLM-supplied arguments. Tool argument schemas SHALL NOT expose `schema`, `tenant_id`, or `purpose`.
- Export tool JSON schemas in OpenAI/LangChain tool-calling format so `agentic-retrieval-loop` can bind them without reshaping.
- Add a retrieval **eval harness** in `src/shared/retrieval/eval/` plus a runner script: loads a versioned golden set, executes each query through the tool layer against a seeded tenant schema, computes `recall@k`, `MRR@k`, `nDCG@k`, and `precision@k` per query and aggregated, and emits a JSON + Markdown report.
- Add the golden set as a versioned JSONL fixture (`tests/fixtures/retrieval_eval/`): each record is `{query_id, query, relevant: [{document_id, chunk_index, grade}], notes}`, with a companion seed corpus so the set is reproducible in CI without production data. No LLM-as-judge in this change.
- Add a **config matrix** runner: the same golden set executed under named retrieval configurations (dense-only, hybrid, hybrid+rerank, varying `top_k` / `rerank_candidate_count`) producing a side-by-side comparison, so config choices become measured rather than asserted.
- Add a baseline-and-regression gate: a committed baseline metrics file and a pytest-marked eval run that fails when aggregate `recall@5` or `nDCG@5` drops more than a configured tolerance below baseline. Marked so it does not run in the default unit-test path.
- **No change to chat runtime behaviour.** The graph, `RAGOrchestrator`, prompt assembly, citations, and all HTTP contracts are untouched. The tool layer is additive and its only consumer in this change is the eval harness; wiring tools into the chat flow belongs to `agentic-retrieval-loop`.
- No new database migration. No new required Python dependency (metrics computed in-repo; no `ragas`/`trulens`).

## Capabilities

### New Capabilities

- `retrieval-tools`: the tool abstraction over retrieval — tool contract and result envelope, the three concrete tools, registry and schema export, tenant-scoping guarantees, and per-tool failure/degradation semantics.
- `retrieval-eval`: the measurement capability — golden-set format and provenance, metric definitions (`recall@k`, `MRR@k`, `nDCG@k`, `precision@k`), config-matrix execution, report format, baseline storage, and the regression-gate threshold behaviour.

### Modified Capabilities

- `retrieval-core`: gains a requirement that retrieval configuration (`retrieval_top_k`, `reranker_enabled`, `rerank_candidate_count`) be resolvable per retrieval call or per retriever instance, rather than read only from the process-global `settings` object. The eval matrix cannot compare configurations otherwise — today `RerankingRetriever.retrieve` reads `settings.reranker_enabled` directly (`src/shared/retrieval/retriever.py:178`), so varying it requires mutating global state across a test run. Existing defaults and behaviour are unchanged when no override is supplied.

## Impact

**Code**
- `src/shared/retrieval/tools/` (new) — `base.py` (`RetrievalTool` protocol, `ToolContext`, `ToolResult`), `document_tools.py`, `entity_tools.py`, `registry.py`, `schemas.py`.
- `src/shared/retrieval/eval/` (new) — `metrics.py`, `golden_set.py` (loader/validator), `runner.py` (config matrix execution), `report.py`.
- `src/shared/retrieval/retriever.py` — retrieval config resolved from an optional per-instance/per-call override before falling back to `settings`. No signature change for existing callers.
- `src/shared/retrieval/__init__.py` — exports for tools and eval entry points.
- `scripts/run_retrieval_eval.py` (new) — CLI entry point for local and CI runs.
- `src/chat_api/services/rag_orchestrator.py` — read-only reuse: `search_entities` calls the existing SQL source path. Refactored only if the SQL path cannot be invoked without an orchestrator instance.

**Fixtures and data**
- `tests/fixtures/retrieval_eval/golden_set.jsonl`, `corpus.jsonl` (seed documents/chunks), `baseline.json` (committed metrics baseline).
- `tests/test_retrieval_tools.py`, `tests/test_retrieval_eval.py` (new).

**Operational**
- The eval run needs a live Postgres + pgvector test database and an embedding backend; with reranking enabled it also needs `model_serving`. On CPU, a full matrix over a few dozen queries takes minutes, so the gate is opt-in per marker, not part of the default `pytest` run.

**Downstream**
- `agentic-retrieval-loop` consumes `ToolRegistry` and the exported schemas; this change fixes that interface ahead of it.

**Not in scope**: LLM-as-judge / answer-quality scoring, end-to-end chat response evaluation, tool wiring into the LangGraph flow, query rewriting, and any change to ingestion, chunking, or embeddings.

## Open Questions

1. **Golden-set corpus provenance.** The golden set needs documents whose content is stable and committable. Assumption: a small synthetic corpus written for this purpose (not tenant data, not copyrighted text), seeded into a test tenant schema by the runner — confirm synthetic is acceptable, or whether the set should instead be labeled against a specific real tenant's documents held outside the repo.
2. **Embeddings during eval.** Every eval run needs query embeddings. Assumption: cache embeddings for the fixed golden-set queries and corpus chunks in a committed vector file so runs are deterministic, offline, and free; live Azure embedding calls become an opt-in flag. Confirm — the alternative is per-run API cost and non-reproducible drift when the embedding model changes.
3. **Golden set size and grading scale.** Assumption: ~30–50 queries at first, graded binary (relevant / not) with the schema allowing graded relevance (0–3) so `nDCG` stays meaningful later. Confirm the initial labeling effort is acceptable.
4. **Where the regression gate runs.** Assumption: manual/CI-on-demand, not on every PR, because of the infrastructure it needs. Confirm whether it should block merges on retrieval-touching PRs.
5. **`search_entities` coupling to `RAGOrchestrator`.** The SQL entity path currently lives on the orchestrator, which belongs to `chat_api`, while the tool layer lives in `src/shared`. Assumption: extract the SQL retrieval call into a service the tool can call without importing `chat_api`; confirm that extraction is in scope here rather than deferred.
