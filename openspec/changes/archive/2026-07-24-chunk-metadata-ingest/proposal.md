## Why

`document_service/ocr_worker.py` already extracts per-page span metadata (`page_number`, `char_start`, `char_end`) into `document_text_spans`, but that metadata is thrown away before chunking: `process_document` joins all spans into one `full_text` string and hands it to the shared token-based chunker, which has no notion of which page or span a chunk came from. As a result, `document_chunks` rows and chat citations carry no page/location information — `Citation.page_number` exists in `src/chat_api/api/v1/schemas.py` but is never populated. This blocks accurate "see page 4" citations and is a prerequisite for later small-to-big context assembly, which needs to know each chunk's position in the source document.

## What Changes

- Chunk per extracted span (page) instead of chunking one flattened `full_text` blob, so each chunk is attributable to exactly one page and never straddles a span/page boundary.
- Add `page_number`, `char_start`, `char_end` columns to `document_chunks` (all tenant schemas + `tenant_template`, via alembic migration following the existing per-schema `DO $$` loop pattern from migration 010).
- Extend the `Chunk` and `RetrievalResult` domain models (`src/shared/retrieval/models.py`) with optional `page_number`, `char_start`, `char_end` fields.
- Populate `Citation.page_number` in `RAGOrchestrator._enrich_citations` from the retrieved chunk's metadata.
- **BREAKING (internal only, no API contract change)**: chunk boundaries for newly ingested documents will differ from today's — a chunk_size=512 window will no longer span across two pages. Existing chunks for already-ingested documents are unaffected (not re-chunked) and will simply have `NULL` metadata until re-ingested; no backfill migration is included in this change (see Open Questions).
- No change to `/api/v1/chat` request/response shape — `page_number` is an existing, previously-unpopulated field on `Citation`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `retrieval-core`: `Chunk` and `RetrievalResult` gain page/location metadata fields; chunking changes from single-blob to per-span, changing the "Typed retrieval domain model" and adding a new chunking-boundary requirement.
- `chat-api`: the "RAG chat endpoint" document-context scenario gains an expectation that citations include `page_number` when the source chunk has it.

## Impact

- `src/document_service/services/ocr_worker.py` — chunk per span instead of per joined `full_text`; pass span metadata through to `_store_chunks`
- `src/shared/retrieval/models.py`, `src/shared/retrieval/chunking.py`, `src/shared/retrieval/retriever.py` — new optional fields, `DenseRetriever` SQL selects the new columns
- `src/chat_api/services/rag_orchestrator.py` — `_enrich_citations` populates `Citation.page_number`
- New alembic migration `021_document_chunks_page_metadata.py` — adds `page_number INTEGER`, `char_start INTEGER`, `char_end INTEGER` to `document_chunks` in `tenant_template` and every existing `tenant_%` schema (same loop pattern as migration 010)
- `tests/conftest.py`'s local `document_text_spans` test-table definition uses different column names (`page_no`, `block_no`, `start_offset`, `end_offset`) than the real migration-defined schema (`span_index`, `char_start`, `char_end`, `page_number`) — this pre-existing drift is out of scope but noted since it affects how realistic integration tests for this change can be written (see design.md)

## Open Questions

- Should existing (already-ingested) documents' chunks be backfilled with metadata via a data migration/re-ingestion job? Deferred — this change only wires metadata for newly ingested documents going forward. Flagging as a candidate follow-up change if tenants need retroactive page citations.
- Per-span chunking means a chunk_size=512 token window can no longer span two pages, so a chunk near a page boundary may be shorter than 512 tokens (bounded by the page's own token count). Confirm this trade-off (page fidelity over uniform chunk size) is acceptable — design.md discusses the alternative (offset-mapped continuous chunking) and why it's deferred.
