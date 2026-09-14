## Why

Conversation-linked attachment rows already live in the document model (ADR-011, CAP-3), but two gaps remain. The tenant-wide Documents library can still reach them: the list query excludes them, yet fetch-by-id, text retrieval and library delete do not, so a conversation attachment is one guessed id away from the library's surface. And deleting a conversation removes only chat messages — the attachment rows, any persisted blobs and every derived artefact survive, which contradicts FR-007's hard-delete expectation. This change keeps the library unchanged for non-chat uploads while making conversation deletion remove every attachment trace the product can reach.

## What Changes

- Exclude conversation-linked document rows from every tenant-wide Documents library surface (list, fetch-by-id, text retrieval, library delete).
- Hard-delete conversation-attachment document rows, persisted blobs, spans, chunks, extracted entities and derived relational rows on conversation deletion.
- Reuse the existing delete-propagation pattern (the same pure builder the extraction worker and the library soft-delete use) instead of inventing a second cleanup path.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `portal-documents`: tenant-wide Documents library surfaces exclude conversation-linked document rows, while non-chat upload, listing and soft-delete behavior stay unchanged.
- `chat-api`: conversation deletion hard-deletes linked attachment files and all derived artefact rows before the conversation row is removed.

## Impact

- `src/document_service/api/v1/documents.py` — exclusion predicates on library surfaces and shared hard-delete cleanup orchestration
- `src/chat_api/api/v1/chat.py` — `delete_conversation` invokes the shared cleanup for attachment documents before removing messages and the conversation
- `src/document_service/content_store/` — blob deletion through the existing content-store adapter
- `src/extraction_service/services/relational_projection.py` — `build_relational_delete_statements` reused for derived-table propagation

## Open Questions

- None. The decomposition and ADR-011 already define the library exclusion and hard-delete semantics.