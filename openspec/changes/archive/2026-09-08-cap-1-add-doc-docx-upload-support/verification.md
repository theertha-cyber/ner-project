# Verification Plan

**Change:** cap-1-add-doc-docx-upload-support
**Generated:** 2026-09-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion | Document Upload | Upload a DOCX document | Given an authenticated tenant user with a valid JWT, when they POST to `/api/v1/documents` with a `.docx` file, then the response has status 201 and contains id, filename, content_type, status "pending", file_size | `test_docx_upload_returns_201` | - [ ] |
| 2 | document-ingestion | Document Upload | Upload a DOC document | Given an authenticated tenant user with a valid JWT, when they POST to `/api/v1/documents` with a `.doc` file, then the response has status 201 and contains id, filename, content_type, status "pending", file_size | `test_doc_upload_returns_201` | - [ ] |
| 3 | document-ingestion | Document Upload | Upload an unsupported file type | Given an authenticated tenant user, when they POST to `/api/v1/documents` with a `.exe` file, then the response has status 422 and the error message indicates the file type is not supported | `test_unsupported_file_type_returns_422` | - [ ] |
| 4 | document-ingestion | Async OCR Processing | DOCX text extraction succeeds | Given a document with status "pending" and DOCX content type, when the OCR worker runs and python-docx extracts text, then the status is updated to "processed" and text spans are inserted | `test_docx_ocr_processing` | - [ ] |
| 5 | document-ingestion | Async OCR Processing | DOC text extraction succeeds | Given a document with status "pending" and DOC content type, when the OCR worker runs and antiword extracts text, then the status is updated to "processed" and text spans are inserted | `test_doc_ocr_processing` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | DOCX extraction function | AI may invent incorrect python-docx API calls or not iterate paragraphs correctly | Review `extract_text_docx()` — confirm it opens the document and iterates `doc.paragraphs`, joining text |
| 2 | DOC extraction fallback | AI may assume antiword is always available without handling the subprocess failure case | Review `extract_text_doc()` — confirm it catches `FileNotFoundError` and `subprocess.CalledProcessError`, raising a descriptive error |
| 3 | ALLOWED_EXTENSIONS update | AI may forget to add both `.doc` and `.docx` to the set, or add them in the wrong format (without leading dot) | Verify `ALLOWED_EXTENSIONS` contains exactly `{".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx"}` |
| 4 | Frontend MIME types | AI may add the MIME types but forget to update the `accept` attribute or helper text | Check all three locations: `ACCEPTED_TYPES` array, `accept` attribute on `<input>`, and the helper text paragraph |
| 5 | Error message update | AI may update the backend error message but not the frontend validation error message | Check both `documents.py` line 84 and `DocumentUpload.tsx` validate function's error message |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| No constraining ADRs | — | — | — |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test output showing `test_docx_upload_returns_201` passes with exit 0
- [ ] Test output showing `test_doc_upload_returns_201` passes with exit 0
- [ ] Test output showing `test_unsupported_file_type_returns_422` passes with exit 0
- [ ] Test output showing `test_docx_ocr_processing` passes with exit 0
- [ ] Test output showing `test_doc_ocr_processing` passes with exit 0
- [ ] Full test suite (`pytest`) passes with no regressions

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code

### Edge Case Evidence

- [ ] DOCX extraction handles empty documents (no paragraphs)
- [ ] DOC extraction gracefully fails when antiword is not installed
- [ ] Frontend validation rejects `.exe` files with correct error message

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

**Change slug:** cap-1-add-doc-docx-upload-support
**Proposal:** `openspec/changes/cap-1-add-doc-docx-upload-support/proposal.md`
**Spec files reviewed:**
- `specs/document-ingestion/spec.md`

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
