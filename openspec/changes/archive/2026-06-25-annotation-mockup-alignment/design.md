## Context

The annotation workspace (sp05) was implemented against an earlier spec draft. A side-by-side comparison of the HTML mockup (`docs/NER Platform.html`) against the generated code reveals eleven divergences: task rows show "Task N" ordinals instead of document filenames, the document viewer has no card container, the span inspector and suggestion panel sit in the wrong column, the armed banner text is informational rather than instructional, and several micro-level visual details differ (dot shape, status button active style, focus inspector format).

All changes are frontend-only within `src/portal/src/components/annotation/`. One backend question is open: whether the annotation-task API response already includes `filename` and `span_count`.

## Goals / Non-Goals

**Goals:**

- Replace every "Task N" reference with the document filename
- Add the paper-card wrapper to the document viewer
- Move SpanInspector and SuggestionPanel into the right entity panel (3-pane mode)
- Update armed banner to show instructional text ("Labeling mode · click words to tag as X")
- Condense the focus-mode span inspector header to a single line
- Change entity type dot from 8 px circle to 11 px rounded square (`border-radius: 3px`)
- Change status button active style to solid primary fill
- Update the right-panel entity palette header to "ENTITY TYPES" uppercase label matching the mockup
- Remove Fullscreen API calls (focus mode is CSS-only)

**Non-Goals:**

- Moving to an oklch color system — the fixed hex palette is functionally equivalent and a color-system rewrite is independent scope
- Changing the token interaction model or span creation logic
- Backend model changes beyond what is required to expose `filename` and `span_count` on the annotation-task response
- Responsive/mobile layout

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | No cross-tenant data exposure — task queue filtering by `annotator_user_id` must remain |
| ADR-004 | OpenSpec spec-driven governance | All changes require spec artifacts before implementation |
| ADR-005 | OpenCode agent permission boundaries | Frontend-only edits; no infrastructure changes permitted without explicit approval |

ADRs 002, 003, 006, 007, 008 relate to model training/serving/chatbot and do not constrain this design.

## Decisions

### Decision 1: Filename comes from the annotation-task API response (no separate document fetch)

**Choice:** Require the `GET /api/v1/annotation-tasks` response to include a `filename` field on each task object. The frontend reads `task.filename` directly.

**Rationale:** A separate `GET /documents/{id}` call per task to retrieve filenames would add N round-trips on workspace load (one per task in the queue). The annotation-task response already contains `document_id`; adding `filename` is a trivial join server-side and eliminates client-side waterfall requests.

**Alternatives considered:**
- *Fetch document details per task on mount* — rejected; O(N) requests, degrades for large queues
- *Client-side filename derivation from document_id* — rejected; document IDs are UUIDs and carry no human-readable information

### Decision 2: Span count in task queue meta comes from the annotation-task API response

**Choice:** Add a `span_count` field and `document_status` field to the annotation-task API response (populated via a JOIN in the gateway query). The task queue renders `"<document_status> · <span_count> spans"` from these fields.

**Rationale:** The mockup shows "processed · 12 spans" as the subtitle. `span_count` is a document-level aggregate that the backend can compute cheaply. Doing it client-side would require prefetching every document's span list, which is wasteful.

**Alternatives considered:**
- *Derive span count from already-loaded confirmed spans* — only works for the currently selected document; other queue items would show 0
- *Omit span count, show only document_status* — simpler but loses the informational value from the mockup

### Decision 3: SpanInspector and SuggestionPanel move to the right entity panel (3-pane)

**Choice:** Remove `SpanInspector` and `SuggestionPanel` from the center document column. Render them in the right panel below `EntityPalette`, stacked vertically with the entity palette above, inspector in the middle, and suggestions at the bottom.

**Rationale:** The mockup's right rail contains all three: entity types, span inspector, and suggestion cards. This keeps the center column purely for reading the document, which is the primary annotation activity. The current center-column placement crowds the document when inspector and suggestions both appear.

**Alternatives considered:**
- *Keep both in center but use a slide-over* — adds animation complexity; mockup doesn't show this
- *Render inspector in right, suggestions in center* — split that matches neither mockup nor logical grouping

### Decision 4: Focus-mode inspector uses condensed single-line header

**Choice:** In focus mode, replace the 2×2 metadata grid header with a single-line format: `"<span_text> · [<charStart>, <charEnd>] · conf <confidence>"`. The reassign chips and delete button remain below this header.

**Rationale:** Focus mode prioritizes reading speed. The 2×2 grid with labels (`char_start`, `char_end`, etc.) takes vertical space that is better used for the document. A single-line summary communicates the same information more compactly. The reassign and delete actions are still accessible below.

**Alternatives considered:**
- *Same 2×2 grid in both modes* — current state; too much vertical height in focus mode
- *Hide inspector entirely in focus mode* — removes a needed interaction

### Decision 5: No AnnotationTask type change for `filename` — update gateway response and frontend type

**Choice:** Update the gateway `GET /annotation-tasks` handler to JOIN with the documents table and return `filename`, `document_status`, and `span_count`. Update the `AnnotationTask` TypeScript type in `TaskQueue.tsx` to include these fields.

**Rationale:** The type is co-located with the component that uses it. Keeping the change scoped to the annotation module avoids broader type pollution.

## Risks / Trade-offs

- [Backend JOIN on documents table could slow annotation-task list queries on large tenants] → Add database index on `documents.id` if not already present; the JOIN is a simple primary-key lookup
- [Tests asserting "Task 1"/"Task 2" will break] → Update all affected test files as part of this change; no logic change, only assertion strings
- [Focus-mode condensed inspector loses the labeled metadata grid] → Acceptable trade-off per mockup; the absolute values are still present in the single-line format

## Migration Plan

1. Update gateway `GET /annotation-tasks` to include `filename`, `document_status`, `span_count` in the response
2. Update `AnnotationTask` TypeScript type to add the new fields
3. Update `TaskQueue.tsx` to render `task.filename` and subtitle
4. Update `AnnotationToolbar.tsx` to receive and display `task.filename` instead of `taskLabel`
5. Update `AnnotationPage.tsx` to remove the `taskLabel` computation and pass `task.filename` directly; restructure JSX to place SpanInspector and SuggestionPanel in the right column
6. Update `DocumentViewer.tsx` to wrap token content in the card container
7. Update `EntityPalette.tsx` to change dot to 11×11 rounded square
8. Update `ArmedBanner.tsx` to render instructional text
9. Update `SpanInspector.tsx` to add condensed focus-mode header
10. Remove fullscreen API calls from `AnnotationPage.tsx`
11. Update affected test files

No database migrations required. No new npm dependencies.

## Open Questions

- Does `GET /api/v1/annotation-tasks` already return `filename`? If so, step 1 may be a no-op and only the TypeScript type and component need updating.
- Should `span_count` in the queue subtitle reflect only confirmed spans, or confirmed + suggested? The mockup shows 12 spans for a document that has 12 confirmed spans — assuming confirmed only.
