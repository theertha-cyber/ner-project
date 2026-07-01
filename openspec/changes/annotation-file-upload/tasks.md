## 1. Database Migration

- [x] 1.1 Create Alembic migration that adds `imported_annotations` table to the tenant template schema with columns: `id UUID PK`, `tokens TEXT[]`, `tags TEXT[]`, `source_file VARCHAR`, `row_index INTEGER`, `created_at TIMESTAMPTZ`
- [x] 1.2 Run migration against local database and verify table creation in test tenant schema

## 2. Import Endpoint

- [x] 2.1 Create `src/annotation_service/api/v1/import_.py` with `APIRouter` and `POST /api/v1/annotation-import` route accepting `UploadFile`
- [x] 2.2 Implement JSONL parser: read file line by line, parse each line as JSON, validate `tokens` and `tags` arrays exist and have equal length
- [x] 2.3 Implement CoNLL TXT parser: read file, group lines by blank-line separators, extract token/tag pairs, reject lines without tab separator
- [x] 2.4 Implement entity type validation: collect all unique entity tags (stripping B-/I- prefix), query `public.entity_definitions` for tenant, reject if any unknown types found — return 422 listing unknown types
- [x] 2.5 Implement persistence: batch-insert validated rows into `imported_annotations` with source filename and row index
- [x] 2.6 Add file size validation (50MB max) and MIME type acceptance as per spec
- [x] 2.7 Register the import router in `src/annotation_service/main.py`

## 3. Export Endpoint Modification

- [x] 3.1 In `src/annotation_service/api/v1/export.py`, add a second query to fetch all rows from `imported_annotations` for the tenant
- [x] 3.2 For each imported row, serialize `{"tokens": ..., "tags": ...}` as a JSONL line, applying the `entity_types` filter if present (replace non-matching tags with O)
- [x] 3.3 Append imported JSONL lines after all document-derived lines in the response

## 4. Tests

- [x] 4.1 Write unit test for JSONL parser: valid input, malformed JSON, empty file, token/tag length mismatch
- [x] 4.2 Write unit test for CoNLL parser: valid input, trailing newlines, tab vs space separators, Unicode tokens
- [x] 4.3 Write unit test for entity type validation: known types pass, unknown types return 422 with list
- [x] 4.4 Write integration test: upload valid JSONL via `POST /api/v1/annotation-import`, verify 201 and DB has rows
- [x] 4.5 Write integration test for export merge: insert spans + imported rows, call export, verify both appear in output
- [x] 4.6 Write integration test for export entity type filter: verify non-matching tags replaced with O in imported rows
- [x] 4.7 Write integration test: upload file exceeding 50MB returns 413
- [x] 4.8 Write integration test: upload CoNLL file returns 201 with correct imported_count

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 5.2 Collect functional evidence (test output / API trace) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 5.6 Run `openspec validate annotation-file-upload --type change --strict` and confirm it exits clean before archive
