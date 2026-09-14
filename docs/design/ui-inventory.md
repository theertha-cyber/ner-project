# UI Inventory — Chat Attachment Upload

## Source
Generated mockups:
- `docs/design/mockup/chat-inbox.html`
- `docs/design/mockup/chat-thread.html`
- `docs/design/mockup/documents-library.html`

## Codebase Discovery Findings
- `src/portal/src/components/chat/ChatInput.tsx` is text-only today, so the composer inventory must include an attachment affordance addition.
- `src/portal/src/app/(auth)/chat/page.tsx` already manages conversation lifecycle and is the routing anchor for chat inbox versus thread states.
- `src/portal/src/app/(auth)/documents/page.tsx` and `src/document_service/api/v1/documents.py` preserve the tenant-wide Documents library as a separate surface.
- `src/document_service/ingestion/service.py` and `src/document_service/services/ocr_worker.py` show the ingestion path and confirm CSV is not yet a handled branch.
- The approved portal palette and clean custom web style remain unchanged from the installed design package.

## Navigation Model
Authenticated portal screens only. `/chat` opens the conversation inbox by default; selecting a conversation updates the URL to `/chat?conversation=<id>` and the browser back button returns to the inbox state. `/documents` remains the tenant-wide library and is separate from chat attachments. All screens sit behind the existing auth gate; unauthenticated users land on the login flow.

## Screens

### SCR-1 — Chat inbox
- **Route:** /chat
- **Purpose:** Browse conversations and open one for attachment-scoped chat.
- **Source reference:** docs/design/mockup/chat-inbox.html
- **Components:** CMP-1, CMP-2, CMP-3
- **States:** empty, loading, error, partial
- **Collection controls:** Fixed-height sidebar list with internal vertical scroll; no pagination controls.
- **Data:** conversation list, create conversation, rename conversation, delete conversation.

### SCR-2 — Chat conversation
- **Route:** /chat?conversation=<id>
- **Purpose:** Send chat messages and stage attachments before send.
- **Source reference:** docs/design/mockup/chat-thread.html
- **Components:** CMP-1, CMP-4, CMP-5, CMP-6
- **States:** empty, loading, error, partial, offline
- **Collection controls:** Message thread scrolls vertically; no paging, newest content stays at bottom.
- **Data:** conversation messages, staged attachments, send state, attachment retrieval scoped to the active conversation.

### SCR-3 — Documents library
- **Route:** /documents
- **Purpose:** Preserve the tenant-wide document library and existing upload flow.
- **Source reference:** docs/design/mockup/documents-library.html
- **Components:** CMP-7, CMP-8, CMP-9, CMP-10
- **States:** empty, loading, error, partial
- **Collection controls:** Numbered pagination, 25 items per page, search resets to page 1, status filter persists in the URL.
- **Data:** tenant document list, search term, status filter, upload action.

## Components

### CMP-1 — Conversation list item
- **Used on:** SCR-1, SCR-2
- **Variants:** active, inactive, truncated title
- **States:** default, hover, focus, active, loading, disabled
- **Source reference:** docs/design/mockup/chat-inbox.html

### CMP-2 — New conversation action
- **Used on:** SCR-1
- **Variants:** primary button
- **States:** default, hover, focus, disabled, loading
- **Source reference:** docs/design/mockup/chat-inbox.html

### CMP-3 — Conversation management controls
- **Used on:** SCR-1
- **Variants:** rename, delete
- **States:** default, hover, focus, destructive
- **Source reference:** docs/design/mockup/chat-inbox.html

### CMP-4 — Message thread
- **Used on:** SCR-2
- **Variants:** user, assistant, thinking, error
- **States:** empty, loading, partial, offline
- **Source reference:** docs/design/mockup/chat-thread.html

### CMP-5 — Chat composer
- **Used on:** SCR-2
- **Variants:** single-line, multiline, sending
- **States:** default, focus, disabled, loading
- **Source reference:** docs/design/mockup/chat-thread.html

### CMP-6 — Attachment staging tray
- **Used on:** SCR-2
- **Variants:** idle, one file, many files
- **States:** default, loading, error, disabled
- **Source reference:** docs/design/mockup/chat-thread.html

### CMP-7 — Status filter tabs
- **Used on:** SCR-3
- **Variants:** all, pending, processing, processed, failed
- **States:** default, hover, focus, active
- **Source reference:** docs/design/mockup/documents-library.html

### CMP-8 — Search field
- **Used on:** SCR-3
- **Variants:** empty, typed
- **States:** default, focus, disabled, error
- **Source reference:** docs/design/mockup/documents-library.html

### CMP-9 — Documents table row
- **Used on:** SCR-3
- **Variants:** normal, deleting, deleted
- **States:** default, hover, focus, loading
- **Source reference:** docs/design/mockup/documents-library.html

### CMP-10 — Pagination controls
- **Used on:** SCR-3
- **Variants:** previous, next, disabled
- **States:** default, hover, focus, disabled
- **Source reference:** docs/design/mockup/documents-library.html

## Assets
None supplied.

## Standard-Rules Additions
| Item | Screen | Why it was added |
| --- | --- | --- |
| Empty inbox state | SCR-1 | The requirement names the chat entry point but does not specify the empty conversation case. |
| Loading inbox state | SCR-1 | The conversation list needs a visible fetch treatment. |
| Error inbox state | SCR-1 | The conversation list needs a recoverable failure state. |
| Attachment staging tray | SCR-2 | The requirement says attachments can be staged before send but does not define the preview state. |
| Send-disabled state | SCR-2 | Prevents accidental submits while the composer is busy or empty. |
| Empty thread state | SCR-2 | A conversation can open before any messages exist. |
| Loading thread state | SCR-2 | Message retrieval needs a skeleton treatment. |
| Error thread state | SCR-2 | Conversation retrieval must fail visibly and recoverably. |
| Search affordance | SCR-3 | The documents collection is searchable and needs a visible control. |
| Pagination range text | SCR-3 | The list can exceed one page and must state position in the set. |
| Empty documents state | SCR-3 | A blank library needs guidance, not a blank table. |
| Loading documents state | SCR-3 | The table needs skeleton rows while fetching. |
| Error documents state | SCR-3 | The library needs a recoverable failure state. |

## Gaps
None.
