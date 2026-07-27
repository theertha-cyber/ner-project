## Why

Every document uploaded through `POST /api/v1/documents` is treated identically regardless of why it was uploaded: it gets OCR'd, chunked, and embedded into `document_chunks` unconditionally, and it's retrievable by both the annotation-task picker (`AssignTaskForm`, backed by `GET /api/v1/documents`) and the chat RAG pipeline (`DenseRetriever`/hybrid retrieval). There is no column, flag, or filter anywhere that distinguishes "this document exists to be annotated and become fine-tuning training data" from "this document exists so a business user can query it via chat." Confirmed by code inspection: `documents` table (migration 003) has no purpose/category column; `AssignTaskForm.tsx` fetches the exact same document list the business-user "Documents" page uploads into; batch extraction (`extraction.py::trigger_batch_extraction`) and chat retrieval both operate over `WHERE status = 'processed'` with no further scoping. This means a document uploaded purely to build a training corpus can currently surface as a chat citation, and there's no way to upload a document intended only for querying without it also being assignable as an annotation task.

## What Changes

- Add a `purpose` column to `{schema}.documents` (values: `query`, `training`; default `query`) via alembic migration across `tenant_template` and every existing `tenant_%` schema.
- Add an optional `purpose` form field to `POST /api/v1/documents` (defaults to `query` when omitted, preserving today's behavior for existing integrations/tests that don't send it).
- `DenseRetriever`, `SparseRetriever`, and `HybridRetriever` (from `retrieval-core`) SHALL hard-filter to `purpose = 'query'` — not as an optional `metadata_filter` a caller can opt into, but as a non-bypassable clause in the retrieval SQL itself, since this is a data-isolation guarantee, not a convenience filter.
- `POST /api/v1/annotation-tasks` (annotation task creation) SHALL only accept documents with `purpose = 'training'`; `GET /api/v1/documents` used by `AssignTaskForm`'s document picker SHALL be filtered (via a query parameter or client-side filter, TBD in design) to show only `purpose = 'training'` documents.
- `POST /api/v1/extract-batch` (batch extraction) SHALL only operate on documents with `purpose = 'query'` when no explicit `documentIds` are given (matching its current "all eligible processed documents" default behavior, now purpose-scoped).
- **BREAKING (internal only)**: existing documents (uploaded before this change) default to `purpose = 'query'` on backfill — any of them currently assigned to an annotation task will need that task's document to be re-tagged `training` (see Open Questions) or the annotation-task requirement's new constraint will reject new tasks against them going forward (existing in-progress tasks are unaffected, only new task creation is gated).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `document-ingestion`: "Document Upload" requirement gains an optional `purpose` field.
- `retrieval-core`: "Retriever interface" requirement — all three retriever implementations hard-scope to `purpose = 'query'` documents.
- `annotation-workspace`: "Annotation Task Management" requirement — task creation is restricted to `purpose = 'training'` documents.
- `extraction-service`: "Batch extraction" requirement — default (no explicit `documentIds`) batch extraction is restricted to `purpose = 'query'` documents.

## Impact

- `src/document_service/api/v1/documents.py` — `upload_document` accepts `purpose`, `list_documents` supports filtering by it
- New alembic migration (next available revision number at implementation time) — adds `purpose VARCHAR(20) DEFAULT 'query' NOT NULL` to `document_chunks`... no, to `documents`, across `tenant_template` and every `tenant_%` schema
- `src/shared/retrieval/retriever.py` — `DenseRetriever`/`SparseRetriever`/`HybridRetriever` SQL gains `AND d.purpose = 'query'` (requires joining or denormalizing `purpose` onto `document_chunks`, see design)
- `src/annotation_service/api/v1/tasks.py` — task creation validates the target document's `purpose`
- `src/extraction_service/api/v1/extraction.py` — `trigger_batch_extraction`'s "all eligible documents" query adds `AND purpose = 'query'`
- `src/portal/src/components/annotation/AssignTaskForm.tsx` — document picker scoped to training-purpose documents
- Portal document upload UI (`use-upload.ts` / wherever the upload form lives) — needs a way to set `purpose` at upload time (design decides: explicit picker vs. separate upload entry points vs. inferred from which page the upload happens on)

## Open Questions

- **Existing data backfill**: today's documents all default to `purpose='query'`. Any of them already assigned to an in-progress/completed annotation task represent a real ambiguity — were they meant to be training-only? Confirm whether a one-time backfill should set `purpose='training'` for any document that already has an `annotation_tasks` row, or whether this is left as manual tenant-admin cleanup.
- **UI mechanism for setting purpose at upload**: should the existing single "Documents" upload page gain a purpose toggle/radio (query vs. training), or should there be two distinct upload entry points (one on the business-user "Documents" page defaulting to `query`, one reached only from the annotation workflow defaulting to `training`)? This affects `use-upload.ts` and whichever page(s) render the upload widget — needs a design decision, not just a backend one.
- **Can a document be both?** Some tenants may genuinely want a document both annotated for training AND queryable by chat. Is `purpose` a single enum (mutually exclusive) or should it eventually support both simultaneously? This proposal treats it as mutually exclusive (simplest, matches the stated requirement); revisit only if a concrete tenant need for "both" surfaces.
