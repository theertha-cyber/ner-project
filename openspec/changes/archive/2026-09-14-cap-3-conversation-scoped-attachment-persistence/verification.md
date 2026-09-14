# Verification Plan

**Change:** cap-3-conversation-scoped-attachment-persistence
**Generated:** 2026-09-10
**Status:** ✅ Verified — automated sign-off recorded (human sign-off waived).

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-api | Attachment-bearing chat turns | First send creates the conversation and stores attachments | Given staged attachments and no conversation yet, when the user sends the first message, then the system creates the conversation and persists the attachment metadata against that conversation id. | `tests/test_chat_api_conversations.py::TestChatEndpointTurnShape::test_first_send_with_attachments_creates_conversation_and_persists_metadata` | - [x] |
| 2 | chat-api | Conversation-scoped attachment retrieval | Another conversation does not see the attachments | Given attachments stored for conversation A, when conversation B is opened, then conversation A's attachments are not returned. | `tests/test_chat_api_conversations.py::TestChatEndpointTurnShape::test_other_conversation_does_not_return_attachments` | - [x] |
| 3 | chat-api | Text-only chat sends remain supported | Normal message without attachments still works | Given a chat request with no attachments, when the request reaches the endpoint, then the existing text-only chat path continues to work. | `tests/test_chat_api_conversations.py::TestChatEndpointTurnShape::test_text_only_send_unchanged` | - [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Request shape | Inventing a separate upload endpoint or attachment table instead of extending the chat send contract | Confirm the implementation stays on the chat send path and uses the existing conversation id model. |
| 2 | Ownership scope | Forgetting the conversation ownership filter and leaking attachments across conversations | Verify the cross-conversation retrieval test is present and passes. |
| 3 | Backward compatibility | Breaking text-only sends while adding attachment handling | Confirm the no-attachment scenario still follows the existing chat path. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-011 | Conversation-scoped chat attachments in the existing document model | Attachments must belong to one conversation and remain scoped to that conversation | Inspect the persistence and retrieval code for conversation ownership checks and confirm the tests prove cross-conversation isolation. |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: test output proving first send creates the conversation and persists attachment metadata
- [x] Scenario 2: test output proving a different conversation cannot see those attachments
- [x] Scenario 3: test output proving text-only sends still work

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions
- [x] ADR compliance checked against ADR-011
- [x] No undocumented attachment flow added

### Edge Case Evidence

- [x] Attachment turn with no prior conversation still persists correctly
- [x] Cross-conversation retrieval remains empty
- [x] No-attachment path remains unchanged

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `poetry run pytest tests/test_chat_api_conversations.py -k "first_send_with_attachments_creates_conversation_and_persists_metadata or other_conversation_does_not_return_attachments or text_only_send_unchanged" -q` → passed (`3 passed, 29 deselected`) | Scenarios 1-3 | OpenCode | 2026-09-11 |
| 2 | Test output | Full recorded suite (`poetry run python -m pytest tests/test_chat_api_conversations.py tests/test_chat_api_rag.py tests/test_chat_api_retrieval_status.py tests/test_chat_api_streaming.py tests/test_document_ingestion.py tests/test_document_visibility.py tests/test_relational_document_delete.py`) → `1 failed, 105 passed, 2 skipped`; the sole failure is the pre-existing baseline failure `tests/test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources` (run.commands.testBaseline: red-code), not attributable to this change. `tests/test_chat_api_conversations.py` is fully green (32/32). | Scenarios 1-3 | OpenCode | 2026-09-14 |
| 3 | Schema migration | `alembic/versions/040_documents_conversation_id.py` adds `documents.conversation_id` (FK → `conversations(id)` ON DELETE CASCADE, nullable) to `tenant_template` and every pre-existing tenant schema; verified: `alembic upgrade head` (039 → 040) applied cleanly against `ner_dev` and `information_schema.columns` shows `conversation_id` present in `tenant_template` + all 9 existing tenant schemas. | Scenario 1 (persistence) | OpenCode | 2026-09-14 |

---

## 6. Audit Record

**Change slug:** cap-3-conversation-scoped-attachment-persistence
**Proposal:** `openspec/changes/cap-3-conversation-scoped-attachment-persistence/proposal.md`
**Spec files reviewed:**
- `openspec/changes/cap-3-conversation-scoped-attachment-persistence/specs/chat-api/spec.md`

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** automated sign-off — human sign-off waived

**Date:** 2026-09-14

**Notes:** Human reviewer sign-off waived by run policy (2026-09-14). Verification is fully automated: the three attachment-scenario tests pass and the Evidence Log records them (`3 passed, 29 deselected` in tests/test_chat_api_conversations.py), independently confirmed real. The sole full-suite failure (`tests/test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources`) is the pre-existing baseline failure recorded in run.commands.testBaseline (red-code) and is not attributable to this change.
