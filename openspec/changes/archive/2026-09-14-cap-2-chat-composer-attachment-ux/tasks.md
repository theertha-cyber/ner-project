## 1. ChatInput component — attachment staging surface

- [x] 1.1 Add an `ATTACH_ACCEPTED_EXTENSIONS` constant in `ChatInput.tsx` mirroring the backend allow-list: `.pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.csv` (FR-002 client acceptance set).
- [x] 1.2 Add a keyboard-operable attachment button to the composer shell with an accessible name (`aria-label="Attach a file"`), styled from tokens (`--surface`, `--line`, `--ink-2`, `--focus-ring`), left of the textarea.
- [x] 1.3 Add a hidden `<input type="file" multiple>` with the accept set; selecting files calls `onAttach(files)` with only supported files and shows an inline rejection message when any chosen file is unsupported (form-validation: inline, role="alert").
- [x] 1.4 Add a `stagedFiles` prop and render a staged attachment tray (aria-label="Staged attachments") with one chip per file — filename plus a per-file remove button exposing an accessible name identifying the file (`Remove <filename>`); tray placed inside the composer, between the shell and the bottom padding.
- [x] 1.5 Add an `onRemoveFile(id)` callback wired to each remove button; add a muted hint line in the tray: "Staging does not reserve the conversation until send." (matches mockup); style all tray elements from tokens (`--surface-3`, `--line`, `--good`, `--ink-2`, `--radius-pill`).
- [x] 1.6 Preserve the existing textarea/send layout and the send-enabled rule: the send control stays disabled when the message is empty even with staged files, and `disabled` prop still forces it off (send-disabled behavior unchanged).

## 2. Chat page — staged queue and send wiring

- [x] 2.1 Add a `stagedFiles: StagedFile[]` state queue to `ChatPageInner` (id, name, size, type) with `handleAttach(files)` (dedupe by name+size; cap at a sane bound) and `handleRemoveFile(id)`; pass `stagedFiles`, `onAttach`, `onRemoveFile` to `ChatInput`.
- [x] 2.2 Extend `handleSendMessage` to accept staged files and build the request body `{ message, conversation_id, attachments: [{ filename, mime_type, file_size_bytes }] }` from the queue — derived from `File` objects; send the same body on both the streaming (`/stream`) and non-streaming (`/api/v1/chat`) paths.
- [x] 2.3 On success (stream `done` frame / non-stream `resp.ok`), clear the staged queue; on failure, keep the queue intact (Decision 5).
- [x] 2.4 Fork the streaming/non-streaming send helpers to thread the attachments body through `handleSendMessageStreaming` / `handleSendMessageNonStreaming` without changing the text-only path's behavior when no files are staged.

## 3. Tests

- [x] 3.1 Create `src/portal/src/components/chat/ChatInput.test.tsx`: staging renders tray entries (Scenario 1), no network calls occur on staging (ADR-011/FR-006), removal leaves other files (Scenario 2), unsupported extension is rejected with an indication (Scenario 3), attach and remove buttons are accessible and keyboard operable (Scenario 6), send stays disabled with files-only and empty text (Scenario 7).
- [x] 3.2 Extend `src/portal/src/app/(auth)/chat/page.test.tsx`: send body carries `attachments` metadata entries on both streaming and non-streaming paths, tray clears after success (Scenario 4), tray preserved and error toast on failure (Scenario 5), no conversation/chat API call fires on file pick (ADR-011).
- [x] 3.3 Run `npm run typecheck --workspace=src/portal` and the portal test command; fix any failures introduced by this change.

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 4.2 Collect functional evidence (test output) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 4.5 Confirm verification.md § Verification Completion is satisfied — per run policy (human waiver in force for run `chat-attachment-upload-20260910`) no human Audit Record is required; automated evidence + passing suite suffices.
- [x] 4.6 Run `openspec validate cap-2-chat-composer-attachment-ux --strict` and confirm it exits clean before archive.