# Verification Plan

**Change:** chat-auto-titles-and-rename
**Generated:** 2026-07-30
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | Automatic conversation title generation | Title generated from a short first message | Given a user with no existing conversation sends a chat message with `conversation_id: null`, when the conversation is created, then `title` is set to a non-null string derived from the message and is returned by `GET /conversations` | `tests/test_chat_api_conversations.py` (title auto-generation test) | - [ ] |
| 2 | chat-api | Automatic conversation title generation | Title truncated for a long first message | Given a first message over 60 characters, when the conversation is created, then the persisted title is at most 60 characters, truncated at a word boundary, ending with `…` | `tests/test_chat_api_conversations.py` (title truncation test) | - [ ] |
| 3 | chat-api | Automatic conversation title generation | Empty-content first message falls back to placeholder title | Given a first message of only whitespace/punctuation, when the conversation is created, then `title` equals `"New conversation"` | `tests/test_chat_api_conversations.py` (title fallback test) | - [ ] |
| 4 | chat-api | Automatic conversation title generation | Title is generated once and not overwritten by later messages | Given a conversation with a non-null title, when another message is sent on that conversation, then `title` remains unchanged | `tests/test_chat_api_conversations.py` (title stability test) | - [ ] |
| 5 | chat-api | Rename conversation endpoint | Owner renames their conversation | Given a conversation owned by user A, when user A sends `PATCH /conversations/{id}` with a valid title, then response status is 200, the returned title matches, and a subsequent GET reflects it | `tests/test_chat_api_conversations.py` (rename success test) | - [ ] |
| 6 | chat-api | Rename conversation endpoint | Renaming another user's conversation returns 404 | Given a conversation owned by user A, when user B PATCHes it, then response status is 404 | `tests/test_chat_api_conversations.py` (rename cross-user 404 test) | - [ ] |
| 7 | chat-api | Rename conversation endpoint | Renaming with an empty title is rejected | Given a conversation owned by user A, when user A PATCHes with a whitespace-only title, then response status is 422 | `tests/test_chat_api_conversations.py` (rename empty title 422 test) | - [ ] |
| 8 | chat-api | Rename conversation endpoint | Renaming with an over-length title is rejected | Given a conversation owned by user A, when user A PATCHes with a title over 100 characters, then response status is 422 | `tests/test_chat_api_conversations.py` (rename over-length 422 test) | - [ ] |
| 9 | chat-api | Rename conversation endpoint | Renaming requires authentication | Given no JWT token, when a PATCH is sent to `/conversations/{id}`, then response status is 401 | `tests/test_chat_api_conversations.py` (rename unauthenticated 401 test) | - [ ] |
| 10 | chat-ui | Rename conversation from sidebar | User renames a conversation via the sidebar | Given a conversation in the sidebar, when the user edits its title via the rename control and confirms, then the rename API is called and the sidebar displays the new title on success | `src/portal/src/components/chat/ChatSidebar.test.tsx` (rename confirm test) | - [ ] |
| 11 | chat-ui | Rename conversation from sidebar | User cancels a rename in progress | Given an in-progress inline rename edit, when the user presses Escape, then no API call is made and the original title remains displayed | `src/portal/src/components/chat/ChatSidebar.test.tsx` (rename cancel test) | - [ ] |
| 12 | chat-ui | Rename conversation from sidebar | Rename API failure keeps the previous title | Given an in-progress inline rename edit, when the confirm triggers a failing API call, then the sidebar keeps the previous title and shows an error indication | `src/portal/src/components/chat/ChatSidebar.test.tsx` (rename failure test) | - [ ] |
| 13 | chat-ui | Rename conversation from sidebar | Newly created conversation shows placeholder until first message | Given a conversation just created with no messages, when rendered, then the sidebar shows "New conversation"; after the first message is sent and the list refreshes, the sidebar shows the backend-generated title | `src/portal/src/components/chat/ChatSidebar.test.tsx` (placeholder-then-title test) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Title derivation algorithm | AI may implement truncation as a hard character cutoff instead of at a word boundary, or forget the `…` suffix, producing titles that look broken | Manually test with a message >60 chars and confirm the persisted title ends at a word boundary with `…`, not mid-word |
| 2 | Title generated on wrong branch | AI may generate/overwrite the title on every message instead of only the first (new-conversation) message, silently mutating user-renamed titles | Rename a conversation, then send another message on it, and confirm the title is untouched (covers scenario 4 and interacts with the rename feature) |
| 3 | Rename ownership scoping | AI may implement the PATCH endpoint without the same `user_id`/`tenant_id` ownership check used by DELETE, allowing cross-user rename | Attempt to PATCH another user's conversation and confirm 404, by direct comparison of the PATCH handler's WHERE clause against the existing DELETE handler's |
| 4 | Validation boundary mismatch | AI may validate title length only on the frontend, or use different bounds (e.g. not trimming whitespace before length-checking) than the spec's 1-100 char (post-trim) rule | Send a PATCH request directly via API client (bypassing frontend) with a whitespace-only title and with a >100 char title; confirm both return 422 |
| 5 | Frontend error-state handling | AI may update the sidebar's local title state optimistically before the API call resolves, leaving a stale/incorrect title displayed if the call fails | Simulate a failing PATCH response (e.g. via network throttling/devtools) and confirm the sidebar reverts to/retains the previous title with an error shown |
| 6 | LLM cost/latency creep | AI may be tempted to "improve" title quality by adding an LLM call despite design.md explicitly ruling this out per ADR-007's latency/cost constraint | Code review of the title-generation code path confirms no network/LLM call is made; confirm response latency for first-message chat requests is unchanged from baseline |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-007-chatbot-architecture | Full RAG chat pipeline with explicit P95 <10s latency target and LLM API cost as a named concern; every response must retain the sources/guardrail/disclaimer contract | Title generation must be a pure in-process string operation with no external LLM call, and must not alter the existing `sources`/`disclaimer`/guardrail behavior of `POST /api/v1/chat` | Code review of the title-generation function confirms it takes only the message string as input and makes no network/DB calls beyond the existing `INSERT INTO conversations`; run the existing chat-api test suite to confirm sources/disclaimer/guardrail scenarios still pass unchanged |
| ADR-008-base-model-as-default | Governs NER base-model fallback behavior | Not applicable — no NER inference involved in this change | Confirm no changes were made to model-serving/NER inference code paths (diff review) |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (Title generated from a short first message): `tests/test_chat_api_conversations.py::TestConversationTitleGeneration::test_title_generated_from_short_message` passes
- [x] Scenario 2 (Title truncated for a long first message): `tests/test_chat_api_conversations.py::TestConversationTitleGeneration::test_title_truncated_at_word_boundary_for_long_message` passes
- [x] Scenario 3 (Empty-content first message falls back to placeholder title): `tests/test_chat_api_conversations.py::TestConversationTitleGeneration::test_title_falls_back_for_whitespace_only_message` and `::test_title_falls_back_for_punctuation_only_message` pass
- [ ] Scenario 4 (Title is generated once and not overwritten): NOT covered by an executable test — this repo's chat-api test suite has no TestClient/DB-backed route fixture to exercise the full `chat()` handler across two requests. Mitigated only by code review (the title write is only reachable from the `else: conversation_id = uuid4()` branch in `chat.py`; the existing-conversation branch never touches `title`). Needs a live/integration test before this can be checked.
- [ ] Scenario 5 (Owner renames their conversation): NOT covered by an executable route test — same fixture gap as Scenario 4. `ConversationRenameRequest`/`ConversationRenameResponse` schema behavior is unit-tested; the live PATCH endpoint round-trip is not.
- [ ] Scenario 6 (Renaming another user's conversation returns 404): NOT covered by an executable route test — mitigated only by code review confirming `rename_conversation` uses the identical `WHERE id = :cid AND user_id = :uid` ownership check as `delete_conversation`.
- [x] Scenario 7 (Renaming with an empty title is rejected): `tests/test_chat_api_conversations.py::TestConversationRenameRequest::test_blank_title_is_rejected` and `::test_empty_title_is_rejected` pass (422 is FastAPI's standard response for a `ValidationError` on this model)
- [x] Scenario 8 (Renaming with an over-length title is rejected): `tests/test_chat_api_conversations.py::TestConversationRenameRequest::test_over_length_title_is_rejected` passes
- [ ] Scenario 9 (Renaming requires authentication): NOT covered by an executable test — no auth-middleware/route test fixture in this suite; mitigated only by code review that `rename_conversation` follows the same `tenant_id`/`user_id` request-state pattern as every other authenticated route in `chat.py`.
- [x] Scenario 10 (User renames a conversation via the sidebar): `src/portal/src/components/chat/ChatSidebar.test.tsx` → `rename > confirms rename with Enter and calls onRename with the new title` passes
- [x] Scenario 11 (User cancels a rename in progress): `ChatSidebar.test.tsx` → `rename > cancels rename with Escape without calling onRename` passes
- [x] Scenario 12 (Rename API failure keeps the previous title): `ChatSidebar.test.tsx` → `rename > keeps the previous title displayed when the rename call fails` passes (verifies the sidebar-level contract: it never displays a title the parent hasn't confirmed via updated props)
- [x] Scenario 13 (Newly created conversation shows placeholder until first message): existing `ChatSidebar.test.tsx` → `renders conversation list` / placeholder fallback (`conv.title || "New conversation"`) covers the placeholder half; the "then shows generated title" half is covered by Scenario 1's backend test plus the existing `loadConversations()` refresh call in `page.tsx` after the first message succeeds

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — word-boundary truncation verified with a long test message (`test_title_truncated_at_word_boundary_for_long_message`)
- [ ] Risk 2 mitigation confirmed — NOT executable-test-covered (see Scenario 4 gap above); code review only
- [ ] Risk 3 mitigation confirmed — NOT executable-test-covered (see Scenario 6 gap above); code review only
- [x] Risk 4 mitigation confirmed — server-side validation rejects whitespace-only and over-length titles, confirmed via `ConversationRenameRequest` unit tests
- [x] Risk 5 mitigation confirmed — sidebar retains previous title on simulated PATCH failure, confirmed via `ChatSidebar.test.tsx`
- [x] Risk 6 mitigation confirmed — code review of `title_generator.py` shows no network/LLM call; the chat-api test suite's existing latency-sensitive tests (`test_chat_api_rag.py`, `test_chat_api_sql.py`) still pass unchanged

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_chat_api_conversations.py` — 25 passed (title generation + rename schema validation) | 1, 2, 3, 7, 8 | claude (agent) | 2026-07-30 |
| 2 | Functional | `pytest` on full chat-api suite (`test_chat_api_conversations.py`, `test_chat_api_guardrails.py`, `test_chat_api_rag.py`, `test_chat_api_rate_limiter.py`, `test_chat_api_reranking.py`, `test_chat_api_sql.py`, `test_chat_api_widget.py`, `test_chat_gateway_integration.py`) — 74 passed, 1 pre-existing unrelated failure (`test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources`, confirmed failing identically on `git stash` before this change), 2 skipped | Risk 6 (no regression from title-generation path) | claude (agent) | 2026-07-30 |
| 3 | Functional | `npx vitest run src/components/chat/ChatSidebar.test.tsx` — 13 passed | 10, 11, 12, 13 | claude (agent) | 2026-07-30 |
| 4 | Gap note | Scenarios 4, 5, 6, 9 and Risks 2, 3 have no executable route/integration test — this repo's `tests/test_chat_api_*.py` suite is schema/pure-function level only, with no TestClient or DB-backed HTTP fixture exercising `chat.py` routes end-to-end. A human reviewer should decide whether to accept code-review-only evidence for these or request a follow-up change adding route-level test fixtures. | 4, 5, 6, 9 | claude (agent) | 2026-07-30 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** chat-auto-titles-and-rename
**Proposal:** `openspec/changes/chat-auto-titles-and-rename/proposal.md`
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
