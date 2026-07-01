# Verification Plan

**Change:** chat-conversation-and-citations
**Generated:** 2026-06-30
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | Conversation creation endpoint | Create new empty conversation | Given authenticated user, when POST /api/v1/chat/conversations, then 201 + id + null title | `test_chat_api_conversations.py::test_create_conversation_success` | - [ ] |
| 2 | chat-api | Conversation creation endpoint | Create conversation without authentication | Given no JWT, when POST /api/v1/chat/conversations, then 401 | `test_chat_api_conversations.py::test_create_conversation_unauthorized` | - [ ] |
| 3 | chat-api | Citation model with document names | Chat response includes citations with document names | Given extracted entities in documents, when user asks about entities, then each source has document_name + entity_type + entity_value + confidence | `test_chat_api_rag.py::test_citation_includes_document_name` | - [ ] |
| 4 | chat-api | Citation model with document names | SQL aggregate query still returns citations | Given ORG entities across 5 docs, when user asks count, then reply includes count AND citations reference documents | `test_chat_api_rag.py::test_aggregate_query_returns_citations` | - [ ] |
| 5 | chat-api | RAG chat endpoint (modified) | Chat with simple entity count query | Given extracted ORG entities, when POST /chat with "How many organizations?", then 200 + reply + sources with document_name + conversation_id | `test_chat_api_rag.py::test_chat_with_citations` | - [ ] |
| 6 | chat-api | RAG chat endpoint (modified) | Chat with document context query | Given document chunks, when user asks about content, then sources include document_id + document_name + chunk_index + relevance_score | `test_chat_api_rag.py::test_document_chunk_sources_include_document_name` | - [ ] |
| 7 | chat-api | RAG chat endpoint (modified) | Chat with NER query | Given promoted NER model, when user asks about entities in snippet, then sources include entity_type + entity_value + confidence + document_name | `test_chat_api_rag.py::test_ner_sources_include_document_name` | - [ ] |
| 8 | chat-api | SQL query generation and validation (modified) | Valid SQL query includes document name | Given question about org entities, when SQL generated, then it SHOULD JOIN documents and include d.filename | `test_chat_api_sql.py::test_sql_generation_includes_document_name` | - [ ] |
| 9 | chat-ui | Citation card display | Assistant message shows citation cards | Given assistant message with 3 citations, when rendered, then each shows document_name + entity details as unified card | component test: `CitationCard.test.tsx` renders document name | - [ ] |
| 10 | chat-ui | Citation card display | Citation card expands to show context | Given citation with context_snippet, when user clicks toggle, then snippet revealed | component test: `CitationCard.test.tsx` expand toggle | - [ ] |
| 11 | chat-ui | Citation card display | Citation card without context snippet | Given citation without context_snippet, when rendered, then no expand toggle shown | component test: `CitationCard.test.tsx` no context | - [ ] |
| 12 | chat-ui | Conversation sidebar (modified) | New conversation button creates conversation via API | Given sidebar displayed, when click "New", then POST sent + new convo in sidebar + selected + input visible | component test: `ChatSidebar.test.tsx` API create + E2E test | - [ ] |
| 13 | chat-ui | Conversation sidebar (modified) | New conversation API fails | Given sidebar displayed, when API errors, then error shown + current convo unchanged | component test: `ChatSidebar.test.tsx` error state | - [ ] |
| 14 | chat-ui | Conversation sidebar (modified) | New conversation button shows loading state | Given button clicked, when API in flight, then button disabled with loading indicator | component test: `ChatSidebar.test.tsx` loading state | - [ ] |
| 15 | chat-ui | Message thread display (modified) | Send message and receive response | Given conversation selected, when user sends message, then optimistic update + loading + citations in response + auto-scroll | E2E test: chat flow with new conversation | - [ ] |
| 16 | chat-ui | Message thread display (modified) | Empty conversation state | Given new empty conversation, when displayed, then "Send a message to start" + input visible | component test: `ChatPage.test.tsx` empty state | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Citation model fields | AI may add fields not in spec (e.g., `source_url`, `verified_by`) or rename spec fields (`document_name` vs `doc_name`) | Cross-check the `Citation` model in code against the spec — every field must match exactly |
| 2 | Citation enrichment query | AI may write a query that fails for tenants with no documents, or fails to handle cross-schema JOIN between tenant schema and `public.entity_definitions` | Verify the enrichment query handles empty results gracefully and uses schema-qualified table names |
| 3 | Source backwards compatibility | AI may remove or modify the existing `Source` model when adding `Citation`, breaking the widget API | Verify `Source` model unchanged in `schemas.py` and widget endpoint still returns `Source[]` |
| 4 | New conversation loading state | AI may omit the disabled/loading state on the button during API call, leaving the user able to click multiple times creating duplicate conversations | Verify button has `disabled` prop bound to loading state; verify test for rapid double-click |
| 5 | SQL prompt update | AI may over-constrain the SQL prompt, causing the LLM to always JOIN documents even for non-entity queries (e.g., "list my documents"), potentially breaking queries | Verify prompt says "SHOULD" not "MUST" for the JOIN; verify non-entity queries still work |
| 6 | Empty conversation edge case | AI may not handle the case where conversation is created but user navigates away before sending a message — stale empty conversations accumulate | Verify there's a background job or admin mechanism to prune empty conversations (or design.md explicitly defers this) |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-007 | Chatbot Architecture with Full RAG and Guardrails | Every response must include sources; sources must be traceable to documents | Verify all chat responses include `sources` array; verify each source has `document_name` |
| ADR-004 | OpenSpec Spec-Driven Development Governance | All changes require spec delta, design, tasks, and verification artifacts | Verify all four artifacts exist in the change folder |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test: `test_create_conversation_success` — POST /api/v1/chat/conversations returns 201 + conversation id (covers #1)
- [ ] Test: `test_create_conversation_unauthorized` — POST without JWT returns 401 (covers #2)
- [ ] Test: `test_citation_includes_document_name` — Chat response sources have document_name set (covers #3, #5)
- [ ] Test: `test_aggregate_query_citations` — COUNT query returns citations referencing documents (covers #4)
- [ ] Test: `test_sql_prompt_includes_join` — Generated SQL contains d.filename for entity queries (covers #8)
- [ ] Test: `test_citation_card_renders_document_name` — CitationCard component renders document_name as heading (covers #9)
- [ ] Test: `test_citation_card_expands_context` — Clicking toggle reveals context_snippet (covers #10)
- [ ] Test: `test_citation_card_no_context` — Citation without context_snippet shows no toggle (covers #11)
- [ ] Test: `test_new_conversation_api_flow` — Clicking new creates conversation via API + shows input (covers #12, #16)
- [ ] Test: `test_new_conversation_api_error` — API error shows error + keeps current convo (covers #13)
- [ ] Test: `test_new_conversation_loading_state` — Button disabled during API call (covers #14)
- [ ] Test: `test_send_message_to_empty_conversation` — First message works with new API-created conversation (covers #15)
- [ ] API trace: Chat response JSON showing Citation model fields

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] `Source` model unchanged in `schemas.py` — widget API backwards compatible
- [ ] Citation enrichment query uses schema-qualified table names for cross-schema JOIN

### Edge Case Evidence

- [ ] Risk 1: Citation model field names match spec exactly — no invented fields
- [ ] Risk 2: Enrichment query handles empty document results gracefully
- [ ] Risk 3: Source model unchanged — widget endpoint test passes
- [ ] Risk 4: Double-click on new conversation button doesn't create duplicates
- [ ] Risk 5: Non-entity SQL queries (e.g., "list my documents") still work after prompt update
- [ ] Risk 6: Stale empty conversations are handled (or deferred in design.md)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |
| 11 | | | | | |
| 12 | | | | | |
| 13 | | | | | |
| 14 | | | | | |
| 15 | | | | | |
| 16 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** chat-conversation-and-citations
**Proposal:** `openspec/changes/chat-conversation-and-citations/proposal.md`
**Spec files reviewed:**
- specs/chat-api/spec.md
- specs/chat-ui/spec.md

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
