## Context

One upload endpoint (`POST /api/v1/documents` in `src/document_service/api/v1/documents.py`) serves every document regardless of intent, and unconditionally triggers OCR → chunk → embed (`trigger_ocr` → `process_document` → `_store_chunks`, writing to `document_chunks`). Three consumers currently read from this same undifferentiated pool with no purpose scoping: `RAGOrchestrator`/`DenseRetriever` (chat retrieval, via `retrieval-core`), `AssignTaskForm`/`POST /api/v1/annotation-tasks` (annotation-task assignment), and `POST /api/v1/extract-batch` (batch NER extraction). `chunk-metadata-ingest` (archived) established the pattern of denormalizing per-document metadata (`page_number`, `char_start`, `char_end`) onto `document_chunks` at ingest time rather than joining back to `documents` at query time — this change follows that same pattern for `purpose`.

## Goals / Non-Goals

**Goals:**

- A `purpose` column (`query` | `training`) on `documents`, set explicitly at upload time, defaulting to `query`.
- Chat retrieval (`DenseRetriever`, `SparseRetriever`, `HybridRetriever`) hard-filters to `purpose = 'query'` — not optional, not caller-controllable.
- Annotation-task creation only accepts `purpose = 'training'` documents; the document picker (`AssignTaskForm`) only offers those.
- Batch extraction's "no explicit `documentIds`" default only operates on `purpose = 'query'` documents.
- A pragmatic backfill for existing documents.

**Non-Goals:**

- No support for a document being both `training` and `query` simultaneously in this change — `purpose` is a single mutually-exclusive enum. If a concrete tenant need for "both" surfaces later, that's an additive change (e.g., `purpose` becomes a set, or a document can be cloned/re-uploaded under the other purpose).
- No retroactive re-embedding or re-annotation triggered by a `purpose` change after the fact — changing `purpose` on an existing document does not automatically re-run ingestion; it only affects new chunks from that point forward (existing chunks' denormalized `purpose` value stays as it was until re-ingestion), matching `chunk-metadata-ingest`'s precedent of not backfilling existing chunks.
- No change to the SQL-generation RAG source (`SQLGenerator`) — that queries `extracted_entities`/`documents` structured data directly, not `document_chunks`; scoping structured-data queries by `purpose` is out of scope here since the proposal's stated gap is specifically about chat citing training-corpus document *content* (chunks), not entity-extraction results (which already only exist for documents someone chose to run batch extraction on).

## Decisions

**`purpose` lives on `documents` (source of truth, settable at upload) and is denormalized onto `document_chunks` (set once at ingest time from the parent document's purpose).**
Matches `chunk-metadata-ingest`'s established pattern exactly (that change denormalized `page_number`/`char_start`/`char_end` for the same reason: avoid a `JOIN` to `documents` in the hot retrieval path). `process_document` already reads/writes the `documents` row for status updates; it fetches `purpose` in that same step and threads it through to `_store_chunks`.
Alternative considered: only store `purpose` on `documents` and `JOIN` in every retrieval query — rejected, inconsistent with the codebase's established denormalization precedent and adds a join to the query path every retrieval change so far has kept join-free.

**Purpose is set explicitly at upload via a `purpose` form field, default `'query'` — no second upload endpoint, no inference from later annotation-task creation.**
Resolves proposal's open question. A single upload widget with an explicit purpose choice (radio/toggle, defaulting to `query`) is simplest: no duplicated upload logic, no new route, and the choice is made by the same person (typically a Tenant Admin) at the moment they know why they're uploading. Inferring `purpose='training'` retroactively from "a task now exists for this document" was considered and rejected: it would mean a document is briefly `query`-visible (and could already be embedded/cited in a chat response) before an admin gets around to assigning it — a real, if narrow, data-exposure window this change exists to close. Explicit-at-upload has no such window.
Frontend: `use-upload.ts`'s `upload(file)` gains a second parameter `purpose: 'query' | 'training' = 'query'`, appended to the `FormData`; the "Documents" upload UI gains a purpose toggle.

**Annotation-task creation validates `purpose` server-side (not just via a filtered picker), returning 422 if the target document isn't `purpose='training'`.**
The document picker (`AssignTaskForm`) filtering to `training`-only documents is a UX convenience, not the enforcement boundary — a client-side filter alone would still let an old client (or a future caller) create a task against a `query` document by ID. `POST /api/v1/annotation-tasks` re-checks `purpose` server-side, mirroring how it already re-checks the active-task conflict server-side rather than trusting the client to have filtered correctly.

**Retrieval SQL adds a literal `AND purpose = 'query'` — not routed through the existing `metadata_filter` parameter from `hybrid-retrieval-hnsw`.**
`metadata_filter` (from the in-flight `hybrid-retrieval-hnsw` proposal, not yet implemented) is caller-supplied and optional — appropriate for a chat-side "restrict to this one document" convenience, but wrong for a hard data-isolation guarantee that must hold even if no caller passes anything. Hardcoding the clause means it can't be accidentally omitted by a future call site. If `hybrid-retrieval-hnsw` lands first, its retrievers gain this hardcoded clause too, additive to (not replacing) `metadata_filter`; if this change lands first, `hybrid-retrieval-hnsw`'s new retrievers inherit the same hardcoded clause when they're written. Either ordering is safe because the two changes touch the same file (`src/shared/retrieval/retriever.py`) but different, additive parts of each query (a `metadata_filter`-driven clause is optional/caller-supplied; the `purpose` clause is unconditional) — implementers should re-check the file's actual state at apply time rather than assuming this design's exact line numbers.

**Batch extraction's default query gains `AND purpose = 'query'`; explicit `documentIds` (when the caller names specific IDs) are NOT purpose-filtered.**
Matches today's asymmetry: the "give me all eligible documents" default path is where an unscoped training document could accidentally get swept into a batch extraction run; a caller who explicitly names document IDs already knows what they're asking for (same principle governs why explicit `metadata_filter` differs from the hardcoded retrieval-side clause above).

**Backfill: existing documents already referenced by an `annotation_tasks` row are set to `purpose='training'`; everything else defaults to `purpose='query'`.**
Resolves proposal's open question with the most concrete signal available — a document that's already been assigned for annotation was, in practice, being used as training material. This is a one-time `UPDATE ... WHERE id IN (SELECT document_id FROM annotation_tasks)` in the migration, run once, not a standing behavior.

## Risks / Trade-offs

- **[Risk] Backfill heuristic (`purpose='training'` for any document with an existing annotation_tasks row) could misclassify a document a tenant genuinely wanted both annotated and queryable** → Mitigation: this is a one-time, reversible column value (a tenant admin can update `purpose` back to `query` via a future admin UI or direct support action); explicitly documented as a judgment call in this design, not silently assumed correct.
- **[Risk] Denormalizing `purpose` onto `document_chunks` means changing a document's `purpose` after ingestion doesn't retroactively change existing chunks' scoping** → Mitigation: matches `chunk-metadata-ingest`'s accepted precedent for `page_number`; document this explicitly as a Non-Goal so it isn't mistaken for a bug later.
- **[Risk] Hardcoding `purpose = 'query'` in retrieval SQL (rather than making it a parameter) could make future legitimate use cases (e.g., an internal admin tool that needs to search training documents) harder to build** → Mitigation: acceptable now — no such use case exists yet; if one appears, it's an explicit new code path (e.g., a separate `TrainingCorpusRetriever`), not a parameter threaded through the chat-facing retrievers.
- **[Risk] Two independent in-flight changes (this one and `hybrid-retrieval-hnsw`) both touch `src/shared/retrieval/retriever.py`** → Mitigation: called out explicitly in Decisions above; whichever change is implemented second must read the file's current state (not assume the other change hasn't landed) and merge its SQL clause additively.
- **[Risk] Existing integration tests / API clients that upload documents without a `purpose` field must keep working** → Mitigation: `purpose` defaults to `'query'` server-side when omitted — no existing caller breaks.

## Migration Plan

1. New alembic migration (revision number assigned at implementation time, following whichever is head): `ALTER TABLE tenant_template.documents ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) NOT NULL DEFAULT 'query'`, same `ADD COLUMN IF NOT EXISTS purpose VARCHAR(20)` on `tenant_template.document_chunks`, looped over every existing `tenant_%` schema (migration 010/021 precedent).
2. In the same migration, backfill: `UPDATE {schema}.documents SET purpose = 'training' WHERE id IN (SELECT document_id FROM {schema}.annotation_tasks)`, per schema.
3. Code changes (upload endpoint, retrievers, task creation, batch extraction default, frontend) ship in the same change.
4. Rollback: downgrade drops both `purpose` columns across all schemas; code rollback is a plain revert (no other data depends on `purpose` existing).

## Open Questions

- None of the in-force ADRs need revisiting — ADR-007's citation/tenant-scoping guarantees are strengthened (an additional scoping dimension), not altered or weakened.
- Confirmed: `purpose` is upload-time-explicit, not inferred (see Decisions) — resolves proposal's UI-mechanism question.
- Confirmed: backfill heuristic uses existing `annotation_tasks` linkage (see Decisions) — resolves proposal's backfill question.
- Confirmed: mutually exclusive enum, no "both" support in this change (see Non-Goals) — resolves proposal's third question.
