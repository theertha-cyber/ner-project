## 1. Allow-list and rejection path

- [x] 1.1 Add `.csv` to `ALLOWED_EXTENSIONS` in `src/document_service/services/ocr_worker.py` so `is_allowed_file("report.csv")` returns True.
- [x] 1.2 Update the `UnsupportedFileType` message in `src/document_service/api/v1/documents.py` to list `.csv` among the allowed extensions.

## 2. Media-type resolution

- [x] 2.1 Add `MEDIA_TYPE_CSV = "text/csv"` and add `text/csv` to the declared-type set in `_media_type_from_declaration` in `ocr_worker.py`.
- [x] 2.2 Add `".csv": MEDIA_TYPE_CSV` to `_EXTENSION_MEDIA_TYPES` so filename-only resolution also recognizes CSV.

## 3. CSV extraction branch

- [x] 3.1 Add `extract_text_csv(file_bytes)` in `ocr_worker.py` using the stdlib `csv` module: one normalized text span per row (cells joined, `char_start`/`char_end` tracked, `page_number = 0`, `span_index` sequential), tolerating quoted delimiters and ragged rows.
- [x] 3.2 Add a CSV dispatch arm in `process_document` (`elif media_type == MEDIA_TYPE_CSV`) that extracts spans and falls through to the existing purpose-gated chunking/embedding path.

## 4. Tests

- [x] 4.1 Add a test in `tests/test_document_ingestion.py` that POSTs a `.csv` file and asserts status 201 with `id`, `filename`, `content_type`, `status: "pending"`.
- [x] 4.2 Extend the unsupported-type rejection test to assert the 422 message lists `.csv` among the allowed extensions.
- [x] 4.3 Add a worker-level CSV processing test asserting one span per row and chunks generated through the shared path.
- [x] 4.4 Add a parser test covering quoted delimiters and ragged row shapes, asserting the document reaches `processed` status.

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 5.2 Collect functional evidence (test output) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 5.5 Confirm verification.md Evidence Log populated — automated verification per the run's human waiver; no human reviewer sign-off task.
- [x] 5.6 Run `openspec validate cap-4-csv-ingestion-branch-for-chat-attachments --strict` and confirm it exits clean before archive.