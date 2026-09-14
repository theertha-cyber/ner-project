## Why

Chat attachments (CAP-3) must accept CSV in the same ingestion flow as the existing supported file types, per FR-002 and ADR-012. Today the document ingestion pipeline rejects `.csv` outright; CSV is the one newly required input type and must enter the existing pipeline as a branch rather than a separate subsystem.

## What Changes

- Extend the ingestion allow-list (`ALLOWED_EXTENSIONS` / `is_allowed_file`) to accept `.csv`.
- Update the upload API's unsupported-file-type error message to list `.csv` among the allowed types.
- Resolve CSV media types (`text/csv` and variants) in the worker's media-type resolution so a CSV file is recognized from declaration, filename, or content sniff.
- Add a CSV extraction branch in `ocr_worker.py` that parses rows into normalized text spans and flows through the existing span/chunk/embedding path.
- Keep existing file-type rejection behaviour intact for types outside the allow list.

## Capabilities

### New Capabilities

- _None._ CSV support extends an existing pipeline; no new capability is introduced.

### Modified Capabilities

- `document-ingestion`: the accepted upload file set gains `.csv`, and the extraction worker gains a CSV media-type branch that parses rows into normalized text spans feeding the existing chunking/embedding/retrieval pipeline. Unsupported file types continue to be rejected with the existing 422 path.

## Impact

- `src/document_service/services/ocr_worker.py` — allow-list, media-type resolution, CSV extraction branch.
- `src/document_service/api/v1/documents.py` — unsupported-type error message listing allowed extensions.
- `src/document_service/ingestion/service.py` — no change required; it already delegates to `is_allowed_file`.
- `tests/test_document_ingestion.py` — CSV accept/parse coverage and existing file-type rejection regressions.
- No schema, storage, retrieval, or portal changes. No new dependency: CSV parsing uses the Python standard library `csv` module.

## Open Questions

- None. ADR-012 settles the approach: CSV is a branch in the existing ingestion worker, never a separate subsystem.