# Add DOC/DOCX Upload Support

**Format version:** 1

## Summary

Add `.doc` (legacy Microsoft Word binary format) and `.docx` (modern Word XML format) to the document upload and text extraction pipeline. The current system accepts only PDF, JPEG, PNG, and TIFF. This change extends the allowed file types on both frontend and backend, adds text extraction for DOC/DOCX, and updates the spec to reflect the new supported types.

## Source

- Requested via: `/change`
- Run: triage
- Grounding: `openspec/specs/document-ingestion/spec.md` (baseline spec), `src/document_service/services/ocr_worker.py` (backend allowed extensions + extraction dispatch), `src/document_service/api/v1/documents.py` (upload endpoint + error message), `src/portal/src/components/documents/DocumentUpload.tsx` (frontend accepted types)

## Files Affected

- `src/document_service/services/ocr_worker.py` â€” Add `.doc` and `.docx` to `ALLOWED_EXTENSIONS` set (line 46); add `extract_text_docx()` function using `python-docx`; add `extract_text_doc()` function for legacy `.doc` format; update `process_document()` dispatch (line 154â€“162) to route `.docx` and `.doc` to their extractors
- `src/document_service/api/v1/documents.py` â€” Update the error message string at line 84 to list `.doc` and `.docx` in the allowed types
- `src/portal/src/components/documents/DocumentUpload.tsx` â€” Add `application/vnd.openxmlformats-officedocument.wordprocessingml.document` and `application/msword` to `ACCEPTED_TYPES` (line 6); add `.doc,.docx` to the `accept` attribute on the file input (line 202); update the helper text at line 270 to mention "DOC, DOCX"
- `openspec/specs/document-ingestion/spec.md` â€” Update "Document Upload" requirement (line 13) to include DOC and DOCX in the accepted types; update "Async OCR Processing" requirement (line 59) to describe DOC/DOCX text extraction; add a scenario for DOCX upload success
- `tests/test_document_ingestion.py` â€” Add test constants for DOCX content; add test case for uploading a `.docx` file; add test case for uploading a `.doc` file; add test case verifying unsupported type rejection still works
- `pyproject.toml` â€” Add `python-docx` dependency for DOCX text extraction

## CAP-1 â€” Add DOC/DOCX Support to Document Upload

### Summary

Extend the document upload pipeline to accept `.doc` and `.docx` files, extract text from them, and process them through the existing OCR/embedding flow.

### Requirements (ADDED)

- The system SHALL accept document uploads for `.doc` and `.docx` files in addition to existing PDF, JPEG, PNG, and TIFF formats.
- The system SHALL extract text from `.docx` files using the `python-docx` library.
- The system SHALL extract text from `.doc` files using an appropriate legacy binary extraction method.
- The frontend file picker SHALL list DOC and DOCX as accepted file types.

#### Scenario: Upload a DOCX document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a `.docx` file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status: "pending"`, `file_size`

#### Scenario: DOCX text extraction succeeds

- **GIVEN** a document with `status: "pending"` and content type `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- **WHEN** the OCR processing worker runs
- **AND** `python-docx` successfully extracts text from the DOCX
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans` with extracted text and character offsets

#### Scenario: Upload a DOC document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a `.doc` file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status: "pending"`, `file_size`

#### Scenario: Upload unsupported file type still rejected

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a `.exe` file
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate the file type is not supported

### Evidence

- Run `pytest tests/test_document_ingestion.py -k "docx"` to confirm the new DOCX upload test passes.
- Upload a `.docx` file via the portal UI and verify it appears in the document list with status `processed`.
- Upload a `.doc` file via the portal UI and verify it appears in the document list with status `processed`.
- Attempt to upload a `.exe` file and confirm the 422 rejection still works.

### Implementation Notes

- **Backend `ALLOWED_EXTENSIONS`** (ocr_worker.py:46): Add `".doc"` and `".docx"` to the set.
- **Backend extraction dispatch** (ocr_worker.py:154â€“162): Add an `elif ext in ("docx",):` branch that calls `extract_text_docx(file_data)`, and an `elif ext == "doc":` branch that calls `extract_text_doc(file_data)`. The DOCX extractor should use `python-docx` to open the document and iterate paragraphs, collecting text. The DOC extractor should use a fallback strategy (e.g., `antiword` subprocess or mark as needing OCR if no pure-Python library is available).
- **Backend error message** (documents.py:84): Update the allowed types string to `".pdf, .jpg, .jpeg, .png, .tif, .tiff, .doc, .docx"`.
- **Frontend `ACCEPTED_TYPES`** (DocumentUpload.tsx:6): Add `"application/vnd.openxmlformats-officedocument.wordprocessingml.document"` and `"application/msword"` to the array.
- **Frontend `accept` attribute** (DocumentUpload.tsx:202): Change to `".pdf,.jpg,.jpeg,.png,.tiff,.tif,.doc,.docx"`.
- **Frontend helper text** (DocumentUpload.tsx:270): Update to `"PDF, DOC, DOCX, JPEG, PNG, or TIFF (max 50MB, up to 20 files)"`.
- **New dependency**: Add `python-docx` to `pyproject.toml` dependencies. For `.doc` support, evaluate `antiword` (system package, invoked via subprocess) or accept that `.doc` files may need OCR as a fallback if no clean extraction path exists.
- **Tests**: Add a `DOCX_CONTENT` constant using a minimal valid DOCX byte sequence (or a small test fixture file). Mock the extraction function if the test doesn't want to depend on `python-docx` being installed, or use a real small DOCX if the test environment supports it.

### Out of scope for this capability

- No schema or database changes â€” the `documents` table already stores `content_type` as a varchar and `blob_path` with the extension, so no migration is needed.
- No changes to the embedding, chunking, or retrieval pipeline â€” extracted text flows through the same path as existing formats.
- No changes to the annotation service, extraction service, or chat API â€” they consume text spans, not raw files.
- No changes to MinIO storage configuration â€” the storage client already accepts arbitrary extensions.
- No changes to the async worker infrastructure â€” `trigger_ocr` and `process_document` already handle extension-based dispatch.


**Governed by:** none

## Dependency Order (Suggested Implementation Sequence)

1. CAP-1

## Summary Table

| ID | Capability | Depends On |
| --- | --- | --- |
| CAP-1 | Add DOC/DOCX Support to Document Upload | â€” |
