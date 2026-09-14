## Context

FR-002 requires the chat attachment flow to accept CSV in addition to the file types the current upload flow already supports. ADR-012 settles the approach: CSV becomes a branch in the existing ingestion pipeline, not a separate subsystem.

Today the pipeline rejects `.csv` outright: `ALLOWED_EXTENSIONS` in `src/document_service/services/ocr_worker.py` holds only `{".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx"}`, `is_allowed_file()` gates both the POST `/api/v1/documents` route and the ingestion boundary, media-type resolution has no CSV entry, and the worker's dispatch chain (PDF / image / DOCX / DOC) has no CSV arm. CAP-3 established that chat attachments are ordinary `documents` rows with a nullable `conversation_id`, so CSV ingestion needs no new data model, store, or retrieval path.

## Goals / Non-Goals

**Goals:**

- Accept `.csv` through the existing document upload contract, for both chat attachments and the tenant Documents flow (same branch, per ADR-012).
- Parse CSV rows into normalized text spans in the extraction worker, then flow through the exact chunking/embedding/retrieval path used for query documents.
- Keep the existing unsupported-file-type rejection behaviour intact, and make its error message name the real allow-list (including `.csv`).

**Non-Goals:**

- No new ingestion subsystem, service, storage type, or schema change.
- No change to conversation scoping (CAP-3), Documents-library exclusion (CAP-5), or composer UI (CAP-2).
- No resume/JD-specific modeling; CSV attachments are text-bearing documents like every other type.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-012 CSV Support as a Branch in the Existing Ingestion Pipeline | Extend the current ingestion allow-list and extraction worker with a CSV branch that parses rows into normalized text spans, then flows through the same chunking/embedding/retrieval pipeline used for query documents. | This design IS ADR-012's implementation: one media-type branch, same pipeline, no separate subsystem. |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments persist as `documents` rows with a nullable `conversation_id`; conversation ownership gates retrieval. | CSV attachments are the same row model; this capability touches no conversation logic. |
| ADR-003 Model Serving Topology | Embeddings flow through the platform's existing serving/embedding contract. | CSV chunks must use the existing `_embed_chunks` path — no new serving arrangement. |

## Decisions

### Decision 1: CSV is a media-type branch in the existing worker

**Choice:** Add `.csv` to the allow-list and add a CSV arm to the extraction dispatch in `ocr_worker.py`, reusing the span/chunk/embedding pipeline unchanged after parsing.

**Rationale:** ADR-012 mandates this over any alternative, and it is the smallest change that satisfies FR-002: the ingest entry point (`ingestion/service.py`) already delegates acceptance to `is_allowed_file`, so extending the allow-list there is the only change the boundary needs.

**Alternatives considered:**
- A separate CSV ingestion service — ruled out by ADR-012 (operational cost, duplication for one type).
- Converting CSV to an intermediary format (e.g., PDF) before ingestion — ruled out by ADR-012 (transformation loss, added complexity).

### Decision 2: Extension-driven acceptance plus declaration-aware media-type resolution

**Choice:** `.csv` joins `ALLOWED_EXTENSIONS`. Media-type resolution gains `text/csv` in the declared-type set and the extension map, so a CSV resolves whether the client declares `text/csv` or sends an uninformative/absent media type.

**Rationale:** This mirrors exactly how the existing types resolve (`resolve_media_type` tiers declaration → filename → content sniff). CSV is plain text with no reliable magic-byte signature, so content sniffing stays out of the CSV path — declaration and extension are authoritative, consistent with the pipeline's existing fallback behaviour.

**Alternatives considered:**
- Magic-prefix sniffing for CSV — ruled out: any text file would match; it would route non-CSV text into the branch.
- Leaving declaration resolution out (extension only) — rejected: a client that declares `text/csv` must not need a matching extension to be recognized; the declared type should win, as it does for every other type.

### Decision 3: One normalized text span per CSV row, cells joined

**Choice:** `extract_text_csv()` parses with the Python standard-library `csv` module (dialect-sniffing for delimiter, quoted fields) and emits one span per row: cells joined into a single normalized text line, `char_start`/`char_end` tracked, `page_number = 0`, `span_index` sequential.

**Rationale:** Row-per-span preserves the CSV's row structure for downstream chunking (each row chunks independently, as a paragraph would in a DOCX), reuses the existing span schema, and keeps the parser deterministic and testable — including the delimiter and row-shape edge cases ADR-012's consequences section requires.

**Alternatives considered:**
- Whole-file single span — ruled out: loses row granularity for retrieval and merges unrelated rows into one chunk.
- Per-cell spans — ruled out: unnecessary granularity; a row is the natural unit of meaning, and spans feed chunking anyway.

### Decision 4: The upload route's unsupported-type message names the real allow-list

**Choice:** Update the `UnsupportedFileType` message in `documents.py` to append `.csv` to the allowed list text.

**Rationale:** The message is user-facing contract text; keeping it stale while the underlying allow-list accepts CSV would make the rejection path lie. This is a one-line change in the same code path FR-002 touches.

## Risks / Trade-offs

- [CSV with ragged rows, quoted delimiters, or multi-line fields could fail extraction] → `csv` module handles quoted delimiters and embedded newlines; the parser tolerates varying column counts (cells joined for shorter rows); parser tests cover these shapes explicitly.
- [A non-CSV file renamed `.csv` is accepted and parsed as CSV text] → Identical to how the pipeline treats every other extension today; the upload contract is extension/declaration-driven, and CSV has no magic bytes to add a content check. Accepted trade-off, documented here rather than hidden.
- [CSV retrieval quality may be weaker than a well-structured document's] → CSV flows through the identical chunking/embedding path; the mitigation is parser determinism and regression coverage, not a special retrieval path (which ADR-012 forbids creating).

## Migration Plan

- Ship in one deploy alongside CAP-3/CAP-5: the allow-list addition is additive, the worker branch is reachable only when a CSV actually arrives, and no schema or storage migration is involved.
- Rollback: revert the allow-list entry, media-type additions, dispatch arm, and message text. Already-ingested CSV documents remain ordinary `documents` rows and behave exactly as other text documents.

## Open Questions

- None. ADR-012 settles the approach; no in-force ADR is being revisited.