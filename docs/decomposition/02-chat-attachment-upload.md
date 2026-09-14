# Feature Decomposition: Chat Attachment Upload

**Format version:** 1
**Requirement:** docs/requirement/chat-attachment-upload.md

## Summary

Add chat composer attachment staging, conversation-scoped attachment persistence/retrieval, CSV support in the existing ingestion flow, and hard-delete cleanup that keeps the tenant-wide Documents library unchanged. This increment covers the portal composer, chat backend contract, document ingestion branch, library exclusion, storage cleanup, and regression tests.

## Source Documents

- `docs/requirement/chat-attachment-upload.md`
- `docs/design/chat-attachment-upload.md`
- `docs/design/ui-inventory.md`
- `docs/design/ui-contract.md`
- `docs/design/deployment-plan.md`
- `docs/adr/011-conversation-scoped-chat-attachments.md`
- `docs/adr/012-csv-branch-in-existing-ingestion-pipeline.md`
- `docs/adr/013-dev-local-docker-compose-recreate-deployment.md`
- Codebase discovery: `src/portal/src/components/chat/ChatInput.tsx`, `src/portal/src/app/(auth)/chat/page.tsx`, `src/chat_api/api/v1/chat.py`, `src/document_service/api/v1/documents.py`, `src/document_service/ingestion/service.py`, `src/document_service/services/ocr_worker.py`, `src/document_service/content_store/minio_store.py`, `tests/test_document_visibility.py`, `tests/test_document_ingestion.py`, `tests/test_relational_document_delete.py`

## Brainstorm Notes

- `ChatInput.tsx` is currently text-only; the chat page already owns conversation selection, first-send creation, and streaming/non-streaming send paths.
- Chat turn persistence already uses conversation IDs, so attachment support fits the same request boundary rather than a separate upload-only workflow.
- The document service already has one ingestion pipeline and one delete path; CSV is a branch extension, not a new subsystem.
- The tenant Documents list is already a separate UI and must continue to ignore chat-owned attachments.
- Hard-delete semantics must remove source blobs plus derived spans/chunks/entities, not just hide rows.

## Files Affected

- `src/portal/src/components/chat/ChatInput.tsx` — attachment button, hidden file input, staged attachment tray, remove action, accessible naming, multipart send payload
- `src/portal/src/app/(auth)/chat/page.tsx` — own staged attachment state, wire send flow to attachments, preserve first-send conversation creation timing
- `src/portal/src/components/chat/MessageThread.tsx` — render attachment-related conversation content if attachments are surfaced in-thread
- `src/portal/src/components/chat/ChatInput.test.tsx` — keyboard/accessibility and staging regression coverage
- `src/portal/src/app/(auth)/chat/page.test.tsx` or equivalent — composer/send flow regressions
- `src/chat_api/api/v1/chat.py` — multipart turn handling, conversation-scoped attachment persistence/retrieval, delete cleanup orchestration
- `src/chat_api/api/v1/schemas.py` — request/response shapes for attachment-bearing turns and attachment metadata
- `src/chat_api/services/context_assembler.py` and adjacent retrieval glue — keep conversation-scoped attachment evidence isolated to the active thread
- `src/document_service/ingestion/contract.py` — carry chat-scoped ingestion metadata through the ingest boundary if needed
- `src/document_service/api/v1/documents.py` — Documents library exclusion, delete-path cleanup helpers, and regression-safe filters
- `src/document_service/ingestion/service.py` — existing ingest entry point for CSV branch reuse
- `src/document_service/services/ocr_worker.py` — CSV media-type branch and row-to-span extraction
- `src/document_service/content_store/minio_store.py` — blob deletion support for conversation hard-delete cleanup
- `src/extraction_service/services/relational_projection.py` — reuse delete propagation for derived relational tables
- `migrations/versions/<new>-chat-attachments.py` (new) — add `documents.conversation_id` and supporting index/constraints
- `tests/test_chat_api_conversations.py` — first-send conversation reservation and conversation-scoped retrieval tests
- `tests/test_chat_api_rag.py` or `tests/test_chat_api_retrieval_status.py` — active-thread retrieval regressions
- `tests/test_document_ingestion.py` — CSV accept/parse coverage and existing file-type regressions
- `tests/test_document_visibility.py` — Documents library exclusion regression coverage
- `tests/test_relational_document_delete.py` — hard-delete cleanup coverage for derived tables and orphan avoidance

---

## CAP-2 — Chat Composer Attachment UX

**Depends on:** CAP-3, CAP-4
**Owning service:** portal
**Satisfies:** FR-001, FR-003, FR-006
**Governed by:** none
**Domain:** `portal-chat-composer`

### Summary

Add attachment staging to the chat composer and wire the chat page so files can be queued locally, reviewed, removed, and sent with the message without reserving a conversation early. This covers the composer UI and the page-level state that hands staged files to the backend send call.

### Requirements (ADDED)

- **Requirement: Chat attachment staging**
  - The chat composer SHALL let a user stage one or more files without creating or reserving a conversation.
  - The chat composer SHALL allow a user to remove a staged file before send.
  - Scenario: Stage files before first send
    - **WHEN** a user selects one or more supported files in the chat composer before the first message is sent
    - **THEN** the files SHALL appear in a staged attachment tray
    - **AND** no conversation SHALL be reserved until the user sends the message

- **Requirement: Multipart send interaction**
  - The chat page SHALL submit the staged attachments together with the message in the same send action.
  - The send control SHALL remain keyboard accessible and expose an accessible name.
  - Scenario: Send a message with staged attachments
    - **WHEN** a user sends a message while attachments are staged
    - **THEN** the page SHALL pass the message and attachments together to the chat backend
    - **AND** the composer SHALL clear the staged attachment tray after a successful send

### Requirement Coverage

FR-001 requires a chat attachment button in `ChatInput.tsx`; FR-006 requires that the first attachment does not reserve a conversation early. FR-003 is supported by keeping the attachment flow inside the chat thread rather than the Documents library.

### Evidence

The composer shows an attach control, staged files can be removed before send, and no conversation is created until the user actually sends. A successful send clears the tray and reuses the current chat page flow.

### Demonstrates Reference Scenarios

Not applicable — the requirement baseline has no worked RS example. This capability implements `SCR-2` and `CMP-5` / `CMP-6` from `docs/design/ui-inventory.md`.

### NFRs

- Keyboard access and focus state must be preserved for the new attachment control.
- Staged attachments must not break the existing send-disabled behavior.

### Constraints

- Must fit the existing Next.js portal and the current chat page state model.
- Must not introduce a separate Documents-library-style upload flow.

### Assumptions

- The backend send contract will accept staged attachments in the same turn request.
- The approved file set from the requirement baseline is the source of truth for client acceptance.

### Contracts / Interfaces

- `ChatInput` gains attachment-aware callbacks and staged-file state.
- `src/portal/src/app/(auth)/chat/page.tsx` owns the temporary attachment queue.
- Chat send payload serialization must align with the backend multipart contract from CAP-3.

### API Surface (indicative)

- Chat send action with attachments

### Data owned

- Client-side staged attachment queue only.

### Events published

- None.

### Events consumed

- None.

### Implementation Notes

- Keep the composer behavior additive so existing text-only send remains intact until the new flow lands.
- The tray and send states should mirror the existing visual language in the chat thread.

### Out of scope for this capability

- Server-side persistence of attachments.
- CSV parsing or ingestion.
- Documents-library filtering or hard-delete cleanup.

---

## CAP-3 — Conversation-Scoped Attachment Persistence

**Depends on:** none
**Owning service:** chat_api
**Satisfies:** FR-003, FR-006
**Governed by:** ADR-011
**Domain:** `chat-attachment-lifecycle`

### Summary

Persist chat attachments as conversation-owned document rows and retrieve them only for the active conversation. This capability establishes the backend send contract, the conversation linkage, and the retrieval boundary that keeps chat attachments out of the tenant-wide library.

### Requirements (ADDED)

- **Requirement: Conversation-linked attachment persistence**
  - The chat backend SHALL create conversation-linked attachment records only when a user sends a message.
  - The chat backend SHALL associate each uploaded attachment with exactly one conversation.
  - Scenario: First send creates the conversation and stores the attachments
    - **WHEN** a user sends their first chat message with staged attachments
    - **THEN** the backend SHALL create the conversation if needed
    - **AND** the backend SHALL persist the attachment metadata with that conversation id

- **Requirement: Conversation-scoped attachment retrieval**
  - The chat backend SHALL return attachments only when the requested conversation owns them.
  - The chat backend SHALL not surface chat attachments through a tenant-wide document query.
  - Scenario: Retrieval stays inside the active conversation
    - **WHEN** a user opens a different conversation
    - **THEN** previously uploaded attachments from another conversation SHALL not be returned

- **Requirement: Attachment-bearing turn contract**
  - The chat turn contract SHALL accept message text plus staged file content in the same request.
  - The chat backend SHALL preserve existing conversation send behavior for messages without attachments.
  - Scenario: Send a normal message without attachments
    - **WHEN** a user sends a message with no staged files
    - **THEN** the existing text-only chat path SHALL continue to work unchanged

### Requirement Coverage

FR-003 requires visibility and retrieval scoped to the conversation. FR-006 requires that attachment staging does not reserve a conversation before send. ADR-011 requires the conversation-owned document row model and the hard-delete behavior that follows it.

### Evidence

A send request with attachments produces conversation-linked records, and a fetch for another conversation cannot see them. Existing text-only chat sends still work.

### Demonstrates Reference Scenarios

Not applicable — the requirement baseline has no worked RS example. This capability implements `SCR-2`, `CMP-4`, `CMP-5`, and `CMP-6` in the chat thread inventory.

### NFRs

- Conversation ownership checks must happen before attachment data is loaded.
- The implementation must preserve the existing chat route’s error shape and auth gating.

### Constraints

- Must reuse the existing conversation model and tenant isolation rules.
- Must not introduce a separate attachment table unless the approved ADRs require it.

### Assumptions

- Attachments are stored as document rows with a nullable `conversation_id`.
- Retrieval and citation assembly can reuse the current document/text storage model.

### Contracts / Interfaces

- `src/chat_api/api/v1/chat.py` multipart turn handling and conversation lookup
- `src/chat_api/api/v1/schemas.py` attachment-bearing request/response models
- `documents.conversation_id` and supporting lookup/indexing in the data model
- retrieval glue in `src/chat_api/services/context_assembler.py` / adjacent orchestration code

### API Surface (indicative)

- `POST /api/v1/chat`
- `POST /api/v1/chat/stream`

### Data owned

- Conversation rows, chat messages, and conversation-linked attachment references.

### Events published

- None.

### Events consumed

- None.

### Implementation Notes

- Keep the new attachment-bearing turn shape additive so existing clients can remain text-only.
- Conversation ownership should be enforced before any attachment bytes or derived context are loaded.

### Out of scope for this capability

- CSV-specific parsing.
- Documents-library filtering rules.
- Blob cleanup and delete propagation.

---

## CAP-4 — CSV Ingestion Branch for Chat Attachments

**Depends on:** CAP-3
**Owning service:** document_service
**Satisfies:** FR-002
**Governed by:** ADR-012
**Domain:** `document-ingestion-csv`

### Summary

Extend the existing ingestion pipeline so CSV files are accepted and processed through the same attachment flow as the other supported file types. CSV stays a branch in the current ingest worker, not a separate subsystem.

### Requirements (ADDED)

- **Requirement: CSV attachment acceptance**
  - The document ingestion pipeline SHALL accept CSV files for chat attachments.
  - The upload validation SHALL still reject unsupported file types.
  - Scenario: Upload a CSV attachment
    - **WHEN** a user uploads a `.csv` file through the chat attachment flow
    - **THEN** the upload SHALL be accepted
    - **AND** the file SHALL enter the same ingestion pipeline as the other supported types

- **Requirement: CSV text extraction branch**
  - The worker SHALL parse CSV rows into normalized text spans.
  - The worker SHALL reuse the existing chunking and retrieval path after CSV parsing.
  - Scenario: CSV processing succeeds
    - **WHEN** the ingestion worker processes a supported CSV file
    - **THEN** text spans SHALL be written for the CSV content
    - **AND** downstream chunk generation SHALL use the existing pipeline

### Requirement Coverage

FR-002 requires CSV support in the accepted file set. ADR-012 explicitly requires CSV to be implemented as a branch in the current ingestion pipeline.

### Evidence

Uploading CSV through the chat path succeeds, the worker emits spans/chunks from the CSV rows, and unsupported file types still fail with the existing rejection path.

### Demonstrates Reference Scenarios

Not applicable — the requirement baseline has no worked RS example. This capability implements `SCR-2` and `CMP-6` because CSV is part of the chat attachment chooser surface.

### NFRs

- CSV parsing must not create a separate storage or retrieval subsystem.
- Existing file-type rejection behavior must remain intact.

### Constraints

- Must extend the current ingest entry point and worker dispatch logic.
- Must remain compatible with the existing document span/chunk model.

### Assumptions

- CSV attachments are treated as text-bearing attachments rather than a special document class.
- The current purpose-based ingest behavior remains in place.

### Contracts / Interfaces

- `src/document_service/api/v1/documents.py` file-type allow-list and error reporting
- `src/document_service/ingestion/service.py` ingest entry point
- `src/document_service/services/ocr_worker.py` media-type dispatch and CSV parsing branch

### API Surface (indicative)

- `POST /api/v1/documents`

### Data owned

- Document rows, text spans, and downstream chunks generated from CSV content.

### Events published

- None.

### Events consumed

- None.

### Implementation Notes

- Keep CSV handling local to the existing worker dispatch so the rest of the ingestion pipeline stays unchanged.
- Reuse the same chunking/embedding path that the other query-oriented document types already use.

### Out of scope for this capability

- Conversation scoping and persistence.
- Documents-library filtering.
- Hard-delete cleanup.

---

## CAP-5 — Documents Library Exclusion and Hard-Delete Cleanup

**Depends on:** CAP-3
**Owning service:** document_service
**Satisfies:** FR-004, FR-007
**Governed by:** ADR-011
**Domain:** `document-library-isolation`

### Summary

Keep conversation-linked attachments out of the tenant-wide Documents library and hard-delete the source files plus derived artefacts when a conversation is deleted. This preserves the existing library behavior while ensuring chat deletion removes all attachment traces the product can reach.

### Requirements (ADDED)

- **Requirement: Documents library exclusion**
  - The tenant Documents library SHALL exclude documents that belong to a conversation.
  - The Documents page SHALL continue to list non-chat uploads unchanged.
  - Scenario: Documents library omits chat attachments
    - **WHEN** a conversation-linked attachment exists for the tenant
    - **THEN** the tenant-wide Documents query SHALL not return that document row

- **Requirement: Conversation hard-delete cleanup**
  - Deleting a conversation SHALL hard-delete linked attachment files and derived artefacts.
  - The delete path SHALL remove document rows, blobs, spans, chunks, and derived relational rows tied to the conversation attachments.
  - Scenario: Delete a conversation with attachments
    - **WHEN** a user deletes a conversation that owns attachments
    - **THEN** the linked attachment blobs SHALL be removed
    - **AND** the attachment-derived database rows SHALL be removed
    - **AND** the deleted conversation SHALL no longer be retrievable through the product UI

### Requirement Coverage

FR-004 requires that the tenant-wide Documents tab/library remain unchanged. FR-007 requires hard-delete of uploaded files and derived artefacts on conversation deletion. ADR-011 explicitly requires the conversation-owned row model and the same cleanup semantics.

### Evidence

The Documents page never shows conversation-owned attachment rows, and deleting the conversation removes the source blob plus all derived records that were generated from that attachment.

### Demonstrates Reference Scenarios

Not applicable — the requirement baseline has no worked RS example. This capability preserves `SCR-3` and its collection controls (`CMP-7`, `CMP-8`, `CMP-9`, `CMP-10`) by keeping conversation attachments out of that surface.

### NFRs

- Delete cleanup must be idempotent and safe to retry.
- Library filters must remain stable for existing non-chat uploads.

### Constraints

- Must reuse the existing delete propagation pattern rather than inventing a second cleanup path.
- Must not alter tenant-wide upload behavior for non-chat documents.

### Assumptions

- The conversation delete route can invoke shared deletion helpers for document cleanup.
- Blob deletion is available from the current content-store adapter.

### Contracts / Interfaces

- `src/document_service/api/v1/documents.py` list/delete filters and cleanup orchestration
- `src/document_service/content_store/minio_store.py` blob deletion support
- `src/extraction_service/services/relational_projection.py` derived-table delete propagation
- conversation delete path in `src/chat_api/api/v1/chat.py`

### API Surface (indicative)

- `GET /api/v1/documents`
- `DELETE /api/v1/chat/conversations/{conv_id}` or the existing conversation delete route in `chat.py`

### Data owned

- Document rows, blob references, text spans, chunks, extracted entities, and relational projections for deleted conversation attachments.

### Events published

- None.

### Events consumed

- None.

### Implementation Notes

- Make the library exclusion explicit in the query predicate rather than relying on naming or UI hiding.
- Cleanup should remove every attachment-derived artefact in the same request path so no recoverable residue remains.

### Out of scope for this capability

- CSV parser behavior.
- Composer attachment staging UI.
- New conversation send contract details.

---

## Cross-Cutting Concerns

- Tenant auth and ownership checks must stay in the existing request guards.
- Error envelopes should stay aligned with the current API conventions.
- Logging must remain shape-only; attachment bytes and document content must not be logged.
- Accessibility applies to the new composer control and staged-attachment interactions.
- Regression coverage should prove: composer staging, CSV acceptance, conversation-scoped retrieval, Documents-library exclusion, and hard-delete cleanup.

## Dependency Order (Suggested Implementation Sequence)

Wave 1 (no prerequisites): CAP-3
Wave 2 (depends on Wave 1): CAP-4, CAP-5
Wave 3 (depends on Wave 2): CAP-2

## Summary Table

| ID | Capability | Depends on | Service | FRs |
|---|---|---|---|---|
| CAP-2 | Chat Composer Attachment UX | CAP-3, CAP-4 | portal | FR-001, FR-003, FR-006 |
| CAP-3 | Conversation-Scoped Attachment Persistence | — | chat_api | FR-003, FR-006 |
| CAP-4 | CSV Ingestion Branch for Chat Attachments | CAP-3 | document_service | FR-002 |
| CAP-5 | Documents Library Exclusion and Hard-Delete Cleanup | CAP-3 | document_service | FR-004, FR-007 |
