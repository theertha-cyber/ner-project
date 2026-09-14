## 1. API contract changes

- [x] 1.1 Update `src/chat_api/api/v1/schemas.py` so the chat request/response path can carry attachment-bearing turns without breaking the existing text-only request shape.
- [x] 1.2 Update `src/chat_api/api/v1/chat.py` to create the conversation on first send and persist attachment metadata against that conversation id in the same request flow.
- [x] 1.3 Update the conversation fetch path in `src/chat_api/api/v1/chat.py` so attachments are only returned for the requested conversation.
- [x] 1.4 Add the alembic migration for `documents.conversation_id` (proposal Impact: "database migration for `documents.conversation_id`") and confirm `alembic upgrade head` applies it.

## 2. Regression coverage

- [x] 2.1 Add a test that first send with attachments creates the conversation and persists attachment metadata.
- [x] 2.2 Add a test that opening a different conversation does not return another conversation's attachments.
- [x] 2.3 Add a test that message sends with no attachments still use the existing text-only path.

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — one entry per row in verification.md § Evidence Log.
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (automated sign-off — human sign-off waived).
- [x] 3.6 Run `openspec validate cap-3-conversation-scoped-attachment-persistence --type change --strict` before archive.
