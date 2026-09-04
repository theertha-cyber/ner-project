## 1. Setup

- [x] 1.1 Add `python-docx` to `pyproject.toml` dependencies
- [x] 1.2 Run `poetry install` to install the new dependency

## 2. Backend Implementation

- [x] 2.1 Add `.doc` and `.docx` to `ALLOWED_EXTENSIONS` set in `ocr_worker.py`
- [x] 2.2 Add `extract_text_docx()` function using `python-docx` in `ocr_worker.py`
- [x] 2.3 Add `extract_text_doc()` function using `antiword` subprocess in `ocr_worker.py`
- [x] 2.4 Update `process_document()` dispatch to route `.docx` and `.doc` to their extractors
- [x] 2.5 Update error message in `documents.py` to list `.doc` and `.docx` in allowed types

## 3. Frontend Implementation

- [x] 3.1 Add DOC and DOCX MIME types to `ACCEPTED_TYPES` array in `DocumentUpload.tsx`
- [x] 3.2 Add `.doc,.docx` to the `accept` attribute on the file input
- [x] 3.3 Update helper text to mention "DOC, DOCX"

## 4. Spec Updates

- [x] 4.1 Update baseline spec `openspec/specs/document-ingestion/spec.md` Document Upload requirement to include DOC and DOCX
- [x] 4.2 Update baseline spec Async OCR Processing requirement to describe DOC/DOCX extraction
- [x] 4.3 Add DOCX upload success scenario to baseline spec

## 5. Tests

- [x] 5.1 Add DOCX_CONTENT test constant to `test_document_ingestion.py`
- [x] 5.2 Add test case for uploading a `.docx` file
- [x] 5.3 Add test case for uploading a `.doc` file
- [x] 5.4 Add test case verifying unsupported type rejection still works

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (requires PostgreSQL)
- [ ] 6.2 Collect functional evidence (test output) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required)
- [x] 6.6 Run `openspec validate cap-1-add-doc-docx-upload-support --strict` and confirm it exits clean before archive
