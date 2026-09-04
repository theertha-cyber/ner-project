# Code Quality — add-doc-docx-upload-support

## Scope
Light code quality review of the DOC/DOCX upload support changes (Deep Review: no).

## Base URL
None (no deployment)

## Environment
N/A

## Files Reviewed
1. `src/document_service/services/ocr_worker.py`
2. `src/document_service/api/v1/documents.py`
3. `src/portal/src/components/documents/DocumentUpload.tsx`
4. `openspec/specs/document-ingestion/spec.md`
5. `tests/test_document_ingestion.py`
6. `pyproject.toml`

## Findings

### 1. OCR Worker (`ocr_worker.py`)
- **ALLOWED_EXTENSIONS**: Correctly includes `.doc` and `.docx`. No issues.
- **extract_text_docx**: Uses `python-docx` to extract text from paragraphs. Joins with newline and strips empty paragraphs. No error handling for malformed DOCX — if `Document()` raises, the exception propagates to the caller, which catches it and sets status to 'failed'. Acceptable.
- **extract_text_doc**: Uses `antiword` subprocess with a 30-second timeout. Raises `RuntimeError` if antiword fails or is not installed. The error message is clear. However, the subprocess call uses `capture_output=True` and `text=True`, which is fine. The temporary file is cleaned up in a `finally` block. No issues.
- **process_document dispatch**: The dispatch logic (lines 201-213) correctly routes `.docx` to `extract_text_docx` and `.doc` to `extract_text_doc`. The extension is derived from `blob_path.split(".")[-1].lower()`. No edge cases (e.g., filenames with multiple dots) because the blob path is constructed by the system.
- **Error handling**: The outer try/except catches any exception from extraction and sets status to 'failed' with an error message. Good.

### 2. API Endpoint (`documents.py`)
- **Error message**: Updated to include `.doc` and `.docx`. No issues.
- **Allowed file types**: Uses the same `ALLOWED_EXTENSIONS` set from `ocr_worker.py`. Consistent.
- **No other changes**: The upload logic remains unchanged, which is correct.

### 3. Frontend Component (`DocumentUpload.tsx`)
- **ACCEPTED_TYPES**: Includes the correct MIME types for DOC and DOCX. The MIME types are correct.
- **accept attribute**: Updated to include `.doc,.docx`. Correct.
- **Helper text**: Updated to "PDF, DOC, DOCX, JPEG, PNG, or TIFF". Correct.
- **Validation**: The `validate` function checks file type against `ACCEPTED_TYPES`. If a file's MIME type is not in the list, it's rejected. This matches the backend validation.
- **No other changes**: The upload logic remains unchanged.

### 4. Spec (`spec.md`)
- **Document Upload requirement**: Updated to include DOC and DOCX. The requirement text is consistent with the implementation.
- **Async OCR Processing requirement**: Updated to describe DOCX extraction using `python-docx` and DOC extraction using `antiword`. Matches the implementation.
- **Scenarios added**: Upload DOCX, upload DOC, upload unsupported file type. All present in the spec.

### 5. Tests (`test_document_ingestion.py`)
- **New test cases**: Three new tests added, covering DOCX upload, DOC upload, and unsupported type rejection. Good.
- **Test quality**: The tests follow existing patterns, mock external dependencies, and verify response codes and metadata. They do not test the actual extraction functions (which would require `python-docx` and `antiword` to be installed and real files). That's acceptable for unit tests.
- **Existing tests**: The original tests (test_7_1 through test_8_5) are unchanged and cover the original flows.

### 6. Dependency (`pyproject.toml`)
- **python-docx**: Added as a dependency with version constraint `>=1.1.0,<2.0.0`. This is appropriate.

## Spec Alignment
The code changes align with the spec updates:
- The spec now includes DOC and DOCX in the Document Upload requirement.
- The spec includes scenarios for DOCX and DOC upload.
- The spec describes DOCX extraction using `python-docx` and DOC extraction using `antiword`.
- The code implements exactly that.

## Potential Issues
1. **No error handling for missing python-docx**: If `python-docx` is not installed, `extract_text_docx` will raise `ImportError` when called. The caller catches the exception and sets status to 'failed', but the error message will be "ImportError: No module named 'docx'". This is acceptable but could be improved with a more specific error message. However, the dependency is declared in `pyproject.toml`, so it should be installed.
2. **antiword availability**: The DOC extractor relies on `antiword` being installed. If it's not, the error message is clear. This is a runtime dependency, not a Python package. The spec mentions this fallback.
3. **No validation of extracted text**: The extraction functions return a list of spans with text, but there's no validation that the text is non-empty. If antiword returns empty text, the document will still be marked as 'processed' with empty spans. This is acceptable.

## Verdict
No blocking issues. The code quality is good, follows existing patterns, and aligns with the spec.
