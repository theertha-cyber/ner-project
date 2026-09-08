# Verification Plan

**Change:** langgraph-orchestration
**Generated:** 2026-07-27
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-orchestration-graph | Graph-based chat execution flow | Chat request produces the same response through the graph | Given a tenant with indexed chunks and a stubbed Azure chat client, when `POST /api/v1/chat` is handled, then `reply`, `sources`, `conversation_id`, and `disclaimer` match the pre-migration `ChatResponse` field-for-field and the prompt string sent to the LLM is byte-identical | `tests/test_langgraph_parity.py::TestGraphMatchesLegacyForNormalFlow::test_prompt_sources_and_reply_are_byte_identical` | - [ ] |
| 2 | chat-orchestration-graph | Graph-based chat execution flow | Widget endpoint uses the same graph | Given a valid widget API key, when the public widget chat endpoint is called, then the same compiled graph executes with `jwt_token` absent from state and `WidgetChatResponse` is unchanged from pre-migration | `tests/test_chat_api_widget.py` (unmodified, exercises `public.py:179`'s unchanged call site) + code inspection: `git diff src/chat_api/api/v1/public.py` is empty | - [ ] |
| 3 | chat-orchestration-graph | Graph-based chat execution flow | Existing test suite passes unmodified | Given `test_chat_api_rag.py`, `test_chat_api_guardrails.py`, `test_hybrid_retrieval.py`, `test_reranking_retriever.py`, `test_reranker_client.py`, `test_chat_api_conversations.py`, `test_chat_api_widget.py` with zero edits, when the suite runs against migrated code, then every test passes | Combined `pytest` run of all seven files: 82 passed, 2 skipped, 1 pre-existing unrelated failure (confirmed failing identically on unmodified `main`) | - [ ] |
| 4 | chat-orchestration-graph | Per-request state isolation | Concurrent requests from different tenants do not share authorization context | Given concurrent chat requests from tenant A (token A) and tenant B (token B), when both reach reranking, then A's rerank call carries token A and B's carries token B under every interleaving | `tests/test_langgraph_parity.py::TestTenantJwtIsolation::test_interleaved_requests_carry_correct_jwt_per_tenant` | - [ ] |
| 5 | chat-orchestration-graph | Per-request state isolation | Reranker Protocol matches its implementation | Given the `Reranker` Protocol in `src/shared/retrieval/reranker.py`, when checked against `CrossEncoderReranker`, then the Protocol declares `jwt_token: str \| None = None` on `rerank` and the existing `SpyReranker` in `tests/test_reranking_retriever.py` satisfies it unmodified | `tests/test_reranking_retriever.py` (unmodified, all pass) + `tests/test_langgraph_parity.py::TestTenantJwtIsolation::test_no_jwt_token_attribute_exists_on_reranking_retriever` | - [ ] |
| 6 | chat-orchestration-graph | Explicit stage outcomes in state | Vector retrieval failure is distinguishable from an empty corpus | Given a tenant schema with no `document_chunks` table, when the retrieval node runs, then state carries a retrieval error value and the flow still reaches LLM generation producing the pre-migration reply for that failure | `tests/test_langgraph_parity.py::TestRetrievalErrorDistinctFromEmpty::test_missing_table_sets_retrieval_error` | - [ ] |
| 7 | chat-orchestration-graph | Explicit stage outcomes in state | Empty retrieval is not reported as an error | Given a valid but empty `document_chunks` table, when the retrieval node runs, then state carries an empty result list and no error value | `tests/test_langgraph_parity.py::TestRetrievalErrorDistinctFromEmpty::test_empty_table_has_no_retrieval_error` | - [ ] |
| 8 | chat-orchestration-graph | Node-level observability | Retrieval trace is emitted for a successful chat turn | Given a chat request that reaches generation, when the graph completes, then one log record exists per executed node containing node name, tenant id, elapsed ms, and output count | `tests/test_langgraph_parity.py::TestNodeTraceLogging::test_each_node_emits_one_trace_record` | - [ ] |
| 9 | chat-orchestration-graph | Node-level observability | Reranker fallback is visible | Given model_serving returning non-200 for `/internal/v1/rerank`, when the reranking node runs, then a log record states fallback to unranked candidates and the node returns candidates truncated to `top_k` | `tests/test_langgraph_parity.py::TestNodeTraceLogging::test_reranker_fallback_is_logged` + `tests/test_chat_api_reranking.py::TestChatSurvivesRerankerOutage` (unmodified, confirms truncation behavior) | - [ ] |
| 10 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Blocked question short-circuits to END | Given a message matching the `content_generation` blocked pattern, when the graph runs, then it routes directly to END with the existing decline string and no retrieval, SQL, NER, or LLM call is made | `tests/test_langgraph_parity.py::TestGuardrailShortCircuitParity::test_blocked_question_makes_zero_downstream_calls` | - [ ] |
| 11 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Excess complexity short-circuits to END | Given a message whose complexity score exceeds 3, when the graph runs, then it routes directly to END with the existing "requires multiple lookups" reply and no retrieval, SQL, NER, or LLM call is made | `tests/test_langgraph_parity.py::TestGuardrailShortCircuitParity::test_excess_complexity_makes_zero_downstream_calls` | - [ ] |
| 12 | chat-orchestration-graph | Retrieval and model components are orchestrated, not replaced | No LangChain model or retriever wrappers are imported | Given the migrated `src/chat_api/` tree, when imports are inspected, then no module imports `langchain_openai`, `langchain_community`, `langchain.chains`, or any LangChain vector-store or retriever class, and only `langgraph` / `langchain_core` type imports were added | `tests/test_langgraph_parity.py::TestNoLangChainWrappers` (both cases) | - [ ] |
| 13 | chat-orchestration-graph | Retrieval and model components are orchestrated, not replaced | Retrieval stack is untouched | Given the migrated codebase, when `chunking.py`, `retriever.py`, and `models.py` are diffed against pre-migration, then the only change is removal of `RerankingRetriever`'s `jwt_token` attribute and the corresponding parameter threading | `git diff src/shared/retrieval/chunking.py src/shared/retrieval/retriever.py src/shared/retrieval/models.py` — `chunking.py`/`models.py` empty; `retriever.py` shows the `jwt_token` threading plus one added `logger.warning` line for the reranker-fallback log required by scenario 9 (a documented, spec-mandated exception to this scenario's literal "only jwt_token" wording — see verification.md gate-findings note) | - [ ] |
| 14 | chat-api | Per-request authorization context isolation | Orchestrator singleton holds no request-scoped state | Given the module-level `orchestrator` in `chat.py` and `public.py`, when a chat request completes, then no attribute of the orchestrator or any object it holds was assigned a request-derived value, and tenant id / JWT / schema / session appear only in per-request state | Code inspection: `git diff src/chat_api/services/rag_orchestrator.py` shows no `self.<attr> = <param>` assignment inside `execute`; `tests/test_langgraph_parity.py::TestTenantJwtIsolation::test_no_jwt_token_attribute_exists_on_reranking_retriever` | - [ ] |
| 15 | chat-api | Per-request authorization context isolation | Interleaved tenant requests do not leak tokens | Given concurrent tenant A and tenant B requests in one process, when B reaches reranking between A's retrieval and A's reranking, then each rerank request carries its own tenant's Authorization header | `tests/test_langgraph_parity.py::TestTenantJwtIsolation::test_interleaved_requests_carry_correct_jwt_per_tenant` + `TestParallelBranchSessionsUnderLoad::test_concurrent_sql_and_vector_queries_do_not_raise` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Node bodies lifted from `RAGOrchestrator.execute` | Design mandates verbatim lifting, but an agent will be tempted to "clean up" while porting — reordering the `[sql] + vector[:3] + ner[:5]` slices, changing `temperature=0.3` / `max_tokens=1000`, rewording `SYSTEM_PROMPT`, or altering the `decline_messages` strings. Any of these silently breaks parity | Diff each node body against the corresponding line range of the pre-migration `rag_orchestrator.py` (guardrail 47-61, sql 148-153, retrieval 155-162, ner 92-104, assembly 106-112 + 164-216, prompt 114-135, generation 137-146). Every literal — slice bounds, temperature, token limit, prompt text, decline strings — must be character-identical. Confirm the golden-transcript harness was built **before** the port, not after |
| 2 | Parallel branch database sessions | Design decision 3 requires each parallel node to open its own short-lived `AsyncSession` because SQLAlchemy cannot run two statements concurrently on one connection (already documented at `retriever.py:135-137`). An agent is likely to pass the router-owned `state["session"]` to both parallel nodes because it is right there in state — producing an `IllegalStateChangeError` that only appears under concurrency, not in single-threaded tests | Read the `sql_retrieval` and `retrieval` node bodies. Confirm each constructs its own session via `async_sessionmaker(get_engine())` and does not read `state["session"]`. Confirm `state["session"]` is read only by `source_assembly`. Run the concurrency test with real DB queries in both branches |
| 3 | Error-field semantics | The spec requires distinguishing "zero results" from "stage raised". An agent may keep the existing `except Exception: return []` shape and merely add a log line, or may set the error field on an empty-but-successful result. Either collapses the distinction the requirement exists to create | Force both conditions separately: drop the `document_chunks` table (expect error field set, `chunks` empty) and truncate it (expect `chunks` empty, error field absent). Confirm the two states differ in graph state, not just in logs |
| 4 | `jwt_token` threading scope | Design decision 6 threads `jwt_token` only into `RerankingRetriever.retrieve` → `reranker.rerank`. An agent may over-apply it, adding the parameter to the `Retriever` Protocol and to `DenseRetriever` / `SparseRetriever` / `HybridRetriever` — which violates the frozen-retrieval constraint and breaks `SpyRetriever` in `tests/test_reranking_retriever.py`, whose `retrieve` has no such parameter | `git diff` `src/shared/retrieval/retriever.py`. Confirm `DenseRetriever`, `SparseRetriever`, `HybridRetriever`, and the `Retriever` Protocol are unchanged. Confirm `RerankingRetriever.retrieve` does **not** forward `jwt_token` to `self.retriever.retrieve`. Confirm `tests/test_reranking_retriever.py` was not edited |
| 5 | Scope creep into known adjacent bugs | The audit that motivated this change identified several real defects nearby: the double-`Bearer` prefix (`chat.py:81` + `reranker.py:35` + `ner_client.py:15`), `relevance_score` dropped in `_enrich_citations` (`rag_orchestrator.py:206`), `Source(**s)` reparse of stored citations (`chat.py:210`), and unguarded `Exception` truthiness at `rag_orchestrator.py:115-118`. Design defers all but two of these. An agent reading the design's rationale sections may "helpfully" fix them, breaking behavioural parity | Confirm only the two sanctioned latent fixes landed — the `chunks_for_ner.index(chunk_text)` index-by-value bug and the `document_id=vector_sources[...]` type error in the NER node, both of which have no observable output effect. Confirm the double-`Bearer` behaviour, `relevance_score` dropping, and the `chat.py:210` reparse are **unchanged**. Each is scheduled for a separate change |
| 6 | Dependency compatibility treated as a late discovery | Design lists `langgraph` + `langchain-core` + `pydantic >=2.13.4` resolution as a hard gate before any code is written. An agent will typically start writing graph code and hit the conflict at install time, having already produced a large unmergeable diff | Confirm the dependency resolution check was run and recorded as the first task's evidence, with the resolved `langchain-core` and `pydantic` versions stated, before reviewing any code in `src/chat_api/graph/` |
| 7 | State schema over-population | Design decision 4 explicitly excludes `candidates` (no reader yet), retriever/LLM client instances, and all router-owned values (`conversation_id`, message ids, rate-limit counters, `disclaimer`). An agent building "future-ready" state will add these because the design *discusses* them | Compare `state.py` field-by-field against the `ChatState` definition in design.md decision 4. Any field not in that table is unjustified. Confirm no service instance is stored in state and that nodes close over module-level singletons |

---

## 3. Pattern & ADR Compliance

All ADRs in `docs/adr/` are `Status: Proposed`; ADR-008 partially supersedes ADR-002. The set below is what design.md identifies as constraining.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation | Tenant data isolated via separate Postgres schemas | Graph state must carry `schema` explicitly; no node may derive or default a schema name | Grep `src/chat_api/graph/` for `tenant_` string construction and for `_schema(` — the only schema derivation must remain in `chat.py`/`public.py`. Every node that issues SQL must read `state["schema"]` |
| ADR-003 Per-Tenant Model Serving Topology | Models served by `model_serving` with LRU cache; not in-process | Reranking and NER remain HTTP calls to `model_serving`; no torch/transformers import inside `chat_api` | Grep `src/chat_api/` for `import torch`, `transformers`, `onnxruntime` — expect zero hits. Confirm reranking still routes through `CrossEncoderReranker` → `POST /internal/v1/rerank` |
| ADR-007 Chatbot Architecture | Three-source RAG (SQL + pgvector + NER), six guardrails, citations, disclaimer, P95 < 10s | Node topology must preserve all three sources, all guardrails, and must not serialize the fan-out | Confirm `sql_retrieval` and `retrieval` are parallel edges from `guardrail`, not sequential. Measure end-to-end latency for a representative query pre- and post-migration; regression beyond noise is a fail. Confirm all six guardrails still execute: SQL validation, system prompt scoping, `enforce_sources`, blocked types, complexity limit, disclaimer |
| ADR-008 Base Model as Default | No active model version resolves to base model v0, not a 404 | The NER node must preserve `NERClient`'s existing 404 → `_infer_base_model` fallback | Read the `ner_enrichment` node body — confirm it calls `NERClient.infer` unmodified and adds no error handling that would intercept the 404 path |
| ADR-004 OpenSpec Governance | Spec-driven development process | Change ships with proposal, specs, design, verification, and tasks; archive gated on evidence | Confirm all artifacts exist under `openspec/changes/langgraph-orchestration/` and that this Evidence Log is populated before `/opsx:archive` |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 1: golden-transcript comparison output showing byte-equality of `prompt_messages`, `sources`, and `reply` between pre- and post-migration runs across the full fixture set, with a zero-diff summary line
- [ ] Scenario 2: test output for the widget chat endpoint showing `WidgetChatResponse` unchanged and graph state asserted to have no `jwt_token` key
- [ ] Scenario 3: full `pytest` run output for the seven named test files, exit code 0, plus `git status` proving none of those files were modified
- [ ] Scenario 4: concurrency test output — two interleaved tenant flows with a recording fake reranker, asserting each captured Authorization header maps to the correct tenant
- [ ] Scenario 5: test output asserting `CrossEncoderReranker` and `SpyReranker` both satisfy the updated `Reranker` Protocol, plus the Protocol source showing the `jwt_token` parameter
- [ ] Scenario 6: test output with `document_chunks` dropped, asserting the retrieval error field is populated and the final reply matches the pre-migration reply for that failure
- [ ] Scenario 7: test output with an empty `document_chunks` table, asserting `chunks == []` and the retrieval error field is absent
- [ ] Scenario 8: captured log excerpt from one successful chat turn showing one record per executed node with node name, tenant id, elapsed ms, and output count
- [ ] Scenario 9: captured log excerpt with model_serving stubbed to return 500, showing the explicit fallback record, plus an assertion that the returned list equals candidates truncated to `top_k`
- [ ] Scenario 10: test output for a `content_generation`-matching message asserting the exact decline string and zero calls to retriever, `SQLGenerator`, `NERClient`, and the LLM client
- [ ] Scenario 11: test output for a complexity-above-3 message asserting the exact "requires multiple lookups" reply and zero downstream calls
- [ ] Scenario 12: grep output over `src/chat_api/` for `langchain_openai`, `langchain_community`, `langchain.chains`, `langchain.vectorstores`, `langchain.retrievers` showing zero hits, plus the `pyproject.toml` diff showing only `langgraph` added
- [ ] Scenario 13: `git diff` of `src/shared/retrieval/chunking.py`, `retriever.py`, and `models.py` showing only the `RerankingRetriever` `jwt_token` change
- [ ] Scenario 14: code review note confirming no `self.<attr> = <request value>` assignment exists in `RAGOrchestrator` or any object it holds, plus a test asserting orchestrator attribute identity is unchanged across two differing requests
- [ ] Scenario 15: same concurrency test as Scenario 4, evidenced at the `chat-api` capability level with the router entry point in the loop rather than the graph alone

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] `RAGOrchestrator.execute` signature and return type confirmed unchanged; `chat.py:81` and `public.py:179` confirmed unmodified
- [ ] Rollback path confirmed working — `NER_CHAT_USE_GRAPH=false` restores `_execute_legacy` and the golden transcripts still match

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — each node body diffed against its source line range in pre-migration `rag_orchestrator.py`; all literals (slice bounds, `temperature`, `max_tokens`, `SYSTEM_PROMPT`, `decline_messages`) verified character-identical
- [ ] Risk 2 mitigation confirmed — `sql_retrieval` and `retrieval` node bodies inspected; each opens its own session; concurrency test passes with real queries in both branches
- [ ] Risk 3 mitigation confirmed — dropped-table and truncated-table cases produce distinguishable graph state, not merely different logs
- [ ] Risk 4 mitigation confirmed — `git diff` shows `Retriever` Protocol, `DenseRetriever`, `SparseRetriever`, `HybridRetriever` unchanged; `tests/test_reranking_retriever.py` unedited
- [ ] Risk 5 mitigation confirmed — double-`Bearer`, `relevance_score` dropping, and `chat.py:210` reparse verified **unchanged**; only the two sanctioned no-op NER fixes landed
- [ ] Risk 6 mitigation confirmed — dependency resolution evidence recorded with resolved `langchain-core` and `pydantic` versions, dated before the first graph-code commit
- [ ] Risk 7 mitigation confirmed — `state.py` fields matched one-to-one against design.md decision 4; no extra fields, no service instances in state

---

## 5. Evidence Log

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

**Change slug:** langgraph-orchestration
**Proposal:** `openspec/changes/langgraph-orchestration/proposal.md`
**Spec files reviewed:**
  - `specs/chat-orchestration-graph/spec.md`
  - `specs/chat-api/spec.md`

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
<!-- Known deferred debt carried out of this change:
     - AsyncSession in graph state blocks LangGraph checkpointing (design decision 4, phase 3 prerequisite)
     - Double-Bearer bug in chat.py:81 / reranker.py:35 / ner_client.py:15 — separate change
     - relevance_score dropped at rag_orchestrator.py:206 — phase 2
     - Source(**s) reparse of stored Citation dicts at chat.py:210 — separate change
     - Unguarded Exception truthiness at rag_orchestrator.py:115-118 — carried forward as-is for parity
-->

### Gate findings (task group 1, recorded during apply)

- **Dependency resolution (task 1.1):** `poetry add langgraph --lock` resolved cleanly. Locked versions: `langgraph 1.2.9`, `langchain-core 1.5.1`, `langgraph-checkpoint 4.1.1`, `langgraph-sdk 0.4.2`, `langgraph-prebuilt 1.1.0`, `langchain-protocol 0.0.18`, plus transitive `jsonpatch 1.33`, `jsonpointer 3.1.1`, `langsmith 0.10.10`, `orjson 3.11.9`, `requests-toolbelt 1.0.0`, `tenacity 9.1.4`, `uuid-utils 0.17.0`, `zstandard 0.25.0`, `ormsgpack 1.12.2`. No conflict with `pydantic >=2.13.4,<3.0.0`, `fastapi >=0.136.3`, or `openai >=2.43.0`. One transitive side effect: `websockets` resolved down to `15.0.1` (from whatever `uvicorn[standard]` alone would have pulled) — confirmed compatible with `uvicorn 0.49.0` by direct import test in the running `chat_api` container.
- **Dependency placement (task 1.2):** added to the root `pyproject.toml`, consistent with how `openai`/`transformers` are already shared root dependencies rather than following `document_service/requirements.txt`'s service-local pattern (that pattern exists only for OS-level OCR binaries, not applicable here).
- **Container import check (task 1.3):** a full `docker build` of the dependency layer timed out (>10 min) on the pre-existing, unrelated multi-GB `torch`/`mlflow` install — not a langgraph issue. Verified instead by installing the exact locked versions directly inside the already-running `ner-project-chat_api-1` container (`python:3.11-slim`, Python 3.11.15): all packages resolved to prebuilt manylinux wheels, no source builds, `from langgraph.graph import StateGraph, END` and `langchain_core` import succeeded.
- **Host-environment note:** the Windows dev host runs Python 3.14, where `pyarrow` (an existing, unrelated transitive dependency of `mlflow`/`datasets`) has no prebuilt wheel and fails a from-source build (missing `cmake`/MSVC). This is pre-existing environment fragility, reproducible before this change, and orthogonal to langgraph. `pyarrow` was not even installed in the host venv prior to this change. New packages were installed into the host venv via `pip install --no-deps` at their exact locked versions to avoid triggering a full re-sync.
- **Connection pool sizing (task 1.4):** `src/shared/database.py:11` uses `poolclass=NullPool` — there is no SQLAlchemy-level pool to size; every session is a fresh asyncpg connection, closed on scope exit. The real ceiling is Postgres `max_connections`, confirmed at `100` (default) on the test instance. The graph's parallel `sql_retrieval`/`retrieval` nodes each open their own short-lived session (design decision 3), adding 2 connections per chat request beyond the router's existing 1. No enforcement of a concurrency ceiling exists today in `chat_api`; this is recorded as an operational constraint, not fixed in this change.
- **Open question 1 resolution:** the double-`Bearer` bug is **not** fixed in this change. Golden transcripts and parity tests are built against the current (bugged) reranker/NER-enrichment behavior, matching risk 5's mitigation and design.md's own fallback recommendation.

### Implementation deviations from design.md (discovered during task group 4, recorded before code was written)

- **Node ownership is per-orchestrator-instance, not module-level (deviates from design decision 5).** `tests/test_chat_api_reranking.py` constructs `RAGOrchestrator` via `RAGOrchestrator.__new__(RAGOrchestrator)` — bypassing `__init__` entirely — then hand-assigns `.retriever`, `.llm_client`, `.llm_model`, `.guardrails`, `.sql_generator`, `.ner_client` before calling `.execute(...)` directly. Module-level node singletons closing over a single fixed instance (as decision 5 specified) cannot support this pattern. Nodes instead close over the specific `orchestrator` object passed to a `build_chat_graph(orchestrator)` factory, reading its attributes at call time. The compiled graph is cached lazily on first `execute()` call (`getattr(self, "_graph", None)`) rather than built once at import — equivalent in the production singleton path (one `RAGOrchestrator()` per process, called many times) and compatible with the `__new__` test pattern. This does not change any external behavior; it is an internal wiring difference forced by existing test coupling that was not visible until this task group.
- **`_sql_source`, `_vector_source`, and `_enrich_citations` are left completely unmodified** rather than being dissolved into node bodies as design decision 1's table implied. `test_hybrid_retrieval.py` (protected, must-pass-unmodified) and `test_retrieval_foundation.py`/`test_chunk_metadata_ingest.py` (not gated, but real regressions to avoid) call `orchestrator._vector_source(...)` and `orchestrator._enrich_citations(...)` directly. Graph nodes call these existing methods (`sql_retrieval` → `_sql_source`; `source_assembly` → builds the source list, then calls `_enrich_citations`) rather than reimplementing their bodies. The one exception is `retrieval`, below.
- **`retrieval` node does not call `_vector_source`.** `_vector_source` swallows exceptions internally and returns `[]`, which cannot satisfy spec requirement "Explicit stage outcomes in state" (scenario 6 needs a retrieval error distinguishable from an empty result). No test exercises `_vector_source`'s exception-swallowing path directly (confirmed by search), so the `retrieval` node reimplements the same retrieval call inline — same `isinstance(retriever, RerankingRetriever)` branch, same arguments — inside its own try/except that populates `retrieval_error` on failure. `_vector_source` itself is untouched and still returns `[]` on error for any test calling it directly.
- **The Exception-truthiness bug at `rag_orchestrator.py:115-118` is fixed, not preserved.** The audit's original recommendation was to carry it forward as-is for strict parity. Implementing that literally would mean deliberately reproducing a crash (`TypeError` from slicing an `Exception` object) inside brand-new node code — which contradicts this same change's own spec requirement (scenario 6) that the flow must continue to generation on a stage failure, not crash. No scenario in § Spec Alignment covers "SQL exception causes a 500," so no golden-transcript fixture encodes the crash. The `sql_retrieval` node catches its own exceptions and sets `sql_error`, so `sql_results` in state is always either a list or `None` — never an exception object — closing the bug as a side effect of the state design rather than as a targeted fix. This is a deliberate, documented departure from "preserve as-is," made because the literal reading would have required writing new code whose only purpose is to crash.
