## 1. Backend — content hash helper

- [x] 1.1 Add `src/document_service/services/content_hash.py` exposing `compute_content_hash(data: bytes) -> str` returning a lowercase SHA-256 hex digest, plus a `CONTENT_HASH_ALGORITHM` constant.
- [x] 1.2 Verification: unit test covering determinism (same bytes → same hash), 64-char lowercase hex shape, and different bytes → different hash — record file name in verification.md § Spec Alignment rows 2.

## 2. Backend — upload persists checksum and identifies duplicates

- [x] 2.1 In `src/document_service/api/v1/documents.py::upload_document`, compute the content hash from `file_data` after the size check.
- [x] 2.2 Query the earliest non-`deleted` document in the tenant schema with the same `checksum` (filtering on `tenant_id`, `ORDER BY created_at LIMIT 1`) before the INSERT.
- [x] 2.3 Add `checksum` to the INSERT column list and parameters.
- [x] 2.4 Return `checksum` and `duplicate_of` on the 201 upload response.
- [x] 2.5 Add `checksum` to the `GET /api/v1/documents/{doc_id}` response.
- [x] 2.6 Verification: API tests covering spec rows 1, 3, 4, 5, 6, 7, 8 — record file names in verification.md § Spec Alignment.

## 3. Backend — schema index

- [x] 3.1 Add `alembic/versions/034_document_checksum_index.py` creating `ix_documents_checksum` on `tenant_template.documents (checksum)` and, via the `DO $$` loop pattern from migration `023`, on every provisioned `tenant_%` schema.
- [x] 3.2 Add the `checksum` column to the `documents` DDL in `tests/test_document_ingestion.py::_create_tables_sql` so the ingestion test fixtures match the live schema.

## 4. Frontend — Select all and selected count

- [x] 4.1 In `src/portal/src/components/extractions/BatchDocumentSelectModal.tsx`, derive the selectable document list (`already_extracted === false`) and the derived all-selected boolean.
- [x] 4.2 Render a "Select all" checkbox between the heading and the scrollable list; disable it when there are zero selectable documents.
- [x] 4.3 Wire its handler to add or remove exactly the selectable document IDs, never an already-extracted ID.
- [x] 4.4 Render a selected-count line below the list counting only selected selectable documents.
- [x] 4.5 Defensively filter `handleConfirm`'s submitted IDs to selectable documents only.
- [x] 4.6 Confirm no change to modal dimensions, scroll behavior, typography, buttons, per-row checkbox styling, or theme tokens.
- [x] 4.7 Verification: component tests covering spec rows 9–14 — record file names in verification.md § Spec Alignment.

## 5. Regression checks

- [x] 5.1 Confirm `POST /api/v1/extract-batch` and `run_batch_extraction` are unmodified, and `tests/test_batch_extraction.py` / `tests/test_batch_extraction_eligibility.py` still pass.
- [x] 5.2 Confirm the existing `BatchDocumentSelectModal.test.tsx` cases (disabled rows, confirm-disabled-when-empty, confirm submits checked ids, cancel) still pass unchanged.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 6.6 Run `openspec validate document-content-hash-and-batch-select-all --type change --strict` and confirm it exits clean before archive.
