## Why

When a chat answer is backed by a large structured result (e.g. "give me candidates who know python"), the LLM's prose reply either truncates the result set to fit the token budget or produces an unwieldy wall of text. There's no way for a user to get the full, complete result out of the chat — they can only see what the model chose to summarize. ChatGPT and similar products solve this by rendering a compact file card once a result crosses a size threshold, with the full data available as a download. We want the same behavior here: small results stay inline, large ones become a CSV/XLSX download.

## What Changes

- Persist a structured row snapshot for a chat turn when the RAG pipeline used SQL/structured retrieval, captured from `ChatState.sql_results` (the full, pre-token-budget result — see `chat-api` `SQL query generation and validation` requirement) rather than the token-budget-truncated `AdmittedEvidence.rows` used to build the LLM prompt.
- Add a `GET /api/v1/chat/messages/{message_id}/export?format=csv|xlsx` endpoint that streams the snapshot as a downloadable file.
- Add an `export` field to `ChatResponse` (message_id, row_count, available formats) so the portal knows whether a download is available for a turn, without inlining the rows into the chat payload itself.
- Add a display threshold: when a turn's structured result exceeds the threshold (row count and/or the existing `sql_completeness`/`AdmittedEvidence.rows_truncated` truncation signal), the portal SHALL show a file card instead of/in addition to the full inline table, mirroring the existing citation-chip pattern in `MessageThread.tsx`.
- Add CSV and XLSX generation (stdlib `csv` for CSV; a new `openpyxl` dependency for XLSX).

## Capabilities

### New Capabilities

- `chat-export`: The export endpoint itself — request/response contract, supported formats (CSV, XLSX), row-snapshot persistence, size limits, and access control (same tenant/user scoping as the owning conversation).

### Modified Capabilities

- `chat-api`: `ChatResponse` gains an `export` field describing export availability for the turn; the turn-persistence path (`_persist_turn_and_respond`) gains a row-snapshot write when structured retrieval was used.
- `chat-ui`: `MessageThread.tsx` gains a file-card component shown when a turn's export is available and its result exceeds the inline-display threshold, alongside the existing source-citation chips.

## Impact

- **Backend**: `src/chat_api/api/v1/schemas.py` (`ChatResponse` field), `src/chat_api/api/v1/chat.py` (`_persist_turn_and_respond`, new export route), `src/chat_api/graph/state.py`/`nodes.py` (surface `sql_results` to the persistence step), a DB migration to store the snapshot (new column or table under the tenant schema, sized for up to 1000 rows per the existing `sql_generator.py` LIMIT cap), `pyproject.toml` (add `openpyxl`).
- **Frontend**: `src/portal/src/components/chat/MessageThread.tsx` (new file-card component), `src/portal/src/app/(auth)/chat/page.tsx` or its fetch layer (download call), possibly a new `ExportCard.tsx` component alongside `CitationChips.tsx`.
- **No changes** to SQL generation, guardrails, or the RAG orchestration pipeline itself — this only adds a persistence and delivery path for a result set that's already being computed.

## Open Questions

- What row-count/size threshold should switch a turn from inline display to a file card? (Candidate signals: reuse `AdmittedEvidence.rows_truncated`/`sql_completeness` directly, or set an independent row-count threshold, e.g. >20 rows.)
- Where should the row snapshot live — a new column on `chat_messages` (e.g. `export_rows JSONB`), or a separate `chat_message_exports` table? Affects retention/cleanup and row-size limits on the messages table.
- Retention: does the snapshot live as long as the message (indefinite), or expire independently (e.g. 30/90 days) to bound storage growth?
- Is XLSX generation server-side (via `openpyxl`) the right call for v1, or is CSV-only sufficient to start, with XLSX added later? (Proposal currently assumes both.)
- Should the widget/embeddable chat surface (separate rate limit tier per `chat-api` `Rate limiting` requirement) get export in v1, or is this portal-only to start?
- Does export apply only to the SQL/structured source, or should it also cover cases where the reply is built purely from document-chunk/semantic sources (out of scope as currently framed — structured rows only)?
