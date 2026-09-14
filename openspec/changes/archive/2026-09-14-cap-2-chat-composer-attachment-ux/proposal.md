## Why

The chat composer is text-only today: `ChatInput.tsx` renders a textarea and a send button, with no way to attach a supporting file to a conversation (FR-001). The backend contract for attachment-bearing turns is already live from CAP-3 (`ChatRequest.attachments`), so the missing piece is the composer UX that stages files client-side, lets the user review and remove them, and submits them together with the message — while never reserving a conversation before the user sends (FR-006).

## What Changes

- `ChatInput` gains an attachment button (accessible name, keyboard operable) that opens a hidden file input restricted to the approved file set: `.pdf, .jpg, .jpeg, .png, .tif, .tiff, .doc, .docx, .csv` (FR-002's client acceptance set).
- `ChatInput` renders a staged attachment tray above the send field showing each staged file's name with a remove control. Removing a file before send is supported.
- The chat page (`src/portal/src/app/(auth)/chat/page.tsx`) owns the temporary staged-attachment queue — client-side only, no server call on file pick, so no conversation is reserved until send (FR-006).
- The send flow passes the staged attachments together with the message in the same request, serialized as `{ filename, mime_type, file_size_bytes }` entries in the `attachments` field of the existing `ChatRequest` body (aligned with the CAP-3 backend contract).
- The staged attachment tray clears after a successful send; on a failed send the staged files are preserved so the user does not lose them.
- The existing send-disabled behavior is preserved: the send control stays disabled while the composer is busy or the message is empty, and staged attachments alone never enable send when no text is present.

## Capabilities

### New Capabilities

- `chat-composer-attachments`: attachment staging in the chat composer, the staged attachment tray with per-file removal, and wiring staged files into the existing chat send payload (message + attachments in the same action).

### Modified Capabilities

<!-- The existing `chat-ui` spec's requirement "Send message and receive response" is
     unchanged for text-only sends; attachment staging is additive, not a change to an
     existing requirement, so no delta spec is produced. -->

## Impact

- `src/portal/src/components/chat/ChatInput.tsx` — attachment button, hidden file input, staged attachment tray, per-file remove, accessible naming, staged-file callback contract.
- `src/portal/src/app/(auth)/chat/page.tsx` — owns the staged-attachment queue, passes attachments into the streaming/non-streaming send body, clears the tray on success and preserves it on failure.
- New/updated portal tests: `src/portal/src/components/chat/ChatInput.test.tsx` (staging, removal, keyboard access, accepted file set) and `src/portal/src/app/(auth)/chat/page.test.tsx` (send payload carries attachments, tray clears on success).
- Backend: no change — the `ChatRequest.attachments` contract from CAP-3 is already live on `POST /api/v1/chat` and `POST /api/v1/chat/stream`.
- Styling comes from the installed theme file (`design-system/chat-attachment-upload/tokens.css`, loaded via `src/portal/src/app/globals.css`); no new colours, fonts or metrics are invented.

## Open Questions

None — the backend contract, the approved file set, and the UI reference (SCR-2, CMP-5, CMP-6 in `docs/design/ui-inventory.md`; `docs/design/mockup/chat-thread.html`) are all settled.