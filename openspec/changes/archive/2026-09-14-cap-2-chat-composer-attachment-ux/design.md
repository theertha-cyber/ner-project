## Context

The portal chat composer (`src/portal/src/components/chat/ChatInput.tsx`) is text-only: a textarea, a send button, and Enter-to-send. The chat page (`src/portal/src/app/(auth)/chat/page.tsx`) owns conversation selection, first-send conversation creation, and the streaming/non-streaming send paths, all serialized as JSON `{ message, conversation_id }`.

CAP-3 already landed the backend half of attachments: both `POST /api/v1/chat` and `POST /api/v1/chat/stream` accept a JSON `ChatRequest` whose optional `attachments` field carries `[{ filename, mime_type, file_size_bytes }]` and persist conversation-linked document rows at send time. CAP-4 extended the ingestion allow-list to include `.csv`, making the accepted file set `.pdf, .jpg, .jpeg, .png, .tif, .tiff, .doc, .docx, .csv`.

CAP-2 is the missing frontend half: staging files in the composer without reserving a conversation (FR-006), reviewing/removing them, and sending message + attachments in the same action (FR-001, FR-003). The UI reference is `SCR-2` (chat conversation), `CMP-5` (composer), `CMP-6` (staging tray) in `docs/design/ui-inventory.md` and `docs/design/mockup/chat-thread.html`. The UI contract binds anti-ai-slop, accessibility-baseline, state-coverage, animation-discipline, form-validation, and typography-hierarchy; all styling must come from `design-system/chat-attachment-upload/tokens.css`.

## Goals / Non-Goals

**Goals:**

- Let a user select one or more supported files in the composer and see them in a staged attachment tray, with per-file removal, before any send.
- Preserve the situation where staging alone never reserves or creates a conversation — no server call happens at file-pick time.
- Send the message and the staged attachments together in the same request, serialized to the live CAP-3 `ChatRequest.attachments` contract, on both streaming and non-streaming paths.
- Clear the tray on a successful send; keep staged files on a failed send.
- Keep the attachment control keyboard-operable with an accessible name and a visible focus state, and leave the existing text-only send behavior and send-disabled rule intact.

**Non-Goals:**

- No server-side persistence, blob upload, or retrieval of attachments (CAP-3/CAP-5 territory).
- No CSV parsing or ingestion (CAP-4 territory).
- No Documents-library filtering or hard-delete cleanup (CAP-5 territory).
- No in-thread rendering of sent attachments beyond what the conversation endpoint already returns (the mockup surfaces the composer tray only; the thread renders messages).
- No drag-and-drop or resumable upload protocol.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-011 | Chat attachments are conversation-owned `documents` rows; retrieval and deletion are conversation-scoped | The send payload's attachment association happens conversation-side at send time; nothing in this capability may create, reserve, or name a conversation before send |
| ADR-012 | CSV support is a branch in the existing ingestion pipeline | `.csv` is part of the accepted client file set; the composer must accept it like any other supported type |
| ADR-013 | Single-environment dev/local deployment with docker compose and recreate rollout | No deployment topology concerns for a portal component change; the portal stack is exercised as-is |

## Decisions

### Decision 1: Client-side staging with zero server calls at pick time

**Choice:** File selection is handled entirely in portal React state. `ChatInput` surfaces a hidden `<input type="file">`; the chat page owns a `File[]` queue; nothing is sent over the network until the user submits the message.

**Rationale:** FR-006 requires that opening the composer or staging the first attachment never reserves a conversation; requirement-baseline DEC-002 confirms no server-side placeholder until send. The CAP-3 backend contract only accepts attachments inside a chat turn, so there is no earlier server interaction to make anyway.

**Alternatives considered:**
- A staging endpoint that uploads bytes early — ruled out: creates the very conversation/attachment reservation FR-006 forbids, and no such endpoint exists.
- localStorage/session persistence of staged files — ruled out: files in the queue are ephemeral by design; persistence would leak file bytes into browser storage for no requirement benefit.

### Decision 2: Serialize to the existing JSON `ChatRequest.attachments`, not new multipart form data

**Choice:** The page sends the same JSON body as today (`{ message, conversation_id }`) plus `attachments: [{ filename, mime_type, file_size_bytes }]` derived from the staged `File` objects.

**Rationale:** CAP-3 already defined and shipped this contract on both `/api/v1/chat` and `/api/v1/chat/stream` (`AttachmentInput`). The decomposition's "multipart send interaction" describes message-and-files-in-one-action semantically; the live wire contract is JSON. Reusing it means the portal needs no new endpoint and remains compatible with the archived CAP-3 tests.

**Alternatives considered:**
- A genuine `multipart/form-data` send with file bytes — ruled out: the backend does not accept it; CAP-3 persists attachment metadata rows only. Inventing a byte-upload path would violate the archived backend spec and silently diverge from the conversation-scoped contract.
- A separate attachment endpoint called before the turn — ruled out: same reservation problem as Decision 1.

### Decision 3: `ChatInput` stays presentational; the page owns the queue

**Choice:** `ChatInput` gains an `onAttach(files: File[])` callback, a `stagedFiles: StagedFile[]` prop (id, name, size, type), and an `onRemoveFile(id)` callback. The chat page holds the authoritative `File[]` state and feeds it into `handleSendMessage`.

**Rationale:** The decomposition assigns queue ownership to `chat/page.tsx` ("owns the temporary attachment queue"), where the send flow already lives. Keeping `ChatInput` presentational makes staging testable in isolation and keeps the tray renderable from one source of truth.

**Alternatives considered:**
- `ChatInput` owns the files and passes them through `onSend(text, files)` — ruled out: the send path and the optimistic message lifecycle live in the page; splitting state between the two makes "clear on success / preserve on failure" awkward to coordinate.

### Decision 4: Client accept set mirrors the backend allow-list, including CSV

**Choice:** The hidden input `accept` is `.pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.csv`, and selection is checked against that extension set before staging; an unsupported file is rejected with an inline message naming the allowed set.

**Rationale:** FR-002 defines the accepted set as "current upload flow types plus CSV"; ADR-012 confirms CSV; `ocr_worker.ALLOWED_EXTENSIONS` is the authoritative list this mirrors exactly. A client-side gate prevents a doomed send before it reaches the backend.

**Alternatives considered:**
- `accept` alone without a selection check — ruled out: `accept` is a hint, not an enforcement; a user can still pick an unsupported file, and the tray would show it as staged.
- A hardcoded subset — ruled out: drifts from the backend allow-list (the exact bug FR-002's "approved file set" exists to prevent).

### Decision 5: Clear the tray on success only, preserve on failure

**Choice:** After a successful send (stream `done` frame or non-stream 2xx), the page clears the staged queue. On any failure, the staged files remain in the tray.

**Rationale:** The requirement scenario says the tray clears after a successful send; state-coverage's error rule requires preserving user input across a failure — clearing staged files on an error would force the user to re-pick every file for a retry.

**Alternatives considered:**
- Always clear after a send attempt — ruled out: hostile on failure; a transient network error would silently discard user work.

### Decision 6: Styling exclusively from the installed token file

**Choice:** Every colour, radius, spacing, shadow and the focus-visible ring for the new control come from `design-system/chat-attachment-upload/tokens.css` (`--surface-3`, `--line`, `--primary`, `--ink-2`, `--good`, `--radius-pill`, `--focus-ring`, `--motion-fast`), resolved through the same CSS variables the current composer already uses.

**Rationale:** The UI contract loads the token file via `globals.css` and binds craft sections that forbid invented metrics, hardcoded color literals, and default-template styling. The mockup (`chat-thread.html`) shows the attach button as a circular icon button and the tray as pill-shaped file chips with a green status dot and muted hint text — all expressible from existing tokens.

**Alternatives considered:**
- New bespoke styles in the component — ruled out: violates the token-only rule and drifts from the approved visual baseline.

## Risks / Trade-offs

- [The backend persists attachment metadata only (per CAP-3); sending does not upload file bytes, so a user may expect the file to be retrievable as a document] → Mitigation: this capability stays strictly within the live contract; byte upload and retrieval are CAP-3/CAP-5 scope, recorded in the run report rather than invented here.
- [Client accept set and backend allow-list could drift apart over time] → Mitigation: the client set is defined in one constant mirroring `ALLOWED_EXTENSIONS`; the component test asserts the exact set so a future mismatch is caught.
- [Staged files are lost if the user navigates away before sending] → Mitigation: accepted and intended — the queue is explicitly temporary client-side state (FR-006); no persistence requirement exists.
- [A large file selection could make the send payload large] → Mitigation: the payload carries metadata only (name/type/size), so payload growth is bounded by the number of files, not their bytes.

## Migration Plan

The change is additive: `ChatInput` keeps its textarea and send button, gaining an attach button and tray; the text-only send path (message without attachments) is byte-for-byte the same request as today. Deploy as part of the portal with the rest of the attachment increment (CAP-3/CAP-4 are already merged). Rollback is a revert of the portal component/page change; no schema, API, or data migration is involved.

## Open Questions

None. No in-force ADR needs revisiting — CAP-2 adds no new decision class requiring an ADR of its own (the lifecycle decisions belong to CAP-3's ADR-011, which already exists).