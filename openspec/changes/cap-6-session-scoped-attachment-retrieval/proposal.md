## Why

A user can stage a file in the chat composer (CAP-2) and the turn persists a conversation-owned `documents` row (CAP-3), but the file's **content never reaches retrieval**: `_persist_attachments` (`src/chat_api/api/v1/chat.py:113-131`) writes a metadata row only — no bytes, no content-store write, no chunking, no embedding — so no `document_chunks` rows are ever produced for it. The driving use case is HR screening: a recruiter opens a new chat session, attaches a job description, and asks the assistant to evaluate resumes against it. Today that attachment is inert and the question cannot be answered from it.

The second half of the gap is isolation. Retrieval is tenant-wide: `DenseRetriever`/`SparseRetriever` (`src/shared/retrieval/retriever.py:65-116`) filter `document_chunks` by tenant schema and `purpose = 'query'` only, and the sole narrowing mechanism is an optional `scope` argument the LLM chooses (`src/shared/retrieval/tools/document_tools.py:14-32`). So if attachment content were simply indexed the obvious way, a JD attached in one session would become retrievable in **every** session for that tenant — the exact opposite of what the use case requires, and a contradiction of ADR-011's conversation-ownership rule and of migration 040's stated intent that conversation-linked documents stay out of tenant-wide retrieval.

## What Changes

- **BREAKING (wire contract):** an attachment-bearing chat turn is sent as `multipart/form-data` carrying the actual file bytes, replacing CAP-2's metadata-only `attachments` JSON array. Text-only turns are unchanged — the existing JSON body remains the request shape when no files are attached, and the route branches on `Content-Type`.
- Chat attachments are ingested through `DocumentIngestionService.ingest()` — the module documented as "the one code path permitted to create a `documents` row" — instead of the direct `INSERT` in `chat.py`, so attachments acquire a content-store write, checksum, retention resolution, text extraction, chunking, and embeddings like any other document.
- `NormalizedDocument` gains a `conversation_id` field so an attachment is conversation-owned from the moment its row is written; there is never a window in which an ingested attachment exists unowned.
- Attachment processing completes **before** the turn's retrieval runs, so the same message that carries the JD can be answered from it.
- `document_chunks` gains a denormalized `conversation_id`, mirroring how `purpose` is already denormalized onto chunks (migration 022), so retrieval can filter without a join.
- Retrieval applies a **mandatory** conversation-visibility predicate derived from the authenticated request context, not from LLM tool arguments: a chunk is visible when its `conversation_id IS NULL` (tenant library content, visible everywhere as today) **or** equals the current conversation. The model cannot widen this scope.
- The composer surfaces per-file upload and indexing state, and keeps a file staged when its upload or ingestion fails.

## Capabilities

### New Capabilities

- `conversation-scoped-retrieval`: the visibility rule for conversation-owned content — how a chunk's conversation ownership determines which conversations may retrieve it, that the rule is enforced from request context rather than chosen by the model, and that tenant-library content remains visible in every conversation.

### Modified Capabilities

- `chat-api`: the attachment-bearing turn contract changes from metadata-only JSON to `multipart/form-data` carrying file bytes; the turn ingests attachments through the ingestion service and blocks on their processing before retrieval runs.
- `chat-composer-attachments`: the composer sends file bytes rather than metadata, reports per-file upload/indexing progress and failure, and preserves staged files when a send fails.
- `retrieval-core`: retrieval gains a mandatory conversation-visibility predicate that cannot be widened by a caller-supplied or model-supplied scope.

## Impact

- `src/chat_api/api/v1/chat.py` — multipart branch on both `/api/v1/chat` and `/api/v1/chat/stream`; `_persist_attachments` replaced by an ingestion-service call; inline await of attachment processing before the RAG turn.
- `src/chat_api/api/v1/schemas.py` — `AttachmentInput` retired from the send contract (metadata now derives from the uploaded parts).
- `src/document_service/ingestion/contract.py` / `service.py` — `conversation_id` on `NormalizedDocument`, written by `_insert_row`.
- `src/document_service/services/ocr_worker.py` — denormalize `conversation_id` onto `document_chunks` alongside `purpose`.
- `src/shared/retrieval/retriever.py` — mandatory conversation-visibility predicate in the dense and sparse SQL.
- `src/shared/retrieval/tools/base.py` / `document_tools.py` — carry the current conversation on `ToolContext`; the predicate is not reachable from `scope`.
- `src/chat_api/services/rag_orchestrator.py`, `src/chat_api/graph/nodes.py` — thread the conversation into the retrieval context.
- `alembic/versions/041_*` — `document_chunks.conversation_id` on `tenant_template` and every provisioned tenant schema, matching the pattern of migrations 022/034/040.
- `src/portal/src/components/chat/ChatInput.tsx`, `src/portal/src/app/(auth)/chat/page.tsx` — send real `File` objects as multipart; per-file state.
- Tests: `tests/test_chat_api_attachments*.py`, `tests/test_retrieval_foundation.py`, `tests/test_ingestion_boundary.py`, portal `ChatInput.test.tsx` / chat `page.test.tsx`.
- Unaffected by design: the Documents-library exclusion and conversation hard-delete from CAP-5 already key off `documents.conversation_id` and already remove `document_chunks`, so they cover the newly-created chunks without modification.

## Open Questions

- None blocking. Two assumptions are recorded as risks in verification.md: (1) inline attachment processing keeps first-turn latency acceptable for the expected attachment sizes, mitigated by the existing 50MB ingestion cap and a bounded wait; (2) no existing caller depends on chat attachments being absent from retrieval results.
