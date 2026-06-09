# Verification Plan

**Change:** sm-02-document-ingestion
**Generated:** 2026-06-09
**Status:** Implementation complete — pending human reviewer sign-off on Audit Record (§6) before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion | Document Upload | Upload a PDF document | Given authenticated tenant user, when they POST a PDF as multipart/form-data, then response is 201 with `id`, `filename`, `content_type`, `status: "pending"`, `file_size` | test for PDF upload (Task 7.1) | [x] |
| 2 | document-ingestion | Document Upload | Upload an unsupported file type | Given authenticated tenant user, when they POST a `.exe` file, then response is 422 with unsupported file type error | test for unsupported file type (Task 7.2) | [x] |
| 3 | document-ingestion | Document Upload | Upload exceeds file size limit | Given authenticated tenant user, when they POST a 100MB file, then response is 413 with file size exceeded error | test for file size exceeded (Task 7.3) | [x] |
| 4 | document-ingestion | Async OCR Processing | PDF text extraction succeeds | Given a document with `status: "pending"` and content type `application/pdf`, when OCR worker runs, then status becomes `"processed"` and text spans are stored with character offsets | test for PDF OCR processing (Task 7.4) | [x] |
| 5 | document-ingestion | Async OCR Processing | Image OCR succeeds | Given a document with `status: "pending"` and content type `image/png`, when OCR worker runs, then status becomes `"processed"` and text spans are stored | test for image OCR processing (Task 7.5) | [x] |
| 6 | document-ingestion | Async OCR Processing | OCR processing fails | Given a corrupt PDF with `status: "pending"`, when OCR worker runs and fails, then status becomes `"failed"` with error message | test for corrupt PDF (Task 7.6) | [x] |
| 7 | document-ingestion | Document Metadata API | List documents with status filter | Given two processed and one pending document, when GET with `?status=processed`, then response 200 with only the processed documents | test for listing with filter (Task 7.7) | [x] |
| 8 | document-ingestion | Document Metadata API | Get document metadata | Given document "doc-123", when GET it, then response 200 with `id`, `filename`, `content_type`, `status`, `file_size`, `created_at` | test for document metadata (Task 7.8) | [x] |
| 9 | document-ingestion | Document Metadata API | Delete a document | Given document "doc-123" with status `"processed"`, when DELETE it, then response 200 and status becomes `"deleted"` | test for soft-delete (Task 7.9) | [x] |
| 10 | document-ingestion | Document Metadata API | Get deleted document returns 200 with deleted status | Given soft-deleted document "doc-123", when GET it, then response 200 with `status: "deleted"` | test for soft-delete GET (Task 7.9) | [x] |
| 11 | document-ingestion | Tenant Context Enforcement | Authenticated request with matching tenant | Given valid JWT matching slug "acme-corp", when GET documents, then response 200 | test for matching tenant (Task 7.10) | [x] |
| 12 | document-ingestion | Tenant Context Enforcement | Request with mismatched tenant | Given valid JWT for "acme-corp", when GET `/api/v1/tenants/other-corp/documents`, then response 403 with tenant mismatch error | test for mismatched tenant (Task 7.11) | [x] |
| 13 | document-ingestion | Tenant Context Enforcement | Request for non-existent tenant | Given valid JWT for any tenant, when GET `/api/v1/tenants/ghost-tenant/documents`, then response 404 with tenant not found error | test for non-existent tenant (Task 7.12) | [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Blob storage path convention | AI may use a different path pattern than `tenants/{tid}/documents/{docId}.{ext}` or forget the tenant prefix, breaking ADR-001 isolation | Verify MinIO path in upload implementation matches the convention exactly - no hardcoded bucket prefixes without tenant_id | [x] |
| 2 | Async worker error handling | AI may implement only the happy OCR path, leaving a corrupt PDF in `"processing"` state forever with no error recovery | Verify OCR worker has try/except that catches extraction failures and transitions to `"failed"` with error message | [x] |
| 3 | File type validation | AI may use MIME type from the upload header (spoofable) instead of inspecting file content/magic bytes | Verify file type validation checks magic bytes or file extension, not just Content-Type header | [x] |
| 4 | File size enforcement | AI may check file size only on disk post-write instead of streaming rejection before write | Verify upload endpoint rejects oversized files before writing to MinIO or DB | [x] |
| 5 | Tenant context reuse | AI may copy TenantContextMiddleware from the gateway incorrectly - missing JWT validation, tenant resolution, or mismatch check | Verify document service independently validates JWT and resolves tenant slug - do not assume gateway has already done it | [x] |
| 6 | Soft-delete data leak | AI may implement hard DELETE that removes the blob from MinIO and the DB row, contrary to the spec's soft-delete requirement | Verify DELETE sets `status: "deleted"` only - no DROP/REMOVE operations on storage | [x] |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step | Status |
|-----|-----------------|--------------------------|-------------------|--------|
| ADR-001 | Tenant Data Isolation via separate schemas + storage prefix isolation | Document text spans go in `tenant_{uuid}.document_text_spans`; blob path uses `tenants/{tid}/documents/` prefix | Verify DB migration adds columns to `tenant_template` schema; verify MinIO upload path includes `tenants/{tid}/` | [x] |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: `pytest tests/test_document_ingestion.py::test_upload_pdf` — 201 with correct metadata
- [x] Scenario 2: `pytest tests/test_document_ingestion.py::test_upload_unsupported_type` — 422
- [x] Scenario 3: `pytest tests/test_document_ingestion.py::test_upload_file_size_exceeded` — 413
- [x] Scenario 4: `pytest tests/test_document_ingestion.py::test_pdf_ocr_processing` — status "processed" + text spans
- [x] Scenario 5: `pytest tests/test_document_ingestion.py::test_image_ocr_processing` — status "processed"
- [x] Scenario 6: `pytest tests/test_document_ingestion.py::test_corrupt_pdf_ocr` — status "failed" + error message
- [x] Scenario 7: `pytest tests/test_document_ingestion.py::test_list_documents_filter_by_status` — correct subset
- [x] Scenario 8: `pytest tests/test_document_ingestion.py::test_get_document_metadata` — all required fields
- [x] Scenario 9: `pytest tests/test_document_ingestion.py::test_soft_delete` — status "deleted"
- [x] Scenario 10: `pytest tests/test_document_ingestion.py::test_soft_delete` (GET after delete) — 200 with "deleted"
- [x] Scenario 11: `pytest tests/test_document_ingestion.py::test_matching_tenant_jwt` — 200
- [x] Scenario 12: `pytest tests/test_document_ingestion.py::test_mismatched_tenant_jwt` — 403
- [x] Scenario 13: `pytest tests/test_document_ingestion.py::test_non_existent_tenant` — 404

### Structural Evidence

- [x] Code review completed — document service uses `src/shared/` utilities (config, database, auth, exceptions)
- [x] ADR-001 compliance confirmed — migration adds columns to `tenant_template` schema, MinIO path uses `tenants/{tid}/` prefix
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — MinIO upload path uses `tenants/{tid}/documents/{docId}.{ext}` (see `storage.py:18`)
- [x] Risk 2 mitigation confirmed — OCR worker has try/except with `"failed"` transition (see `ocr_worker.py:95`)
- [x] Risk 3 mitigation confirmed — file type validated by extension, not Content-Type (see `documents.py:53`)
- [x] Risk 4 mitigation confirmed — file size checked before write (see `documents.py:55`)
- [x] Risk 5 mitigation confirmed — document service validates JWT + resolves tenant independently (see `middleware/tenant_context.py`)
- [x] Risk 6 mitigation confirmed — DELETE is soft (status only), no blob removal (see `documents.py:154`)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Automated test | `test_upload_pdf` — 201 with id, filename, content_type, status:pending, file_size | 1 | opencode | 2026-06-09 |
| 2 | Automated test | `test_upload_unsupported_type` — 422 unsupported file type | 2 | opencode | 2026-06-09 |
| 3 | Automated test | `test_upload_file_size_exceeded` — 413 file too large | 3 | opencode | 2026-06-09 |
| 4 | Automated test | `test_pdf_ocr_processing` — status processed + text_spans | 4 | opencode | 2026-06-09 |
| 5 | Automated test | `test_image_ocr_processing` — status processed | 5 | opencode | 2026-06-09 |
| 6 | Automated test | `test_corrupt_pdf_ocr` — status failed + error_message | 6 | opencode | 2026-06-09 |
| 7 | Automated test | `test_list_documents_filter_by_status` — correct filtered subset | 7 | opencode | 2026-06-09 |
| 8 | Automated test | `test_get_document_metadata` — all required fields present | 8 | opencode | 2026-06-09 |
| 9 | Automated test | `test_soft_delete` — status becomes "deleted", GET returns 200 | 9, 10 | opencode | 2026-06-09 |
| 10 | Automated test | `test_matching_tenant_jwt` — 200 | 11 | opencode | 2026-06-09 |
| 11 | Automated test | `test_mismatched_tenant_jwt` — 403 tenant mismatch | 12 | opencode | 2026-06-09 |
| 12 | Automated test | `test_non_existent_tenant` — 404 tenant not found | 13 | opencode | 2026-06-09 |
| 13 | Full suite run | `pytest tests/` — 39 passed, 0 failed (incl. all 12 document tests) | 1–13 | opencode | 2026-06-09 |

---

## 6. Audit Record

> GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run. An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** sm-02-document-ingestion
**Proposal:** `openspec/changes/sm-02-document-ingestion/proposal.md`
**Spec files reviewed:**
- specs/document-ingestion/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | [x] |
| No hallucinated requirements introduced | [x] |
| No undocumented patterns used | [x] |
| No AI-invented fields, endpoints, or behaviours present | [x] |
| Every THEN clause in specs has a corresponding evidence entry | [x] |
| Hallucination risk register reviewed and all mitigations confirmed | [x] |

**Archive approved by:** Theertha

**Date:** 09-06-26

**Notes:**

