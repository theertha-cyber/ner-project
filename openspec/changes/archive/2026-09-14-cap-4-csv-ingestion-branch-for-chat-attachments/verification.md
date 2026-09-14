# Verification Plan

**Change:** cap-4-csv-ingestion-branch-for-chat-attachments
**Generated:** 2026-09-14
**Status:** 🟢 Complete — Evidence Log populated from the automated test run (recorded `2026-09-14`, attempt 1). Per the run's human waiver, verification is fully automated: passing tests plus collected evidence mark this change done; no human reviewer sign-off is required.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion | CSV file ingestion | Upload a CSV document | Given an authenticated tenant user, when they POST `/api/v1/documents` with a `.csv` file, then the response has status 201 and the body contains `id`, `filename`, `content_type`, and `status: "pending"` | tests/test_document_ingestion.py — CSV upload returns 201 | - [x] |
| 2 | document-ingestion | CSV file ingestion | Unsupported file type remains rejected | Given an authenticated tenant user, when they POST `/api/v1/documents` with a `.exe` file, then the response has status 422 and the error message lists the allowed extensions including `.csv` | tests/test_document_ingestion.py — unsupported-type 422 message lists `.csv` | - [x] |
| 3 | document-ingestion | CSV text extraction branch | CSV processing writes spans and chunks | Given a `.csv` file uploaded with purpose `query` and processed by the worker, then it is recognized as CSV media type, spans are written one per row, and chunks are generated through the existing pipeline | tests/test_document_ingestion.py — worker CSV processing writes spans/chunks | - [x] |
| 4 | document-ingestion | CSV text extraction branch | CSV with quoted delimiters and ragged rows is normalized | Given a CSV whose rows differ in column count with quoted commas, when processed, then every row contributes a span and the document reaches `processed` | tests/test_document_ingestion.py — ragged/quoted CSV parser test | - [x] |

> **Rule:** every scenario above has one row; all four must pass before archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Allow-list scope | AI may add `.csv` only to one gate (route message or worker) and miss the other, leaving the ingestion boundary and the user-facing rejection message inconsistent | Check `ALLOWED_EXTENSIONS`, `is_allowed_file()`, and the `UnsupportedFileType` message all name `.csv`; run the 422 rejection test which asserts the message lists it |
| 2 | Media-type resolution | AI may make CSV resolve only by extension, so a client declaring `text/csv` with an uninformative or absent extension is not recognized | Verify `resolve_media_type("text/csv", ...)` and `resolve_media_type(None, "data.csv", None)` both return `text/csv` |
| 3 | Chunking-path reuse | AI may invent a separate CSV chunking/embedding path instead of reusing `_shared_chunk_text` and `_embed_chunks`, violating ADR-012 | Inspect the CSV dispatch arm: after span extraction it must fall through to the identical purpose-gated chunking block used by other types |
| 4 | CSV parser edge cases | AI may parse with naive `split(",")`, breaking quoted delimiters, embedded newlines, and ragged rows | Parser must use the stdlib `csv` module; the ragged/quoted parser test must pass and assert per-row spans |
| 5 | Span model fit | AI may emit spans with invented fields (e.g., `sheet_name`) the `document_text_spans` insert cannot store | Every span dict must carry exactly `span_index`, `text`, `char_start`, `char_end`, `page_number` as the existing extractors do |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-012 CSV Support as a Branch in the Existing Ingestion Pipeline | Extend the current allow-list and worker with a CSV branch; reuse the same chunking/embedding/retrieval pipeline; no separate CSV subsystem | `.csv` acceptance goes through the existing `is_allowed_file` boundary; extraction is one new arm in `ocr_worker.py`; no new service, store, or table | Inspect diff: only `ocr_worker.py` worker logic + `documents.py` error message + tests changed; no new storage/retrieval code |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments persist as `documents` rows with nullable `conversation_id` | CSV must not introduce a different row model or attachment table | No schema/DDL change in this change; CSV lands as a normal `documents` row |
| ADR-003 Model Serving Topology | Embeddings flow through the platform's existing embedding contract | CSV chunks embed via `_embed_chunks` | CSV processing test confirms chunks written via the shared `_store_chunks` path |

---

## 4. Evidence Requirements

Evidence **MUST** be collected and logged in Section 5 before this change is archived.

### Functional Evidence

- [x] Scenario 1 — test output showing the CSV upload test passes (exit 0, 201 asserted) — `test_csv_upload_returns_201` passed; suite exit 0
- [x] Scenario 2 — test output showing the unsupported-type 422 test passes and the message lists `.csv` — `test_7_2_unsupported_file_type_returns_422` (extended, asserts `.csv` in message) and `test_csv_extension_is_supported_and_message_lists_it` passed
- [x] Scenario 3 — test output showing worker CSV processing writes one span per row and generates chunks — `test_csv_processing_writes_spans_and_chunks` passed (3 spans, chunk_count > 0)
- [x] Scenario 4 — test output showing the ragged/quoted CSV parser test passes and the document reaches `processed` — `test_csv_extractor_normalizes_quoted_and_ragged_rows` passed; document status asserted `processed`

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — allow-list, `is_allowed_file`, and rejection message all name `.csv`
- [x] Risk 2 mitigation confirmed — declaration- and extension-driven CSV media-type resolution both return `text/csv`
- [x] Risk 3 mitigation confirmed — CSV chunking reuses the shared `_shared_chunk_text`/`_embed_chunks` path
- [x] Risk 4 mitigation confirmed — parser uses stdlib `csv`; ragged/quoted test passes
- [x] Risk 5 mitigation confirmed — CSV span dicts carry exactly the five existing span fields

---

## 5. Evidence Log

Recorded from the automated test run (waiver: no human reviewer). Populated before archive.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | pytest output — `test_csv_upload_returns_201` (POST `/api/v1/documents` with `data.csv`, asserts 201, `id`, `filename`, `content_type`, `status: "pending"`) | Upload a CSV document | ralph (automated) | 2026-09-14 |
| 2 | Functional | pytest output — `test_7_2_unsupported_file_type_returns_422` (extended) and `test_csv_extension_is_supported_and_message_lists_it` (422, message lists `.csv`; `is_allowed_file`/`resolve_media_type` CSV checks) | Unsupported file type remains rejected | ralph (automated) | 2026-09-14 |
| 3 | Functional | pytest output — `test_csv_processing_writes_spans_and_chunks` (worker path: status `processed`, 3 spans, `"planning, vaguely"` survives quoting, ragged row joins, `chunk_count > 0`) | CSV processing writes spans and chunks | ralph (automated) | 2026-09-14 |
| 4 | Functional | pytest output — `test_csv_extractor_normalizes_quoted_and_ragged_rows` (3 spans, offsets, page 0, span_index 0..2) | CSV with quoted delimiters and ragged rows | ralph (automated) | 2026-09-14 |
| 5 | Structural | code review — design.md decisions match implementation (single dispatch arm, shared chunking path, no new storage/retrieval code, no schema change) | all | ralph (automated) | 2026-09-14 |
| 6 | Edge Case | risk-register mitigations 1–5 confirmed in code + tests (allow-list + message; both resolution paths; shared `_shared_chunk_text`/`_embed_chunks`; stdlib `csv`; five-span field shape) | all | ralph (automated) | 2026-09-14 |