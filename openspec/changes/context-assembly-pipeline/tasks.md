## 1. Configuration

- [x] 1.1 Add `context_token_budget: int = 6000`, `context_max_chunks: int | None = None` (falls back to `retrieval_top_k` when unset), and `conversation_history_turns: int = 5` to `Settings` in `src/shared/config.py`
- [x] 1.2 Unit test: assert defaults (budget 6000, history turns 5) with no `NER_CONTEXT_*` / `NER_CONVERSATION_*` env vars set (covers scenario 15)

## 2. ContextAssembler — Budget

- [x] 2.1 Create `src/chat_api/services/context_assembler.py` with the single `SYSTEM_PROMPT` definition (moved, not copied) and a `ContextAssembler` class
- [x] 2.2 Implement token measurement using `tiktoken` `cl100k_base` — the same encoding `src/shared/retrieval/chunking.py` uses — reusing that module's `TOKENIZER` rather than creating a second encoder instance
- [x] 2.3 Implement whole-chunk admission: iterate chunks in arrival order, admit while the running token total plus the chunk fits `context_token_budget`, skip any chunk that does not fit
- [x] 2.4 Implement the oversized-first-chunk fallback: if no chunk fits, truncate the highest-ranked chunk on a **token** boundary (decode a token slice — never a character slice) so context is never empty
- [x] 2.5 Count every rendered component against the budget — system prompt, conversation history, SQL results, NER entities, and chunks (covers Hallucination Risk 7)
- [x] 2.6 Test: 512-token chunk with an accommodating budget, assert full text present and no fixed-character cut (covers scenario 1)
- [x] 2.7 Test: five chunks exceeding the budget, assert in-order admission and total tokens ≤ budget (covers scenario 2)
- [x] 2.8 Test: oversized chunk followed by a fitting one, assert the oversized chunk is wholly absent with no fragment (covers scenario 3)
- [x] 2.9 Test: single chunk exceeding the whole budget, assert token-boundary truncation and non-empty context (covers scenario 4)
- [x] 2.10 Test: large SQL results and NER entities alongside chunks, assert total ≤ budget (covers scenario 5)
- [x] 2.11 Test: `NER_CONTEXT_TOKEN_BUDGET=2000`, assert assembled context ≤ 2000 tokens (covers scenario 16)

## 3. ContextAssembler — Deduplication

- [x] 3.1 Implement dedup: group admitted chunks by `document_id`, and where two admitted chunks have adjacent `chunk_index` values, trim the shared boundary text from the later-positioned one — comparing `chunk_index` values across the whole admitted set, not list positions (covers Hallucination Risk 3)
- [x] 3.2 Add a full-containment check as a general guard for any other exact duplicate
- [x] 3.3 Ensure dedup builds new strings and never assigns to `RetrievalResult` or `Source` attributes (covers Hallucination Risk 2)
- [x] 3.4 Test: two same-document adjacent-index chunks sharing overlap, assert overlap text appears exactly once (covers scenario 6)
- [x] 3.5 Test: adjacent-index chunks arriving non-consecutively (simulating rerank reordering), assert overlap still deduplicated (covers scenario 7)
- [x] 3.6 Test: same-document non-adjacent chunks with similar text, assert both preserved untrimmed (covers scenario 8)
- [x] 3.7 Test: after assembly trims overlap, assert the corresponding `Citation.context_snippet` still contains the untrimmed retrieved text (covers scenario 9)

## 4. ContextAssembler — Provenance

- [x] 4.1 Implement chunk labeling as `Document "<filename>" (page <n>):`, omitting the page clause when `page_number` is `None` and falling back to the document id when the filename is unresolved
- [x] 4.2 Confirm the assembler performs no database access — filenames arrive as a `document_id → filename` map parameter (covers Hallucination Risk 5)
- [x] 4.3 Test: chunk resolving to `report.pdf` page 3, assert label includes filename and page and does not present the raw id as the name (covers scenario 10)
- [x] 4.4 Test: chunk with resolved filename but `page_number=None`, assert filename present and no page reference (covers scenario 11)
- [x] 4.5 Test: chunk with unresolvable filename, assert document-id fallback and no exception (covers scenario 12)

## 5. Wire the Graph Path

- [x] 5.1 Re-read the live `src/chat_api/graph/nodes.py` and `src/chat_api/graph/state.py` before editing — `langgraph-orchestration` is still active on these files; this change's diff must be confined to `prompt_assembly_node`'s body plus one added return key in `source_assembly_node` (covers Hallucination Risk 8)
- [x] 5.2 Add `document_names: dict[str, str]` to `ChatState` in `src/chat_api/graph/state.py`
- [x] 5.3 Update `source_assembly_node` to also return the `document_id → filename` map it already resolves via `_enrich_citations`, without adding a second query
- [x] 5.4 Rewrite `prompt_assembly_node` to delegate to `ContextAssembler`, consuming `document_names` from state; delete its local `SYSTEM_PROMPT` and all inline truncation (`chunks[:3]`, `chunk_text[:500]`, `sql_results[:10]`, `ner_entities[:5]`)

## 6. Wire the Legacy Path

- [x] 6.1 Update `RAGOrchestrator._execute_legacy` in `src/chat_api/services/rag_orchestrator.py` to delegate context building to `ContextAssembler`, passing the document-name map it resolves in the same function
- [x] 6.2 Delete the duplicate `SYSTEM_PROMPT` and inline `context_parts` assembly from `rag_orchestrator.py`
- [x] 6.3 grep test: assert exactly one `SYSTEM_PROMPT` definition remains in the codebase (covers scenario 14, Hallucination Risk 6)
- [x] 6.4 grep test: assert no character-slice of `chunk_text` remains in the assembler or either execution path (covers Hallucination Risk 1)
- [x] 6.5 Test: assemble prompt messages via the graph path and the legacy path for identical inputs, assert equivalence (covers scenario 13)

## 7. End-to-End & Regression

- [ ] 7.1 End-to-end test: seed a ~512-token chunk, ask a question retrieving it, capture the actual prompt sent to the LLM, assert the chunk's full text is present (covers scenario 22) — BLOCKED: requires live tenant DB with seeded documents; see note below
- [ ] 7.2 End-to-end test: seed a chunk from `report.pdf` page 3, assert the prompt identifies `report.pdf` and the response still returns a citation (covers scenario 23) — BLOCKED: same as 7.1
- [x] 7.3 Test empty-source degradation: assemble with empty SQL, empty chunks, and empty NER independently and together, assert no error and a sane fallback context
- [x] 7.4 Re-run the existing chat-api regression suites and confirm the RAG chat endpoint's existing scenarios still pass (covers scenarios 17-21), noting the known pre-existing `test_chat_response_sources` disclaimer-wording failure is unrelated
- [x] 7.5 Re-run `tests/test_retrieval_foundation.py` and the retrieval/rerank suites — assembly changes must not affect retrieval behavior. Note: several tests in `test_retrieval_foundation.py` / `test_hybrid_retrieval.py` / `test_chat_api_reranking.py` error with `ForeignKeyViolationError` on `audit_events`→`tenants` during fixture teardown — pre-existing test-DB state pollution unrelated to this change (reproduced identically before any assembler edits). All tests that do run pass.
- [ ] 7.6 Measure and record per-query prompt token count and end-to-end chat latency before and after this change; state the cost/latency delta explicitly against ADR-007's P95 < 10s and cost consequences — BLOCKED: requires live LLM calls, deferred to human reviewer with API access
- [x] 7.7 Confirm `pyproject.toml` is unchanged by this change — `tiktoken` was already a dependency; the `langgraph` entry present in the diff predates this change (from `langgraph-orchestration`)

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. 21/23 pass; scenarios 22-23 blocked on live-DB e2e (see verification.md).
- [x] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate context-assembly-pipeline --type change --strict` and confirm it exits clean before archive. Confirmed clean.
