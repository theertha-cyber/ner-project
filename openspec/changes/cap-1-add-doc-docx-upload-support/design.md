## Context

The document ingestion pipeline accepts PDF, JPEG, PNG, and TIFF files. The extraction dispatch in `ocr_worker.py` routes by file extension: PDFs go through PyMuPDF, images go through Tesseract OCR. The frontend upload component mirrors these types in its `ACCEPTED_TYPES` array and `accept` attribute.

Enterprise users frequently have document collections in Microsoft Word format. `.docx` is a ZIP-based XML format that can be parsed with `python-docx`. `.doc` is a legacy binary format with no clean pure-Python extraction path — `antiword` (a system utility) handles it, but is not always available. The design must accommodate both scenarios.

## Goals / Non-Goals

**Goals:**

- Add `.doc` and `.docx` to the allowed file types on both frontend and backend
- Extract text from `.docx` using `python-docx` (paragraph iteration)
- Extract text from `.doc` using `antiword` subprocess, with OCR fallback if `antiword` is unavailable
- Update the baseline spec to document the new supported types
- Add tests for DOCX upload, DOC upload, and confirm unsupported-type rejection still works

**Non-Goals:**

- Schema or database changes — `documents.content_type` and `documents.blob_path` already store arbitrary extensions
- Changes to embedding, chunking, or retrieval pipeline — extracted text flows through the same path
- Changes to annotation, extraction, or chat services — they consume text spans, not raw files
- Changes to MinIO storage configuration — the storage client already accepts arbitrary extensions
- Changes to async worker infrastructure — `trigger_ocr` and `process_document` already handle extension-based dispatch

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 | OpenSpec governance | Changes must follow the OpenSpec lifecycle |
| ADR-005 | OpenCode agent boundaries | Agent work stays within defined boundaries |

No ADRs constrain the file format support or extraction approach directly.

## Decisions

### Decision 1: Use `python-docx` for `.docx` extraction

**Choice:** Use the `python-docx` library to open `.docx` files and iterate paragraphs collecting text.

**Rationale:** `python-docx` is a mature, well-maintained pure-Python library. It handles the OOXML format natively without requiring system packages. Text extraction is straightforward: open the document, iterate `doc.paragraphs`, join text. No OCR needed.

**Alternatives considered:**
- `docx2txt` — lighter weight but less control over paragraph iteration and text structure. `python-docx` is more widely used and better documented.
- Tesseract OCR on rendered pages — works but is slower, requires image rendering, and loses text fidelity. Only suitable as a fallback.

### Decision 2: Use `antiword` subprocess for `.doc` extraction

**Choice:** Attempt to run `antiword` via `subprocess.run()` for `.doc` files. If `antiword` is not installed or fails, fall back to marking the document as needing OCR (the existing `extract_text_pdf_as_image` pattern could be adapted, but for now we raise an informative error).

**Rationale:** `antiword` is a well-known Linux utility for extracting text from `.doc` files. It produces clean text output. The subprocess approach keeps the Python code simple and delegates format handling to a proven tool. The fallback ensures the system degrades gracefully.

**Alternatives considered:**
- `textract` — wraps multiple extractors including `antiword`, but adds a heavy dependency chain. Overkill for this use case.
- ` olefile` + manual binary parsing — fragile and format-dependent. Not worth the complexity.
- OCR-only fallback — acceptable but loses text fidelity. Used only when `antiword` is unavailable.

### Decision 3: Minimal error handling for `.doc` extraction failure

**Choice:** If `.doc` extraction fails (antiword missing, corrupt file), the document status transitions to `failed` with an error message, exactly as PDF extraction failure does today.

**Rationale:** The existing error handling path in `process_document` already catches exceptions and sets `status: 'failed'` with an error message. No new error handling pattern is needed — the `.doc` extractor simply raises on failure and the existing catch block handles it.

## Risks / Trade-offs

- [antiword may not be installed in all environments] → The `.doc` extractor documents this and falls back to an error. Users can install `antiword` (`apt-get install antiword` on Debian/Ubuntu) or convert `.doc` to `.docx` before upload.
- [python-docx adds a dependency] → It is a pure-Python library with no native dependencies. Minimal impact on deployment.
- [Legacy `.doc` format is rarely used] → The effort-to-value ratio is acceptable. Most modern Word documents are `.docx`.

## Migration Plan

1. Add `python-docx` to `pyproject.toml` and run `poetry install`
2. Deploy the code changes (backend + frontend)
3. No database migration needed
4. Rollback: revert the code change; existing documents are unaffected

## Open Questions

None — all design decisions are settled by the decomposition and existing patterns.
