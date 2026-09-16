## Why

`export-chat-results` shipped a way to download a large structured chat answer as CSV/XLSX, gated by a single row-count threshold that decides three things at once: whether the reply text truncates, whether "See more" appears, and whether the download option shows at all. Live testing surfaced real problems with collapsing all three into one number: a verbose single-result answer got wrongly truncated, small-but-legitimately-tabular answers couldn't be downloaded at all, and the download UI renders eagerly (full card, two format buttons) even for users who never want to export. This change decouples those three concerns and makes the export offer opt-in rather than proactive.

## What Changes

- The download offer is no longer gated by a row-count threshold — it appears whenever a turn has any structured result (`export.row_count >= 1`), independent of size.
- Text truncation ("See more") is driven by actual rendered visual overflow (a max-height/line-clamp check in the browser) rather than a hardcoded line/row count — removes `PREVIEW_LINE_LIMIT`'s role in deciding truncation.
- The download option is no longer presented proactively as a full file card. Instead, a lightweight prompt appears first, stating the actual result count (e.g. "This includes 45 results — want a downloadable version?"); the CSV/XLSX format actions only render after the user responds affirmatively.
- The export prompt is no longer positioned at the truncation boundary — since export availability and text truncation are now independent, the prompt appears below the reply whenever exportable data exists, whether or not that particular reply's text happens to truncate.

## Capabilities

### New Capabilities

(none — the two new requirements below are additions within the existing `chat-ui` capability, not a new capability)

### Modified Capabilities

- `chat-ui`: the "Inline preview truncation and file card, driven by result count" requirement (introduced by `export-chat-results`) is removed and replaced by three narrower requirements — "Inline preview truncation is independent of export availability", "Export offer appears whenever structured data exists, regardless of result count", and "Export prompt reveals download actions only after the user opts in" — each covering one of the three concerns the old requirement bundled together. "Authenticated download from the file card" is renamed to "Authenticated download from the revealed format actions" to match the new two-step mechanics (content otherwise unchanged).

## Impact

- **Frontend**: `src/portal/src/components/chat/MessageThread.tsx` (the `isTruncatable`/`PREVIEW_LINE_LIMIT` logic — truncation trigger changes from a line/row-count check to a rendered-overflow check; export-offer gating changes from `row_count > PREVIEW_LINE_LIMIT` to `row_count >= 1`; positioning of the export affordance relative to the truncation boundary changes), `src/portal/src/components/chat/ExportCard.tsx` (becomes a two-stage component: a lightweight prompt stating the row count, then the CSV/XLSX actions on confirmation — or is split into two components).
- **Backend**: none expected — `ChatResponse.export`/`MessageResponse.export` already carry `row_count`, which is all the frontend needs for both the new gating and the new prompt copy. The download endpoint and its ownership/sanitization behavior are unchanged.
- **OpenSpec bookkeeping**: `export-chat-results` archived as `2026-09-16-export-chat-results`, so the canonical `openspec/specs/chat-ui/spec.md` now contains the requirements this change renames/modifies.

## Open Questions

- Exact wording for the lightweight prompt (beyond "must state the row count") — copy is otherwise unspecified.
