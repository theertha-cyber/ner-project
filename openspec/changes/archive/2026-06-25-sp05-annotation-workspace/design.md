## Context

The annotation workspace frontend (`/annotation`) was originally specced against a text description of requirements, before a full UI mockup existed. The finalized NER Platform HTML prototype diverges from that spec in several significant ways: the view-mode toggle is now a radio group, the toolbar is rearchitected with an inline status control, the focus-mode entity palette moves to a bottom-center floating strip, and the span inspector uses inline chip buttons instead of a dropdown. The existing backend APIs (`/spans`, `/annotation-tasks`, `/prelabel`, `/entity-types`) are unchanged and require no modification.

This design aligns the frontend implementation with the mockup and defines the component decomposition, state ownership, and interaction contracts needed to build it correctly.

## Goals / Non-Goals

**Goals:**

- Align `portal-annotation` component tree with the finalized HTML mockup
- Define clear component boundaries and shared state ownership
- Clarify the interaction model for armed mode, status transitions, and focus mode
- Resolve the toolbar control redesign (status group replaces Mark Complete)

**Non-Goals:**

- Backend API changes — none required
- Multi-token drag selection — covered by the existing `drag-annotation` spec; not changed here
- Keyboard shortcut system beyond Escape-to-disarm
- Accessibility / ARIA audit (out of scope for this iteration)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 — OpenSpec SDD Governance | All changes require proposal → design → spec → tasks pipeline | This document fulfills the design gate |
| ADR-005 — OpenCode Agent Boundaries | Frontend agents must not call backend services directly; all data flows through the Next.js API route layer | Portal annotation page must proxy all API calls through `/api/v1/…` gateway routes, not call the Python gateway directly |

All other ADRs (001, 002, 003, 006, 007, 008) concern backend, ML infrastructure, or chatbot — none constrain this purely frontend change.

## Decisions

### Decision 1: View-mode toggle is a radio button group, not a single toggle

**Choice:** Implement the view-mode control as two explicit buttons — "3-pane" and "Focus" — styled as a pill-shaped radio group using `background: var(--surface-3)` with the active button getting a filled `var(--surface)` + shadow treatment, consistent with the mockup.

**Rationale:** The HTML prototype is unambiguous: `<button>3-pane</button>` and `<button>Focus</button>` inside a shared container. The previous spec requirement ("There SHALL NOT be separate '3-pane' and 'Focus' buttons acting as a radio group") is now superseded by the finalized mockup. A radio group communicates current state more clearly than a toggle whose label changes depending on mode.

**Alternatives considered:**
- Single "Focus" toggle (previous spec) — ruled out; conflicts with the mockup and is less scannable at a glance
- A `<select>` control — ruled out; doesn't match the pill-shaped visual pattern

### Decision 2: Task status managed via inline toolbar status group, not a dedicated "Mark Complete" button

**Choice:** The toolbar contains a three-button status group (pending → in_progress → completed). Clicking a button sends `PATCH /annotation-tasks/{id}` with the new status. The backend already enforces the state-machine constraint (422 if completing with no spans), so the UI reflects the result optimistically and reverts on error.

**Rationale:** The mockup removes "Mark Complete" entirely and replaces it with a status group, which gives annotators more control and matches how the backend already models the task lifecycle. Moving the guard logic to the backend response (422 + toast) is simpler than duplicating it in the frontend with a disabled-button tooltip.

**Alternatives considered:**
- Keep "Mark Complete" button alongside the status group — ruled out; the mockup does not include it
- Disable the `completed` button when no spans exist (replicate old guard) — ruled out; adds frontend complexity that the backend already handles via 422

### Decision 3: Focus mode floating palette is a bottom-center fixed strip, not a right-side panel

**Choice:** In focus mode, the entity palette renders as a `position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%)` glassmorphism pill containing inline entity chips and the Pre-label button. The span inspector renders as a `position: fixed; top: 140px; right: 30px; width: 290px` glass card with `backdrop-filter: blur(20px)`.

**Rationale:** The mockup specifies these exact positions and the glassmorphism treatment (`background: var(--glass); backdrop-filter: blur(22px) saturate(1.4)`). Keeping the palette bottom-center maximizes the visible document area in focus mode, which is the primary goal of the mode.

**Alternatives considered:**
- Right-side fixed panel (previous spec) — ruled out; conflicts with mockup and obscures document text
- Portal-rendered overlay — ruled out; unnecessary complexity, `position: fixed` inside the page component is sufficient

### Decision 4: Component decomposition

**Choice:** Decompose the annotation workspace into these components under `src/portal/src/app/annotation/`:

```
page.tsx                    — top-level layout, state root, data fetching
components/
  AnnotationToolbar.tsx     — toolbar: filename, status group, span counter, pre-label, view toggle
  ArmedBanner.tsx           — pulsing banner shown when entity type is armed
  TaskQueue.tsx             — left-pane task list (3-pane mode only)
  DocumentViewer.tsx        — center/main document token renderer
  EntityPanel.tsx           — right-pane in 3-pane; bottom palette in focus mode
  SpanInspector.tsx         — right-pane card (3-pane) or fixed overlay (focus mode)
  SuggestionPanel.tsx       — dashed-card list for pre-labeled suggestions (3-pane only)
```

Shared state lives in `page.tsx` via `useState`/`useReducer` and is passed down as props. No external state manager is needed for this scope.

**Alternatives considered:**
- Context/Zustand store — ruled out; prop-passing is sufficient for a single page, avoids over-engineering
- Monolithic page component — ruled out; too large to maintain, makes re-rendering difficult to control

### Decision 5: Task display name uses document filename, not "Task N" ordinal

**Choice:** Each task queue row displays the document filename field returned by the annotation-tasks list endpoint. The toolbar shows the same filename. "Task N" labels are removed.

**Rationale:** The mockup shows `invoice-2026-00417.pdf` as the task label. Filenames give annotators meaningful context for which document they're working on; ordinals were an interim placeholder.

**Alternatives considered:**
- Keep "Task N" for the queue and show filename in the toolbar — ruled out; the mockup is consistent in showing filenames everywhere

## Risks / Trade-offs

- [Status group allows jumping status freely (e.g. pending → completed directly)] → Backend returns 422 if preconditions aren't met; show a toast with the error message and revert the optimistic state update
- [Glassmorphism backdrop-filter not supported in all browsers] → Degrade gracefully: if `backdrop-filter` is unsupported, the panel still renders with `background: var(--surface)` at full opacity; functionality is unaffected
- [Filename field may not be present in the current annotation-task list response] → Verify backend response shape before implementation; if absent, add `document_filename` to the task list endpoint (small backend addition, doesn't break existing consumers)

## Migration Plan

1. Replace `portal-annotation` page component tree with the new component decomposition (no database or API migrations needed)
2. Deploy frontend; the previous behaviour is replaced in-place at `/annotation`
3. Rollback: revert the portal deployment to the previous image — no data is affected

## Open Questions

1. **State machine enforcement in UI**: Should the status group disable the `completed` button when there are no confirmed spans (client-side guard), or always allow the click and surface the backend 422? 
Answer: always allow the click and surface the 422
2. **Filename field availability**: Does `GET /api/v1/annotation-tasks` currently return `document_filename`? If not, a small backend change is needed before frontend implementation.
Answer: not filename. it should be task 1, task 2 etc.
3. **Fullscreen API in focus mode**: The new mockup does not show a fullscreen call — it shows a CSS-only focus mode. Confirm whether `document.documentElement.requestFullscreen()` should still be called, or if focus mode is now CSS-only (the mockup HTML has no Fullscreen API reference).
Answer: focus mode should be implemented like in the mockup.
