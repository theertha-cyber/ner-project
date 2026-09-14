## Context

The Batch Runs tab (`src/portal/src/components/extractions/BatchRunsTab.tsx`) renders inside `ExtractionPage.tsx`, which itself renders inside `AppShell.tsx`'s `<main>` element (`flex: 1; padding: 24px 28px; overflow: auto`). Today the two-column grid (run list + detail panel) participates in normal document flow with no height constraint, so as the run list grows, the whole `<main>` region scrolls — carrying the page header and tab pills out of view. The `BatchDocumentSelectModal` is unaffected (already `fixed inset-0` + internal `overflow-y-auto`); it's included in scope only as a "no regression" check.

## Goals / Non-Goals

**Goals:**
- The left-hand run list column scrolls independently within a bounded height.
- The page header, tab pills, and right-hand detail panel do not move when the run list is scrolled.
- Confirm the existing document-selection dialog behavior (centered, internally scrollable) is unaffected.

**Non-Goals:**
- Redesigning the detail panel, run cards, or dialog.
- Introducing a global app-shell layout change (e.g., making the whole `<main>` non-scrolling) — scope is limited to the Batch Runs tab's run list column.

## Currently-In-Force ADRs

None — this is a CSS/layout-only change with no architectural, data, or dependency impact.

## Decisions

### Decision 1: Bound the run list column height with `max-height` + `overflow-y: auto`, not a page-level flex/`h-screen` restructure

**Choice:** Give the left column a `max-height` derived from the viewport (e.g., `calc(100vh - <offset for header/tabs/padding>)`) and `overflow-y: auto`, leaving the right detail panel and outer page layout otherwise unchanged.

**Rationale:** Matches the user's explicit ask ("only the Runs list scrollable, not the actual page") with a minimal, localized change. Avoids touching `AppShell.tsx` or `ExtractionPage.tsx`, which are shared by the other two tabs (Playground, Entity Review) and would risk regressions there.

**Alternatives considered:**
- Restructure `AppShell`'s `<main>` to `overflow: hidden` and make every tab manage its own scroll region — ruled out as it changes behavior for Playground and Entity Review tabs, which is out of scope and against "nothing else right now."
- Use `position: sticky` on the header/tabs instead of bounding the list — ruled out because the right detail panel would still be able to grow the page, and it doesn't scope the fix to "only the run list."

## Risks / Trade-offs

- [A hardcoded `calc(100vh - Npx)` offset may misalign if the header/tab pill height changes later] → Compute the offset from the actual rendered chrome (e.g., wrap in a flex column with `flex: 1; min-height: 0` on the list container instead of a magic-number `calc()`), so it adapts automatically.
- [Right detail panel content could still be taller than the viewport, still causing outer `<main>` scroll] → Out of scope per proposal; only the run list's independent scroll behavior is required. Note this as an accepted trade-off, not a regression, since detail-panel scroll behavior is unchanged from today.

## Migration Plan

Pure frontend CSS/layout change in one component; no data migration. Deploy via normal portal build/release. Rollback is a straight revert of the component diff — no state, schema, or API involved.

## Open Questions

None.
