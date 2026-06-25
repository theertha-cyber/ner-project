## Why

The annotation workspace implementation (sp05) diverges from the finalized HTML mockup in several visible and behavioural ways — task rows still show "Task N" ordinals instead of filenames (an explicitly removed requirement from sp05), the document viewer lacks the paper-card container, the span inspector and suggestion panel are in the wrong column, and several micro-interactions differ from what was designed. This change closes those gaps so the shipped UI matches the mockup.

## What Changes

- **Task queue rows** show the document filename as the primary label and `"<doc_status> · <N> spans"` as the subtitle, replacing the ordinal "Task N" label and raw status string
- **Annotation toolbar** shows the document filename (from the active task), not the task ordinal
- **Document viewer** wraps token content in a white card (`border-radius: 16px`, `padding: 36px 40px`, `box-shadow`, `max-width: 680px`) matching the mockup's paper surface aesthetic
- **Status button group** active state uses a solid primary-color fill (`background: var(--primary); color: #fff`) rather than the current subtle surface overlay
- **Entity type dots** change from 8 px circles to 11 px rounded squares (`border-radius: 3px`), matching the mockup
- **SpanInspector placement in 3-pane mode** moves from the center document column to the right entity panel, stacked below the entity palette
- **SuggestionPanel placement in 3-pane mode** moves from the center document column to the right entity panel, stacked below the span inspector
- **Armed banner text** changes to the instructional form: `"Labeling mode · click words to tag as <name>"` instead of showing the entity description
- **Focus mode span inspector** renders in a condensed single-line format (`"<text> · [charStart, charEnd] · conf <value>"`) instead of the full 2×2 metadata grid

## Capabilities

### New Capabilities

_(none — all changes are corrections to an existing capability)_

### Modified Capabilities

- `portal-annotation`: Task label display, document card layout, panel placement for inspector and suggestions, armed banner text, focus mode inspector format, entity dot shape, status button active style

## Impact

- `src/portal/src/components/annotation/TaskQueue.tsx` — label and meta display
- `src/portal/src/components/annotation/AnnotationPage.tsx` — toolbar task label, right-panel layout, panel placement for inspector and suggestions
- `src/portal/src/components/annotation/AnnotationToolbar.tsx` — toolbar filename display
- `src/portal/src/components/annotation/DocumentViewer.tsx` — card container wrapper
- `src/portal/src/components/annotation/EntityPalette.tsx` — dot shape
- `src/portal/src/components/annotation/SpanInspector.tsx` — focus mode condensed layout
- `src/portal/src/components/annotation/ArmedBanner.tsx` — banner text
- Related tests for all touched components

No API changes. No new dependencies. No changes to the backend or gateway.

## Open Questions

- The task queue `q.meta` field in the mockup shows `"processed · 12 spans"` — this is a document-level attribute (`document.status`, `document.spans`). Annotation tasks returned by `GET /annotation-tasks` may not include document span count inline. Does the backend need to be updated to include `span_count` in the annotation-task response, or should the frontend derive it separately?
- The `AnnotationTask` type currently uses `document_id` but not `filename`. The task queue filename display requires the filename to be available on the task object. Is `filename` already included in the annotation-task API response, or does it need to be added?
