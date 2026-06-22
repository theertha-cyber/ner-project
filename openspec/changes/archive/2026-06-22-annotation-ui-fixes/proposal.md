## Why

The annotation workspace built in sp-05 is functionally complete but has several UX gaps that make day-to-day annotation slow and frustrating: spans can only be created one token at a time, BIO tags are derived at export rather than stored, the focus mode is not a true fullscreen, and several controls (mark complete, sticky nav) are either hidden or unreliable. These issues are blocking annotators from working efficiently.

## What Changes

- **Drag-to-annotate**: replace single-token click-to-annotate with click-and-drag across tokens; entity type must be armed first; single-click on same token preserves existing inspector / single-token span behavior
- **BIO tag storage**: compute and persist `bio_tags TEXT[]` on every span at write time (create + retype); export reads stored tags directly with fallback for legacy rows
- **Deselect annotation**: clicking any unspanned token (when no entity type is armed) closes the span inspector
- **Mark Complete visibility**: fix disabled-state styling so the button is clearly visible and discoverable when no spans exist yet
- **Sticky navbar**: fix AppShell height chain (`minHeight` → `height: 100vh`) so the topbar never scrolls out of view; add `position: sticky` to Topbar header
- **Focus mode toggle**: replace 2-button radio (3-pane / Focus) with a single toggle button
- **Fullscreen focus mode**: entering focus mode triggers the browser Fullscreen API; Escape / toggle exits and syncs state
- **Task display name**: replace raw `doc-{uuid8}` labels with `Task N` (1-based queue position) in both the toolbar and task queue sidebar

## Capabilities

### New Capabilities

- `drag-annotation`: multi-token span creation via mouse drag; covers drag state tracking in DocumentViewer/Token, range computation from token indices, and integration with existing armed-type flow
- `bio-tag-storage`: persistence of BIO tag arrays on the spans table; covers DB migration, computation at span write time, and export read path

### Modified Capabilities

- `portal-annotation`: existing annotation workspace requirements extended with deselect behavior, mark-complete visibility, focus-mode toggle + fullscreen, and task display naming
- `app-shell`: sticky topbar requirement — layout height chain fix and `position: sticky` on Topbar

## Impact

**Frontend**
- `src/portal/src/components/annotation/AnnotationPage.tsx` — drag state, deselect, fullscreen API, task index display, focus toggle
- `src/portal/src/components/annotation/DocumentViewer.tsx` — drag event wiring
- `src/portal/src/components/annotation/Token.tsx` — `onMouseDown` / `onMouseEnter` props
- `src/portal/src/components/annotation/TaskQueue.tsx` — `Task N` labeling
- `src/portal/src/components/app-shell/AppShell.tsx` — `height: 100vh`
- `src/portal/src/components/app-shell/Topbar.tsx` — `position: sticky`

**Backend**
- `alembic/versions/009_add_bio_tags_to_spans.py` — new migration (non-breaking, nullable column)
- `src/annotation_service/api/v1/spans.py` — BIO computation at `POST` and `PATCH`
- `src/annotation_service/api/v1/export.py` — read stored `bio_tags`; fallback for NULL

**No changes** to: training pipeline, extraction service, model serving, gateway auth, AnnotationTask API shape, span-reducer action types.

## Open Questions

- None. All design decisions were resolved during exploration: ARM-first drag (not select-first), `bio_tags TEXT[]` on spans table, frontend queue-order naming.
