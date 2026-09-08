## Why

On the Batch Runs tab, the run list (left column) and detail panel (right column) sit inside the page's normal document flow, so a long run list grows the whole page and the browser scrolls the entire `/extractions` page — header, tab pills, and all — instead of just the run list. This makes the header and tabs scroll out of view while browsing runs. Additionally, the "New batch run" document-selection dialog should stay centered on screen with only its document checklist scrollable, matching existing behavior.

## What Changes

- Constrain the Batch Runs tab's left-hand run list to its own scrollable region (fixed/bounded height, `overflow-y: auto`) so scrolling the run list no longer scrolls the page.
- Keep the page-level chrome (header, tab pills) and the right-hand detail panel non-scrolling relative to the run list — only the run list column scrolls internally.
- No changes to the `BatchDocumentSelectModal` dialog — it already renders centered (`fixed inset-0 flex items-center justify-center`) with an internally scrollable document list (`overflow-y-auto` within a `max-h-[80vh]` panel); verify this remains intact and unaffected by the run list change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `portal-extraction-page`: The "Batch Runs Tab — Batch Extraction Management" requirement's layout description is amended to specify that the left-hand run list column is independently scrollable within a bounded height, rather than growing the page.

## Impact

- `src/portal/src/components/extractions/BatchRunsTab.tsx` — left column layout/styling only.
- No API, hook, or data-model changes.
- No changes to `BatchDocumentSelectModal.tsx` (confirmed already correct; covered by verification, not implementation).

## Open Questions

- None — CSS/layout-only change scoped to one component.
