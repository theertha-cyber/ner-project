## 1. Service Scaffolding & Shared Code

- [x] 1.1 Create `src/document_service/` with FastAPI app factory, `main.py` — reuse `src/shared/` imports (config, database, auth, exceptions)
- [x] 1.2 Add MinIO service to `docker-compose.yml` (port 9000, console 9001)
- [x] 1.3 MinIO env vars already present in `src/shared/config.py` (minio_endpoint, minio_access_key, minio_secret_key, minio_bucket)
- [x] 1.4 Dependencies added (PyMuPDF, pytesseract, pdf2image, boto3)

## 2. Database Migrations

- [x] 2.1 Created `003_document_service_tables.py` — adds `content_type`, `file_size`, `blob_path`, `updated_at` to `tenant_template.documents`
- [x] 2.2 Adds `span_index`, `char_start`, `char_end`, `page_number`, `created_at` to `tenant_template.document_text_spans`
- [x] 2.3 Adds `storage_used_bytes` to `public.tenants`

## 3. MinIO Blob Storage

- [x] 3.1 Implement `MinioStorageClient` in `src/document_service/services/storage.py` — upload_file(), get_file(), delete_file(), auto bucket creation
- [x] 3.2 File validation: allowed extensions check + 50MB max file size rejection at endpoint level (422/413)

## 4. Document Upload Endpoint

- [x] 4.1 POST `/api/v1/tenants/{slug}/documents` — multipart/form-data, validate, store in MinIO, DB insert with `status: "pending"`, return 201
- [x] 4.2 `TenantContextMiddleware` in `src/document_service/middleware/tenant_context.py` — JWT decode, slug→tenant resolution, active + match check
- [x] 4.3 Metadata stored in `tenant_{tid}.documents` with blob_path, file_size, content_type

## 5. Async OCR Worker

- [x] 5.1 `trigger_ocr()` in `src/document_service/services/ocr_worker.py` — create_task worker, transitions pending→processing→processed/failed
- [x] 5.2 PDF text extraction via PyMuPDF (`fitz.open`) with page-level spans and char offsets
- [x] 5.3 Image OCR via `pdf2image` + `pytesseract` for scanned/embedded images
- [x] 5.4 try/except wrapping with `status: "failed"` + error_message on any extraction failure

## 6. Document CRUD Endpoints

- [x] 6.1 GET `/api/v1/tenants/{slug}/documents` — `?status=` filter, pagination (page/per_page), ordered by `created_at DESC`
- [x] 6.2 GET `/api/v1/tenants/{slug}/documents/{doc_id}` — return all metadata fields
- [x] 6.3 DELETE `/api/v1/tenants/{slug}/documents/{doc_id}` — soft-delete (sets `status: "deleted"`, no blob removal)

## 7. Tests

- [x] 7.1 PDF upload returns 201 with correct metadata
- [x] 7.2 Unsupported file type returns 422
- [x] 7.3 File size exceeded returns 413
- [x] 7.4 PDF OCR processing — upload PDF, simulate processing, verify status "processed" and text spans
- [x] 7.5 Image OCR processing — upload PNG, simulate processing, verify status "processed"
- [x] 7.6 Corrupt PDF — verify status transitions to "failed" with error message
- [x] 7.7 List with `?status=processed` filter returns correct subset
- [x] 7.8 Get document metadata includes all required fields
- [x] 7.9 Soft-delete — status becomes "deleted", GET still returns 200 with deleted status
- [x] 7.10 Matching tenant JWT returns 200
- [x] 7.11 Mismatched tenant JWT returns 403
- [x] 7.12 Non-existent tenant slug returns 404

## 8. Verification & Evidence

- [x] 8.1 All 12 acceptance-criteria tests pass (`pytest tests/` — 39/39 total, 12/12 document-specific)
- [x] 8.2 Evidence Log populated below in verification.md § Evidence Log
- [x] 8.3 Hallucination Risk Register confirmed — all 6 mitigations verified in code
- [x] 8.4 ADR-001 compliance confirmed — tenant-isolated schemas + MinIO path prefix
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 8.6 Run `openspec validate sm-02-document-ingestion --type change --strict` and confirm it exits clean before archive.
