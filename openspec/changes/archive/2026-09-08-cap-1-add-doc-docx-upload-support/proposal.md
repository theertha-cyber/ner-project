## Why

The document ingestion pipeline currently accepts only PDF, JPEG, PNG, and TIFF files. Many enterprise users have existing document libraries in Microsoft Word format (`.doc` and `.docx`). Adding support for these formats removes a friction point and enables users to upload their existing document collections without converting them first.

## What Changes

- Add `.doc` and `.docx` to the backend allowed file extensions set
- Add a `python-docx`-based text extractor for `.docx` files
- Add a `.doc` legacy extractor using `antiword` subprocess or OCR fallback
- Update the upload endpoint error message to list the new types
- Add `application/msword` and `application/vnd.openxmlformats-officedocument.wordprocessingml.document` to the frontend accepted MIME types
- Update the frontend file input `accept` attribute and helper text
- Update the baseline spec to document DOC/DOCX support
- Add `python-docx` as a project dependency
- Add tests for DOCX upload, DOC upload, and confirm unsupported-type rejection still works

## Capabilities

### New Capabilities

_(none — this extends an existing capability)_

### Modified Capabilities

- `document-ingestion`: The Document Upload requirement expands accepted types to include DOC and DOCX; the Async OCR Processing requirement adds DOC/DOCX text extraction descriptions

## Impact

- **Backend code**: `ocr_worker.py` (new extractors + dispatch), `documents.py` (error message)
- **Frontend code**: `DocumentUpload.tsx` (accepted types, accept attribute, helper text)
- **Specs**: `openspec/specs/document-ingestion/spec.md` (requirement updates)
- **Dependencies**: `pyproject.toml` gains `python-docx`
- **Tests**: `tests/test_document_ingestion.py` (3 new test cases)

## Open Questions

- For legacy `.doc` extraction: `antiword` is a system package. If unavailable in the deployment environment, `.doc` files will need OCR fallback. This is acceptable for now — the extraction function documents the fallback.
