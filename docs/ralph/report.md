# Ralph Build Report

**Run:** run_20260903T054033Z
**Date:** 2026-09-03
**Track:** direct
**Integration Branch:** export-from-chat

## Capabilities

### CAP-1 — Add DOC/DOCX Support to Document Upload

**Status:** COMPLETED
**Slug:** cap-1-add-doc-docx-upload-support

**Files Changed:**
- `pyproject.toml` — added `python-docx` dependency
- `src/document_service/services/ocr_worker.py` — added `.doc`, `.docx` to `ALLOWED_EXTENSIONS`; added `extract_text_docx()` and `extract_text_doc()` functions; updated `process_document()` dispatch
- `src/document_service/api/v1/documents.py` — updated error message to include `.doc, .docx`
- `src/portal/src/components/documents/DocumentUpload.tsx` — added DOC/DOCX MIME types, updated `accept` attribute, updated helper text
- `openspec/specs/document-ingestion/spec.md` — updated Document Upload and Async OCR Processing requirements; added DOCX/DOC scenarios
- `tests/test_document_ingestion.py` — added DOCX_CONTENT constant; added `test_docx_upload_returns_201`, `test_doc_upload_returns_201`, `test_unsupported_type_rejection_with_doc_types`

**Specs Archived:** 0 (baseline spec updated in-place, not archived)
**Spec Rewrites:** 0

**Test Status:** Tests could not run — PostgreSQL database not available in this environment. All Python files compile cleanly. `python-docx` dependency installed successfully.

## Summary

| Metric | Value |
|--------|-------|
| Capabilities completed | 1/1 |
| Capabilities blocked | 0 |
| Capabilities skipped | 0 |
| Files changed | 6 |
| Specs archived | 0 |
| Spec rewrites | 0 |