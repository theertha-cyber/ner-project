# Chat Attachment Upload — Technical Design

## Overview
Add attachment support to the chat composer without reserving a conversation until send time, keep retrieval scoped to the conversation that owns the files, preserve the tenant-wide Documents library, and extend the existing ingestion pipeline with CSV support.

## Background / Context
### Baseline findings
- Requirement baseline `docs/requirement/chat-attachment-upload.md` is approved and marks the run as ready for architecture.
- `PROJECT.md` defines the platform as a greenfield multi-tenant NER system with PostgreSQL, object storage, FastAPI, Next.js, and a separate Documents workflow.
- Governance baseline `baseline-policy.json` requires ADRs for persistence choices, integration style changes, and deployment topology decisions.
- Active customer overlay is empty (`customers/active.json` has `customerId: null`), so no extra architecture overlay applies.

### Codebase Discovery Findings
- `src/portal/src/components/chat/ChatInput.tsx:16-124` is text-only today; there is no attach control or file input.
- `src/portal/src/app/(auth)/chat/page.tsx:65-157,198-268,444-501` already manages conversation create/select/rename/delete and sends chat turns with `conversation_id`.
- `src/chat_api/api/v1/chat.py:69-110,113-161,268-388,444-501` creates conversations on first send, persists turns by conversation, and hard-deletes conversations/messages only.
- `src/portal/src/app/(auth)/documents/page.tsx:61-128` and `src/document_service/api/v1/documents.py:64-143` anchor uploads in the tenant Documents workflow, not chat.
- `src/document_service/ingestion/service.py:70-138` is the single ingest entry point; `src/document_service/services/ocr_worker.py:462-527` dispatches extraction by media type and currently has no CSV branch.
- `src/document_service/api/v1/documents.py:146-229` lists tenant documents independent of conversation context; preserving this behavior means chat attachments must be filtered out of that view.
- `src/document_service/services/ocr_worker.py:371-542` already purges derived data on reprocess/failure paths and releases working copies, which is the right cleanup pattern for hard-delete semantics.

## Goals
- Add a chat attachment affordance in the composer.
- Keep first attachment staging client-side so no conversation is reserved before send.
- Persist attachments conversation-scoped and retrieve them only within that conversation.
- Preserve tenant-wide Documents tab/library behavior unchanged.
- Hard-delete source files and derived artefacts when a conversation is deleted.
- Reuse the existing ingestion path and add CSV as a supported branch.

## Non-Goals
- No change to the tenant-wide Documents page UX.
- No resume/JD-specific modeling.
- No new vector store or alternate document service.
- No resumable upload protocol.

## Proposed Design
### Composer and conversation lifecycle
- `ChatInput` gains an attachment button, hidden file input, and staged attachment list.
- Attachment selection stays local in the chat page state; no server call is made on file pick.
- The first send request carries both message text and staged files, so the backend can create the conversation and persist attachments in the same turn.
- Existing conversations can accept additional attachments the same way, but still only when the user sends a message.

### Backend send contract
- Add a multipart chat turn endpoint alongside the existing JSON turn path so message text and files can be submitted together.
- The backend creates the conversation only if one does not already exist for the send, then stores the turn and attachment metadata atomically in the same request flow.
- Attachments are resolved by conversation id during retrieval; they are never surfaced by tenant-wide document listing.

### Data model / schema
- Add `conversation_id UUID NULL` to `documents`, indexed with tenant id.
- Use `conversation_id IS NOT NULL` to mark chat attachments and to exclude them from Documents library queries.
- Keep `documents` as the primary record so the existing ingestion, processing, and cleanup code paths remain reusable.
- Ensure `document_chunks` and `document_text_spans` are deleted when their parent document is hard-deleted.
- Conversation delete performs a full cleanup of linked blobs, derived artefacts, attachment rows, and conversation rows.

### Retrieval isolation
- Chat retrieval only joins documents whose `conversation_id` matches the active conversation.
- Attachment citations and any downstream RAG/context assembly use the conversation-scoped subset only.
- Tenant/user authorization remains unchanged; conversation ownership is still enforced before any data is loaded.

### CSV ingestion integration
- Extend `is_allowed_file()` and the upload API allow-list to include `.csv`.
- Add a CSV branch in `ocr_worker.py` that parses rows into normalized text spans, then feeds the same chunking/embedding path used for query documents.
- CSV attachments and CSV Documents uploads share the same ingestion branch; there is no separate CSV service.
- Query-purpose CSVs participate in retrieval; non-query CSVs stop after spans are stored, matching existing purpose behavior.

### Documents library preservation
- Documents list/search endpoints keep their current tenant and role filters, plus one extra exclusion: rows with `conversation_id` are hidden from the tenant-wide library.
- Existing Documents upload behavior remains unchanged for non-chat uploads.
- This keeps chat attachments discoverable only in the conversation UI while leaving the tenant library intact.

## Data Model / API Changes
- `documents.conversation_id` nullable FK to conversations.
- New multipart chat turn request shape for message + attachments.
- CSV file-type allow-list added to document ingestion.
- Conversation delete path extended to hard-delete linked documents and all derived artefacts.

## Non-Functional Requirements
| Category | Target | Measured how | Source (stated / clarified / inferred) |
| --- | --- | --- | --- |
| Security / compliance | No regulated-data handling workflow or special classification path is introduced by this feature | Review of new chat/upload code paths and tests confirming no classification-specific branches or fields | stated |
| Deletion completeness | After conversation deletion, linked source files, derived artefacts, and conversation records are unrecoverable through the product | Delete then verify 404 on conversation, empty attachment linkage, and absent blobs/spans/chunks | stated |
| Accessibility | Attachment control is keyboard reachable, has an accessible name, and keeps visible focus state | Manual keyboard check plus axe-core on the chat page | recommended |

## Testing Strategy
- Unit tests for attachment staging state and send payload construction.
- Integration tests for multipart chat send, conversation creation on first send, and conversation-scoped retrieval.
- Integration tests for conversation delete covering blobs, document rows, spans, and chunks.
- Regression tests ensuring Documents library queries still return only non-conversation documents.
- Parser tests for CSV ingestion and chunk generation.
- Accessibility check for keyboard operability and focus state on the composer.

## Rollout Plan
1. Land schema, ingestion, and delete-path changes behind code that is backward compatible with existing chat and Documents flows.
2. Enable the chat composer attachment UI after backend multipart handling is in place.
3. Verify Documents library regressions and conversation delete cleanup before release.
4. No phased rollout is required beyond the single deployment environment recorded in the deployment plan.

## Risks & Mitigations
- CSV row normalization may not match all downstream expectations; mitigate with parser tests and retrieval smoke tests.
- Hard-delete cleanup could leave orphaned blobs if a delete step fails; mitigate with fail-fast deletion and tests that verify both storage and DB cleanup.
- Documents library regressions could surface if the conversation filter is missed; mitigate with direct library regression coverage.

## Open Questions
None.
