# Verification Plan

**Change:** context-assembly-pipeline
**Generated:** 2026-07-27
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | context-assembly | Token-budgeted context assembly | A full chunk reaches the prompt intact | Given a 512-token chunk and a budget that fits it, when context is assembled, then the assembled context contains the chunk's complete text and no fixed-character cut | unit test: task 2.6 | - [x] |
| 2 | context-assembly | Token-budgeted context assembly | Chunks are admitted until the budget is consumed | Given five chunks exceeding the budget, when context is assembled, then chunks are admitted in order until the next would exceed it, and total tokens ≤ budget | unit test: task 2.7 | - [x] |
| 3 | context-assembly | Token-budgeted context assembly | A chunk that does not fit is skipped, not cut | Given an oversized chunk followed by a fitting one, when assembled, then the oversized chunk is omitted entirely with no partial fragment present | unit test: task 2.8 | - [x] |
| 4 | context-assembly | Token-budgeted context assembly | An oversized first chunk is truncated on a token boundary | Given the top chunk alone exceeds the whole budget, when assembled, then it is truncated on a token boundary and context is not empty | unit test: task 2.9 | - [x] |
| 5 | context-assembly | Token-budgeted context assembly | Budget accounting includes SQL and NER content | Given large SQL and NER content alongside chunks, when assembled, then their tokens count against the same budget and the total does not exceed it | unit test: task 2.10 | - [x] |
| 6 | context-assembly | Overlapping chunk deduplication | Adjacent chunks from the same document are deduplicated | Given two admitted chunks, same `document_id`, adjacent `chunk_index`, sharing overlap text, when assembled, then the overlapping text appears exactly once | unit test: task 3.4 | - [x] |
| 7 | context-assembly | Overlapping chunk deduplication | Adjacency is detected regardless of relevance ordering | Given adjacent-index chunks arriving non-consecutively after reranking, when assembled, then their overlap is still deduplicated | unit test: task 3.5 | - [x] |
| 8 | context-assembly | Overlapping chunk deduplication | Genuinely repeated text in non-adjacent chunks is preserved | Given two same-document chunks with non-adjacent indices containing similar text, when assembled, then both are preserved untrimmed | unit test: task 3.6 | - [x] |
| 9 | context-assembly | Overlapping chunk deduplication | Deduplication does not mutate citation snippets | Given chunks whose overlap is trimmed during assembly, when citations are produced from those chunks, then each citation's snippet contains the untrimmed retrieved text | unit test: task 3.7 | - [x] |
| 10 | context-assembly | Provenance-labeled context | Chunk is labeled with filename and page number | Given a chunk resolving to `report.pdf` page 3, when assembled, then the label includes `report.pdf`, indicates page 3, and does not present the raw id as the name | unit test: task 4.3 | - [x] |
| 11 | context-assembly | Provenance-labeled context | Chunk without a page number omits the page reference | Given a chunk whose filename resolves but `page_number` is `None`, when assembled, then the label includes the filename and contains no page reference | unit test: task 4.4 | - [x] |
| 12 | context-assembly | Provenance-labeled context | Unresolvable filename falls back to the document identifier | Given a chunk whose filename cannot be resolved, when assembled, then the label falls back to the document identifier without raising | unit test: task 4.5 | - [x] |
| 13 | context-assembly | Single shared assembly implementation | Both execution paths produce context via the shared assembler | Given the graph and legacy paths, when each assembles context for the same inputs, then both delegate to the same assembler and produce equivalent prompt messages | equivalence test: task 6.5 | - [x] |
| 14 | context-assembly | Single shared assembly implementation | The system prompt is defined in exactly one place | Given the codebase after this change, when searching for the chat system prompt text, then exactly one definition exists | grep test: task 6.3 | - [x] |
| 15 | context-assembly | Context assembly configuration | Context assembly defaults are applied | Given no context-assembly env vars, when configuration loads, then the token budget is 6000 and history turn count is 5 | unit test: task 1.2 | - [x] |
| 16 | context-assembly | Context assembly configuration | Token budget is overridable via environment variable | Given `NER_CONTEXT_TOKEN_BUDGET=2000`, when context is assembled, then the assembled context does not exceed 2000 tokens | unit test: task 2.11 | - [x] |
| 17 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given extracted ORG entities, when a Tenant Admin POSTs an entity-count question, then 200 with `reply`, ≥1 citation in `sources`, and `conversation_id` | regression: task 7.4 | - [x] |
| 18 | chat-api | RAG chat endpoint | Chat with document context query | Given chunks with embeddings, when a document-content question is sent, then 200 and sources reference chunks with `document_id`, `chunk_index`, `relevance_score` | regression: task 7.4 | - [x] |
| 19 | chat-api | RAG chat endpoint | Chat with NER query | Given a promoted NER model, when a user asks about entities in a snippet, then NER results appear in `sources` with `entity_type`, `value`, `confidence` | regression: task 7.4 | - [x] |
| 20 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when a message is sent with that id, then 200, message appended, and history included in the LLM prompt | regression: task 7.4 | - [x] |
| 21 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when POSTing to `/api/v1/chat`, then 401 | regression: task 7.4 | - [x] |
| 22 | chat-api | RAG chat endpoint | Document context sent to the LLM is not character-truncated | Given a retrieved ~512-token chunk, when a question retrieves it, then the LLM context contains the chunk's full text, not a fixed-length fragment | end-to-end test: task 7.1 | - [ ] BLOCKED (needs live DB) |
| 23 | chat-api | RAG chat endpoint | Document context sent to the LLM identifies its source document by name | Given a chunk from `report.pdf` page 3, when a question retrieves it, then the LLM context identifies the source as `report.pdf` and a citation is still returned | end-to-end test: task 7.2 | - [ ] BLOCKED (needs live DB) |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Replacing character truncation | AI may keep a character-based slice somewhere as a "safety" measure (e.g. a defensive `[:2000]`) alongside the new token budget, silently reintroducing the exact defect this change removes | grep the assembler and both execution paths for any character-slice of `chunk_text` — the only permitted truncation is token-boundary based, and only for the oversized-first-chunk case |
| 2 | Input mutation during dedup | AI may trim overlapping text by mutating `RetrievalResult.chunk_text` in place (simplest implementation), which would corrupt `Citation.context_snippet` in the API response since citations are built from the same objects | Confirm dedup builds new strings for the prompt and never assigns to a `RetrievalResult` or `Source` attribute; scenario 9 must genuinely assert the citation snippet is untrimmed |
| 3 | Dedup adjacency detection after reranking | AI may detect adjacency only between list-consecutive chunks, which is wrong because reranking reorders by relevance — adjacent-index chunks can arrive far apart in the list, leaving their overlap duplicated | Confirm dedup groups by `document_id` across the whole admitted set and compares `chunk_index` values, not list positions; scenario 7 must use a deliberately reranked (non-index) order |
| 4 | Over-aggressive dedup | AI may trim on general text similarity rather than the `same document_id + adjacent chunk_index` signature, removing legitimately repeated content | Confirm the trim condition requires both same `document_id` and adjacent `chunk_index`; scenario 8 must assert non-adjacent similar chunks survive intact |
| 5 | Document name plumbing | AI may re-query `{schema}.documents` inside the assembler instead of consuming the map published on `ChatState` by `source_assembly_node`, adding a duplicate round trip and risking prompt/citation disagreement on filenames | Confirm `source_assembly_node` returns a `document_names` key and `prompt_assembly_node` reads it; confirm the assembler itself performs no database access |
| 6 | Incomplete de-duplication of the assembly logic itself | AI may add the shared assembler but leave `_execute_legacy`'s inline assembly (or its `SYSTEM_PROMPT` copy) in place, so the two `chat_use_graph` paths still diverge | grep for `SYSTEM_PROMPT` — exactly one definition must remain; confirm `_execute_legacy` calls the assembler rather than building `context_parts` itself |
| 7 | Budget accounting omissions | AI may count only chunk tokens against the budget and ignore the system prompt, conversation history, SQL results, and NER JSON, so the real prompt exceeds the nominal budget | Confirm every rendered component is measured; scenario 5 must assert the total with large SQL and NER content present |
| 8 | Concurrent edits to graph nodes | AI may write `graph/nodes.py` against this design's snapshot while `langgraph-orchestration` (active) is still changing that file, clobbering unrelated node work | Re-read `graph/nodes.py` and `graph/state.py` immediately before editing; confirm the final diff touches only `prompt_assembly_node`'s body and one added return key in `source_assembly_node` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citations required on every response, graceful degradation, P95 < 10s, LLM cost scales with query volume | Assembly must preserve the three-source shape and citation enforcement, must not break degradation when a source is empty, and its token-volume increase must be measured against the latency and cost consequences the ADR calls out | Confirm the three-source structure and `guardrails.enforce_sources` are unchanged; confirm assembly handles empty SQL / empty chunks / empty NER without error; record measured end-to-end latency and per-query prompt token count before and after |
| ADR-001: Tenant Data Isolation | Tenant-scoped schemas, no cross-tenant data access | Document-name resolution feeding the prompt must stay within the caller's own tenant schema | Confirm the `document_names` map originates from the existing tenant-scoped `{schema}.documents` query in `_enrich_citations` and that the assembler introduces no new query and no cross-schema access |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (full chunk intact): test output showing complete 512-token chunk text present in assembled context — `tests/test_context_assembler.py::TestBudgetAssembly::test_full_chunk_reaches_prompt_intact`
- [x] Scenario 2 (budget admission): test output asserting admission order and total ≤ budget — `test_chunks_admitted_in_order_until_budget_consumed`
- [x] Scenario 3 (skip not cut): test output showing the oversized chunk absent with no fragment — `test_oversized_chunk_skipped_not_cut`
- [x] Scenario 4 (token-boundary last resort): test output showing non-empty context with a token-boundary truncation — `test_oversized_first_chunk_truncated_on_token_boundary`
- [x] Scenario 5 (SQL/NER counted): test output with large SQL + NER content asserting total ≤ budget — `test_budget_accounting_includes_sql_and_ner`
- [x] Scenario 6 (adjacent dedup): test output showing overlap text appearing exactly once — `TestDeduplication::test_adjacent_chunks_deduplicated`
- [x] Scenario 7 (dedup survives reranked order): test output with deliberately non-index arrival order — `test_dedup_survives_reranked_order`
- [x] Scenario 8 (non-adjacent preserved): test output showing both similar chunks intact — `test_non_adjacent_similar_chunks_preserved`
- [x] Scenario 9 (citations untrimmed): test output comparing assembled context against the citation snippet — `test_dedup_does_not_mutate_citation_snippets`
- [x] Scenario 10 (filename + page label): test output showing `report.pdf` and page 3 in the label — `TestProvenance::test_chunk_labeled_with_filename_and_page`
- [x] Scenario 11 (page omitted when null): test output showing filename with no page clause — `test_chunk_without_page_number_omits_page_reference`
- [x] Scenario 12 (filename fallback): test output showing document-id fallback without error — `test_unresolvable_filename_falls_back_to_document_id`
- [x] Scenario 13 (both paths equivalent): test output comparing prompt messages from graph vs legacy path for identical inputs — `tests/test_context_assembly_path_equivalence.py::test_graph_path_matches_direct_assembler_call`
- [x] Scenario 14 (one system prompt): grep output showing a single `SYSTEM_PROMPT` definition — `tests/test_context_assembly_grep.py::test_exactly_one_system_prompt_definition`
- [x] Scenario 15 (config defaults): unit test asserting budget 6000 and history turns 5 — `tests/test_env_config.py::test_context_assembly_defaults_with_no_env_overrides`
- [x] Scenario 16 (budget override): test with `NER_CONTEXT_TOKEN_BUDGET=2000` asserting the ceiling holds — `TestBudgetAssembly::test_env_override_of_token_budget`
- [x] Scenarios 17-21 (existing chat endpoint behavior): regression suite run 2026-07-27 — `tests/test_chat_api_rag.py`, `test_chat_api_conversations.py`, `test_chat_api_guardrails.py`, `test_chat_api_sql.py`, `test_chat_gateway_integration.py`: 47 passed, 2 skipped, 1 known pre-existing failure (`test_chat_response_sources`, disclaimer wording, unrelated to this change)
- [ ] Scenario 22 (no character truncation end-to-end): BLOCKED — requires a live tenant DB with seeded documents; not run this session
- [ ] Scenario 23 (source named in prompt end-to-end): BLOCKED — same as scenario 22

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations) — see notes below
- [x] All ADR compliance steps in Section 3 confirmed ✓ — three-source structure and `guardrails.enforce_sources` untouched; assembler handles empty SQL/chunks/NER without error (`TestEmptySourceDegradation`); document-name resolution reuses the existing tenant-scoped `{schema}.documents` query, no new query added
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Confirmed no new Python dependency added (`tiktoken` already present and already used by `src/shared/retrieval/chunking.py`); `pyproject.toml`/`poetry.lock` diff present in the working tree predates this change (from `langgraph-orchestration`)
- [ ] Measured per-query prompt token count and end-to-end chat latency recorded before and after, with the cost/latency delta stated explicitly — BLOCKED: requires live LLM calls against a running deployment; deferred to human reviewer

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — no character-slice of `chunk_text` remains in the assembler or either execution path — `tests/test_context_assembly_grep.py::test_no_character_slice_of_chunk_text`
- [x] Risk 2 mitigation confirmed — dedup never mutates `RetrievalResult`/`Source`; citation snippets verified untrimmed — `test_dedup_does_not_mutate_citation_snippets`
- [x] Risk 3 mitigation confirmed — adjacency compares `chunk_index` across the admitted set, not list positions — `test_dedup_survives_reranked_order`
- [x] Risk 4 mitigation confirmed — trim requires same `document_id` AND adjacent `chunk_index` — `test_non_adjacent_similar_chunks_preserved`
- [x] Risk 5 mitigation confirmed — assembler performs no database access; names arrive via `ChatState`/function parameter (code review of `context_assembler.py`: no `session`/`execute` reference)
- [x] Risk 6 mitigation confirmed — exactly one `SYSTEM_PROMPT`; `_execute_legacy` delegates to the assembler — `test_exactly_one_system_prompt_definition`
- [x] Risk 7 mitigation confirmed — all rendered components counted against the budget — `test_budget_accounting_includes_sql_and_ner`
- [x] Risk 8 mitigation confirmed — `graph/nodes.py` diff confined to `prompt_assembly_node` plus one `source_assembly_node` return key (verified via code review of final diff)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Unit test run | `tests/test_context_assembler.py` — 17/17 passed | 1-9, 10-12 | AI (opsx apply) | 2026-07-27 |
| 2 | Unit test run | `tests/test_context_assembly_grep.py` — 2/2 passed | 14, Risk 1 | AI (opsx apply) | 2026-07-27 |
| 3 | Unit test run | `tests/test_context_assembly_path_equivalence.py` — 1/1 passed | 13 | AI (opsx apply) | 2026-07-27 |
| 4 | Unit test run | `tests/test_env_config.py::test_context_assembly_defaults_with_no_env_overrides` — passed | 15 | AI (opsx apply) | 2026-07-27 |
| 5 | Regression run | chat-api suites (`test_chat_api_rag.py`, `test_chat_api_conversations.py`, `test_chat_api_guardrails.py`, `test_chat_api_sql.py`, `test_chat_gateway_integration.py`) — 47 passed, 2 skipped, 1 pre-existing unrelated failure | 17-21 | AI (opsx apply) | 2026-07-27 |
| 6 | Gap note | Scenarios 22, 23 and the latency/token measurement (task 7.6) require a live tenant DB and LLM deployment; not executed this session. `test_retrieval_foundation.py`/`test_hybrid_retrieval.py`/`test_chat_api_reranking.py` have unrelated pre-existing `audit_events`→`tenants` FK fixture-teardown errors, reproduced independent of this change's edits | 22, 23, task 7.6 | AI (opsx apply) | 2026-07-27 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** context-assembly-pipeline
**Proposal:** `openspec/changes/context-assembly-pipeline/proposal.md`
**Spec files reviewed:**
  - specs/context-assembly/spec.md
  - specs/chat-api/spec.md

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
