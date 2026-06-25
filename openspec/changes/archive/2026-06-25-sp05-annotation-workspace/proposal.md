## Why

The current annotation workspace spec was written before a complete UI mockup existed, so its layout rules, component designs, and interaction patterns are misaligned with the finalized NER Platform mockup. This change supersedes those requirements with specs derived directly from the HTML prototype so that implementation produces a pixel-faithful result.

## What Changes

- **BREAKING** The view-mode control changes from a single "Focus" toggle button to a two-button radio group labeled "3-pane" / "Focus". The previous spec explicitly prohibited this; the mockup mandates it.
- The toolbar is redesigned: it now shows the document filename (JetBrains Mono), a three-state status button group (pending / in_progress / completed), a live span counter ("N confirmed · N suggested"), a ✦ Pre-label button, and the 3-pane / Focus toggle — replacing the previous "Mark Complete" button.
- Task status is now controlled inline from the toolbar status group rather than a dedicated "Mark Complete" button; the auto-disable-when-no-spans rule is removed.
- The entity type palette redesign adds a `base:` sub-label under each entity name (showing the NER base type, e.g. `base: ORG`) and right-aligns the confirmed-span count.
- The armed-mode banner gains a pulsing dot animation and an "esc · done" keyboard-shortcut hint replacing the plain text banner.
- The span inspector redesign replaces the retype dropdown with inline quick-reassign chips and presents metadata (`char_start`, `char_end`, `confidence`, `base`) in a 2×2 grid.
- Focus mode gains a **floating bottom-center label palette** (glassmorphism pill) replacing the fixed right-side panel; the floating span inspector moves to `top: 140px; right: 30px` (unchanged position but now rendered as a glass card with backdrop blur).
- The task queue left pane now shows the actual document filename and a metadata string per row (not "Task N" labels); "Task N" labeling is removed from both the queue and the toolbar.

## Capabilities

### New Capabilities

*(none — all changes are requirement updates to an existing capability)*

### Modified Capabilities

- `portal-annotation`: Toolbar layout and controls redesigned; view-mode toggle behavior changed (radio group, not single toggle); entity palette visual hierarchy updated; armed banner animation added; span inspector interaction model changed (chips instead of dropdown); focus-mode floating palette moved to bottom-center; task display switches from "Task N" labels to document filenames.

## Impact

- `src/portal/src/app/annotation/` — primary change area (page component, sub-components for toolbar, entity palette, span inspector, suggestion panel, focus-mode overlay)
- `src/portal/src/app/annotation/page.tsx` — layout restructure for 3-pane grid and focus-mode CSS
- No backend API changes required
- No `localStorage` key changes; `"ner-annotation-layout"` persists as before

## Open Questions

1. Should the toolbar status group allow free transition in any direction (pending → completed directly), or must it follow the `unannotated → in-progress → completed` state machine enforced in the existing backend spec?
Answer: free transition 
2. Does the document filename come from the task record (already in the task list response) or does it require an extra `GET /documents/{id}` fetch?
Answer: task record
3. The mockup shows `"Task N"` labels removed in favour of filenames — confirm that the backend annotation-task list endpoint already returns the document filename field.
Answer: keep "Task N" labels
