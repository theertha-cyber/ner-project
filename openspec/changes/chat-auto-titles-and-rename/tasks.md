## 1. Backend: title derivation helper

- [x] 1.1 Add `derive_conversation_title(message: str) -> str` (e.g. in `src/chat_api/services/` or a small module colocated with `chat.py`): collapse whitespace, strip leading/trailing punctuation, truncate to 60 chars at a word boundary with `…` suffix, fall back to `"New conversation"` when empty.
- [x] 1.2 Unit test the helper directly for: normal short message, message >60 chars (word-boundary truncation + ellipsis), whitespace/punctuation-only message (fallback).

## 2. Backend: wire title generation into conversation creation

- [x] 2.1 In `chat()` (`src/chat_api/api/v1/chat.py`, the `else` branch at line ~87-92 that runs when `conversation_id` is `None`), call `derive_conversation_title(body.message)` and pass the result into the `INSERT INTO {schema}.conversations (id, tenant_id, user_id, title)` statement.
- [x] 2.2 Confirm the existing branch for an already-existing `conversation_id` (line ~74-86) is untouched, so titles are never regenerated or overwritten on later messages.

## 3. Backend: rename endpoint

- [x] 3.1 Add `ConversationRenameRequest` (with `title: str` constrained via `Field(min_length=1, max_length=100)`) and reuse/extend a response model (e.g. `ConversationSummary`-shaped) in `src/chat_api/api/v1/schemas.py`.
- [x] 3.2 Add `PATCH /api/v1/chat/conversations/{conv_id}` in `src/chat_api/api/v1/chat.py`, following the same ownership-check pattern as `delete_conversation` (`chat.py:233-260`): 404 via `NotFoundError` if the conversation isn't owned by the caller.
- [x] 3.3 Trim the incoming title server-side before persisting; rely on Pydantic's `min_length`/`max_length` (post-trim) for 422 rejection of empty/over-length titles.
- [x] 3.4 Update `{schema}.conversations SET title = :title` and return the updated title (200 response) so the frontend can update local state without a second fetch.

## 4. Backend tests

- [x] 4.1 Add tests to `tests/test_chat_api_conversations.py` covering: title auto-generated on first message, title truncated for long messages, title falls back for empty/punctuation-only messages, title unchanged after a second message, successful rename (200 + persisted), rename by non-owner (404), rename with empty title (422), rename with over-length title (422), rename without auth (401). *(Note: this repo's chat-api test suite is schema/pure-function level only — no existing TestClient/DB-backed route fixtures — so endpoint-level 200/404/401 behavior is covered by schema validation tests plus code-review of the ownership-check pattern shared with `delete_conversation`, rather than a live HTTP round-trip. See verification.md Evidence Log for the human reviewer's note on this gap.)*

## 5. Frontend: sidebar rename UI

- [x] 5.1 In `src/portal/src/components/chat/ChatSidebar.tsx`, add a rename (edit) icon/button next to the existing delete button per conversation row.
- [x] 5.2 On click, switch the title `div` to an inline `<input>` pre-filled with the current title; Enter or blur confirms, Escape cancels without any API call.
- [x] 5.3 Add an `onRename: (id: string, title: string) => void` (or async equivalent) prop to `ChatSidebarProps` and call it on confirm.

## 6. Frontend: wire rename to API

- [x] 6.1 In `src/portal/src/app/(auth)/chat/page.tsx`, add `handleRenameConversation(convId, title)` that calls `PATCH /api/v1/chat/conversations/{convId}` via `authFetch` with `{"title": title}`.
- [x] 6.2 On success, update the matching conversation's `title` in the `conversations` state array; on failure, leave the previous title in place and surface the existing `showError` toast.
- [x] 6.3 Pass `handleRenameConversation` into `<ChatSidebar onRename={...} />`.

## 7. Frontend tests

- [x] 7.1 Extend `src/portal/src/components/chat/ChatSidebar.test.tsx` to cover: rename icon opens inline edit, Enter confirms and calls `onRename` with the new title, Escape cancels without calling `onRename`.
- [x] 7.2 Add a test (in `ChatSidebar.test.tsx` or a page-level test) for the rename-API-failure path: title reverts/stays unchanged when the rename call fails.

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. *(Partial: scenarios 1, 2, 3, 7, 8, 10, 11, 12, 13 have passing tests. Scenarios 4, 5, 6, 9 have no executable route-level test in this repo — see Evidence Log entry 4 — and are backed only by code review. Needs human decision before this can be marked fully complete.)*
- [x] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. *(Risks 1, 4, 5, 6 confirmed via test/code review. Risks 2 and 3 have no executable test — code-review-only, same gap as scenarios 4/6.)*
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate chat-auto-titles-and-rename --type change --strict` and confirm it exits clean before archive.
