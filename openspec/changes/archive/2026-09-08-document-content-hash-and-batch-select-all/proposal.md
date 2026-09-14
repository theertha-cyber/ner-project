## Why

Two gaps remain around batch extraction and the documents that feed it.

1. **No content identity for uploaded documents.** `upload_document` (`src/document_service/api/v1/documents.py:41`) persists `filename`, `content_type`, `file_size`, `blob_path`, and `purpose`, but never populates the `checksum VARCHAR(64)` column that `tenant_template.documents` has declared since migration `002`. The same physical file uploaded twice under two different filenames produces two unrelated document records, two OCR runs, two extraction runs, and duplicated entities — with nothing in the system able to tell that the content is identical.

2. **Batch document selection has no bulk control.** `BatchDocumentSelectModal.tsx` already renders already-extracted documents disabled (shipped by `batch-extraction-document-selection`), but a user with dozens of eligible documents must tick every checkbox individually, and the modal gives no feedback on how many documents a run will actually cover.

## What Changes

**Document content hashing (document-ingestion)**

- Compute a deterministic SHA-256 hex digest over the uploaded file bytes at upload time, in a single shared helper, and persist it into the existing `documents.checksum` column.
- Before insert, look up any existing non-deleted document in the same tenant schema with the same checksum, and return its ID as `duplicate_of` on the upload response.
- Duplicates are **identified and linked, never rejected or merged.** The upload still succeeds with its own document ID, its own blob, its own OCR run, and its own extraction history. No existing record is mutated or deleted.
- Add a checksum index to `tenant_template.documents` and to every already-provisioned tenant schema.
- Expose `checksum` on the document-metadata GET response.

**Batch document selection (portal-extraction-page)**

- Add a "Select all" checkbox directly under the modal heading, operating only on documents with `already_extracted: false`.
- Add a selected-count line showing how many selectable documents are currently selected.
- Disable "Select all" when the modal contains zero selectable documents.
- No change to modal dimensions, scroll behavior, typography, buttons, checkbox styling, or theme handling.

**Explicitly out of scope**

- `POST /api/v1/extract-batch` is unchanged. The worker already excludes already-extracted documents (`worker.py:137`), so the "disabled documents never get extracted" invariant is already enforced server-side; adding a second rejection path would duplicate the idempotency logic and change the documented explicit-`documentIds` contract for non-UI callers.
- No merging, deduplication, or deletion of existing document records.
- No backfill of `checksum` for documents uploaded before this change.
- Tenant aliases, vocabulary clustering, cardinality rules, normalization metrics, and extraction quality gates are separate future changes.

## Capabilities

### New Capabilities

(none — this extends existing capabilities)

### Modified Capabilities

- `document-ingestion`: new requirement covering content hashing and duplicate identification on upload.
- `portal-extraction-page`: new requirement covering bulk selection in the batch document-selection modal.

## Impact

- `src/document_service/services/content_hash.py` (new): `compute_content_hash(data: bytes) -> str`.
- `src/document_service/api/v1/documents.py`: compute + persist `checksum`, duplicate lookup, `checksum`/`duplicate_of` on responses.
- `alembic/versions/034_document_checksum_index.py` (new): checksum index on `tenant_template.documents` and all provisioned tenant schemas.
- `src/portal/src/components/extractions/BatchDocumentSelectModal.tsx`: "Select all" control and selected-count line.
- `tests/test_document_content_hash.py` (new), `tests/test_document_ingestion.py` (test-fixture DDL gains `checksum`), `src/portal/src/components/extractions/BatchDocumentSelectModal.test.tsx`.

## Open Questions

- Should the portal surface `duplicate_of` in the upload UI (e.g. "identical to X")? Deferred — this change establishes the identity signal; the UX for it can follow once the data exists.
- Should pre-existing documents be backfilled with checksums by re-reading their MinIO blobs? Deferred — a backfill job is independent of this change and can run later without schema churn.
