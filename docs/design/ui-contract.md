# UI Design Package

## Source
Generated from the current application UI reference (existing portal screens/styles in `src/portal/src/app/globals.css` and related chat/documents components), aligned to `docs/requirement/chat-attachment-upload.md` and `docs/design/chat-attachment-upload.md`.

## Codebase Discovery Findings
- `src/portal/src/components/chat/ChatInput.tsx` is text-only today; the existing chat composer has no attachment control or file input.
- `src/portal/src/app/(auth)/chat/page.tsx` already owns conversation create/select/rename/delete and routes chat turns through `conversation_id`.
- `src/portal/src/app/(auth)/documents/page.tsx` and `src/document_service/api/v1/documents.py` keep the tenant Documents library separate from chat-scoped content.
- `src/document_service/ingestion/service.py` is the ingestion entry point, and `src/document_service/services/ocr_worker.py` currently has no CSV branch.
- The current portal palette and clean custom web style remain the approved visual baseline for this change.

## Design System
- Style: clean, customized to the current portal UI palette; chose it over bento (too dashboard/card-forward for this chat flow) and editorial (too reading-first for a product workspace).
- Platform: web
- Tokens: design-system/chat-attachment-upload/tokens.css
- Theme Entry Point: src/portal/src/app/globals.css

## Screens
| Screen | Route | Source reference |
| --- | --- | --- |
| Chat inbox | /chat | docs/design/mockup/chat-inbox.html |
| Chat conversation | /chat?conversation=<id> | docs/design/mockup/chat-thread.html |
| Documents library | /documents | docs/design/mockup/documents-library.html |

## Assets
None supplied.

## Standard-Rules Additions
- Added explicit empty, loading, and error states for the chat inbox list so the sidebar is never left undefined.
- Added attachment staging, keyboard handling, and send-disabled feedback for the chat composer.
- Added pagination range, search affordance, and empty/loading/error states for the Documents library table.
- Added focus-visible treatment and stable keyboard order for all interactive controls.

## Craft Bindings
- anti-ai-slop — always bound; prevents filler copy, emoji icons, and default-template styling.
- accessibility-baseline — always bound; covers contrast, focus, keyboard access, and labelling.
- state-coverage — always bound; this flow needs empty/loading/error states on both chat and documents views.
- animation-discipline — always bound; keeps motion subtle and interruptible.
- form-validation — bound because the chat composer, upload affordance, and document search are interactive input surfaces.
- typography-hierarchy — bound because the screens are content-bearing and rely on clear message/table hierarchy.

## Artifacts
- design-system/chat-attachment-upload/tokens.css
- src/portal/src/app/globals.css
- docs/design/ui-inventory.md
- docs/design/ui-contract.md
- docs/design/mockup/chat-inbox.html
- docs/design/mockup/chat-thread.html
- docs/design/mockup/documents-library.html

## Open Items
None.
