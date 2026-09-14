# Unit — add-doc-docx-upload-support

## Scope
Unit test coverage for the DOC/DOCX upload support changes.

## Base URL
None (no deployment)

## Environment
N/A

## Test Execution
- Command: `pytest tests/test_document_ingestion.py -v`
- Result: **could not run** — PostgreSQL database unavailable (connection refused). The test suite requires a running PostgreSQL instance at `postgresql+asyncpg://ner:ner@localhost:5432/ner_test`.

## Test Cases Present
The test file `tests/test_document_ingestion.py` includes the following new test cases:

| Test ID | Description | Status |
| --- | --- | --- |
| `test_docx_upload_returns_201` | Upload a `.docx` file, verify 201 response and metadata | not run |
| `test_doc_upload_returns_201` | Upload a `.doc` file, verify 201 response and metadata | not run |
| `test_unsupported_type_rejection_with_doc_types` | Verify unsupported file types still rejected after adding DOC/DOCX | not run |

## Observations
- The new tests follow the same pattern as existing tests (mock storage and OCR trigger).
- The DOCX_CONTENT constant creates a minimal valid DOCX using zipfile, which is a good approach.
- The DOC content constant uses a minimal OLE header (`\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`).
- Existing tests (test_7_1 through test_8_5) cover the original upload, validation, and deletion flows.

## Code Coverage Analysis
- **Changed files**: `ocr_worker.py`, `documents.py`, `DocumentUpload.tsx`, `spec.md`, `tests/test_document_ingestion.py`, `pyproject.toml`
- **Test coverage**: The new test cases cover the upload endpoint for DOC and DOCX. They do not test the actual extraction functions (`extract_text_docx`, `extract_text_doc`) — those are covered indirectly through the integration tests (which also require PostgreSQL).
- **Missing test coverage**: Extraction functions with real DOC/DOCX files, error handling when antiword is unavailable, and the chunking/embedding path for DOC/DOCX documents.

## Verdict
**not run** — unit tests require PostgreSQL database. The code compiles and follows existing patterns.
