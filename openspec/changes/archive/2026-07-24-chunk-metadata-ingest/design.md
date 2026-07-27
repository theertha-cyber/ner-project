## Context

`ocr_worker.extract_text_pdf`/`extract_text_image`/`extract_text_pdf_as_image` already produce per-page spans with `page_number`, `char_start`, `char_end`, stored in `document_text_spans`. `process_document` then does `full_text = "\n".join(s["text"] for s in spans if s["text"].strip())` and passes that single flattened string to `chunk_text` (from `retrieval-foundation`'s `src/shared/retrieval/chunking.py`), which token-chunks it with no awareness of page boundaries. `document_chunks` (migration 010) has no location columns. `Citation.page_number` exists in `src/chat_api/api/v1/schemas.py` but nothing ever sets it.

`retrieval-foundation` (archived) established `Chunk`, `RetrievalResult`, the `Retriever` protocol, and `DenseRetriever` — this change extends those, it does not replace them. ADR-007 (chatbot-architecture, in force) requires citations for every response but does not mandate page numbers specifically; this change strengthens citation quality within that existing contract, it doesn't change the contract itself.

## Goals / Non-Goals

**Goals:**

- Every chunk produced from newly ingested documents carries `page_number`, `char_start`, `char_end` back to its source span.
- `document_chunks` persists this metadata; `DenseRetriever` returns it on `RetrievalResult`.
- `Citation.page_number` is populated when the underlying chunk has it.

**Non-Goals:**

- No backfill of existing (already-ingested) documents' chunks — they keep `NULL` metadata until re-ingested. A backfill/re-ingestion job is a candidate follow-up change, not part of this one.
- No hybrid retrieval, no reranking, no context-assembly changes — those are later changes in the roadmap.
- No change to `document_text_spans` schema — it already has the metadata this change consumes.
- No fix to the pre-existing `tests/conftest.py` / real-schema column-name drift for `document_text_spans` beyond what's needed to write realistic tests for this change (see Decisions).

## Decisions

**Chunk per span (page), not per flattened `full_text` blob.**
Two approaches were considered for carrying metadata through chunking:

- **(a) Per-span chunking (chosen)**: run the existing token-chunker independently on each span's `text`, tagging every resulting chunk with that span's `page_number`/`char_start`/`char_end`. A chunk never crosses a page boundary.
- **(b) Offset-mapped continuous chunking**: keep chunking one continuous `full_text` (preserving cross-page context in a single chunk), but build a precise char-offset map from `full_text` positions back to `(span, page_number)`, then compute each output chunk's page range by reverse-mapping its token span.

(a) is chosen: it is simple, has no offset-alignment risk, and page-exact citations are the actual goal here — "chat with document A, page 4" is a more valuable answer than a chunk that happens to span pages 3–4 with one attributed page number. (b) would also require fixing today's latent offset bug (see below) as a prerequisite, since the char_offset computed in `extract_text_pdf` counts every span including whitespace-only ones, while `full_text` filters them out (`if s["text"].strip()`) — so `document_text_spans.char_start`/`char_end` are not currently guaranteed to line up with positions in `full_text` at all. Fixing that bug is out of scope; per-span chunking sidesteps it entirely because each span is chunked using its own local text, never `full_text`.

Trade-off accepted: a chunk near a page boundary may be shorter than `chunk_size` tokens (bounded by its page), and very short pages produce very short chunks. This is a quality trade-off, not a correctness one, and is easy to revisit later (e.g., merging small trailing chunks) without touching the metadata plumbing this change adds.

**`document_chunks` gains three nullable columns: `page_number INTEGER`, `char_start INTEGER`, `char_end INTEGER`.**
Nullable because existing chunks (pre-this-change) have no metadata and are not backfilled. All three are set together — a chunk always has a single source span, so page_number/char_start/char_end come from that one span, never mixed.
Migration follows the exact pattern of migration 010 (`ALTER TABLE tenant_template.document_chunks ADD COLUMN ...`, then a `DO $$ ... FOR schema_name IN tenant_%` loop for every existing tenant schema) — this is the established convention in this codebase for schema changes that must apply across all per-tenant schemas.

**`Chunk` and `RetrievalResult` gain optional fields, not new models.**
`page_number: int | None = None`, `char_start: int | None = None`, `char_end: int | None = None` on both. Keeping them on the existing models (rather than a new `ChunkMetadata` sub-model) matches `retrieval-foundation`'s decision to keep these models flat and matches how `RetrievalResult` is already consumed directly by attribute access in `rag_orchestrator.py`.

**`DenseRetriever`'s SQL adds the three columns to its `SELECT` — no other query change.**
Preserves scenario 3 from `retrieval-foundation` (dense retrieval ranking/ordering behavior) exactly; only the returned columns change, not the `ORDER BY`/`WHERE`/index usage.

**Test fixture note:** `tests/conftest.py`'s local `_TENANT_TABLES_SQL` defines `document_text_spans` with columns (`page_no`, `block_no`, `start_offset`, `end_offset`) that don't match the real migration-defined schema (`span_index`, `char_start`, `char_end`, `page_number`, used by `ocr_worker.py`). This change's tests seed `document_chunks` directly (as `retrieval-foundation`'s tests already do) rather than going through `document_text_spans`, so this drift doesn't block testing — but it's flagged here since a future change that actually tests the OCR-to-span pipeline end-to-end will hit it.

## Risks / Trade-offs

- **[Risk] Per-span chunking changes chunk boundaries for all newly ingested documents, invalidating any assumption that chunk_index N always means "the Nth 512-token window of the document"** → Mitigation: `chunk_index` already only had document-scoped meaning via `document_chunks`, not a cross-document guarantee; no code depends on chunk_index being continuous across pages. Confirm via grep before implementing.
- **[Risk] Very short pages (e.g., a mostly-blank page) produce very short or empty chunks, adding low-value rows to `document_chunks`** → Mitigation: skip chunking for spans whose stripped text is empty (already filtered before `full_text` join today — apply the same filter per-span).
- **[Risk] Nullable metadata on old chunks means `DenseRetriever` results are a mix of chunks with and without page numbers, and downstream code must handle `None` gracefully** → Mitigation: `Citation.page_number` is already `int | None` in the schema; explicit test asserting citation construction succeeds when `page_number` is `None`.
- **[Risk] Migration touches every tenant schema in a loop (as 010 did) — a partial failure mid-loop leaves some tenant schemas migrated and others not** → Mitigation: same risk profile as the precedent migration 010 already accepted in this codebase; no new mitigation invented beyond following the existing pattern (idempotent `ADD COLUMN IF NOT EXISTS` semantics via `ADD COLUMN ... IF NOT EXISTS` where supported, matching migration 003's style).

## Migration Plan

1. Add alembic migration `021_document_chunks_page_metadata.py`: `ALTER TABLE tenant_template.document_chunks ADD COLUMN IF NOT EXISTS page_number INTEGER, ADD COLUMN IF NOT EXISTS char_start INTEGER, ADD COLUMN IF NOT EXISTS char_end INTEGER`, then loop over existing `tenant_%` schemas applying the same ALTER (pattern matches migration 010's `DO $$ ... FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%'`).
2. Update `Chunk`/`RetrievalResult` models, chunking logic, `DenseRetriever` SQL, `_store_chunks`, and `_enrich_citations` in the same change (all backward compatible — new nullable fields, no removed fields).
3. Rollback: downgrade drops the three columns (matching migration 010's downgrade style); code rollback is a plain revert since all new fields are optional with `None` defaults.
4. No backfill step — deliberately deferred (see Non-Goals/Open Questions).

## Open Questions

- None of the in-force ADRs need revisiting — ADR-007's citation-required guardrail is strengthened, not altered.
- Confirmed with proposal.md: backfill of pre-existing chunks is explicitly out of scope for this change.
