## Context

The annotation workspace (`src/portal/src/components/annotation/`) renders a toolbar with a three-way status pill group. `AnnotationToolbar.handleStatusClick` PATCHes `/api/v1/annotation-tasks/{id}` optimistically and rolls back on error. The backend (`src/annotation_service/api/v1/tasks.py`) enforces a transition table:

```python
valid_transitions = {
    "unannotated": ["in-progress"],
    "in-progress": ["completed"],
}
```

`completed` has no entry, so every click on a completed task's `in_progress` or `pending` button yields `422 INVALID_TRANSITION` — a UI affordance that is guaranteed to fail. Separately, `AnnotationPage` promotes `unannotated` → `in-progress` lazily at three call sites (token click, drag mouseup, suggestion promote), each with a duplicated `sentInProgressRef` guard.

Span edits already persist immediately (each span POST/DELETE hits the API), so there is no dirty-buffer "Save" to implement — "save" is already continuous. The requested "Mark as Completed saves and completes" therefore means: settle in-flight writes, then complete.

## Goals / Non-Goals

**Goals:**

- Remove the status selector from the toolbar; status becomes a read-only badge.
- Promote a task to `in-progress` once, on task open, in one place.
- Add a bottom action bar with a primary "Mark as Completed" button.
- Make `completed` terminal in both UI and API, while allowing idempotent re-completion.

**Non-Goals:**

- Freezing span edits on completed tasks (span endpoints stay status-agnostic).
- Any admin "reopen task" capability — no reopen path is being added anywhere.
- Reworking span persistence into an explicit dirty-buffer save model.
- Changing the task queue's own rendering beyond reflecting status.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation | Per-tenant Postgres schemas; queries resolve schema from tenant context | Task status reads/writes keep using `_schema(tenant_id)`; no cross-schema queries introduced |
| ADR-004 OpenSpec Governance | Spec-driven flow — spec deltas precede implementation | Behaviour changes land as delta specs in this change before code |
| ADR-005 OpenCode Agent Boundaries | Agents edit only within declared scope | Edits confined to the annotation portal components, tasks API, and their tests |

ADR-002, ADR-003, ADR-006, ADR-007, ADR-008 concern model strategy, serving topology, training infrastructure, and chatbot architecture — not applicable to this change.

## Decisions

### Decision 1: Promote to `in-progress` on task selection, not on first span

**Choice:** Move the `unannotated` → `in-progress` PATCH into the task-selection effect in `AnnotationPage`, keeping the `sentInProgressRef` session guard. Remove the three inline promotion blocks from `handleTokenClick`, the drag mouseup handler, and `handlePromote`.

**Rationale:** The user requirement is "every task opens In Progress by default". One call site removes three duplicated guards and makes the badge truthful the moment the document renders.

**Alternatives considered:**
- Keep lazy promotion and just relabel the badge — ruled out: badge would lie until the first edit, and doesn't satisfy the stated requirement.
- Promote server-side on `GET /documents/{id}` — ruled out: read endpoints should not mutate state, and the document endpoint has no task context.

### Decision 2: `completed` → `completed` is an idempotent 200

**Choice:** Add `"completed": ["completed"]` to `valid_transitions`. The `NO_SPANS` check still runs; the UPDATE is a harmless self-write.

**Rationale:** Re-visiting a finished document, editing, and pressing "Mark as Completed" must not error. Idempotence keeps the client dumb — it always sends the same payload — while leaving genuine reopen attempts (`completed` → `in-progress`) rejected exactly as today.

**Alternatives considered:**
- Client hides/disables the button when already completed — ruled out: user explicitly wants to re-save edits on a revisited document.
- Return 204/short-circuit before the span check — ruled out: keeps the guard uniform and the response shape identical for all completions.

### Decision 3: New `AnnotationActionBar` component in the existing grid row 4

**Choice:** Extract a presentational `AnnotationActionBar.tsx` (props: `task`, `isCompleting`, `saveState`, `onMarkCompleted`) and mount it at `gridColumn: "1 / -1", gridRow: 4` of the workspace grid. `AnnotationPage` owns the `handleMarkCompleted` callback and the completing/save state.

**Rationale:** The workspace grid already declares `gridTemplateRows: "auto auto 1fr auto"` with an unused fourth row — the bar drops in without layout surgery. Keeping the fetch in `AnnotationPage` matches how every other mutation on the page is owned there and keeps the bar testable in isolation.

**Alternatives considered:**
- Put the button inside `SpanInspector` or the right rail — ruled out: not visible in Focus mode, and the user asked for bottom-of-page.
- Self-fetching action bar mirroring the old toolbar pattern — ruled out: the optimistic-fetch-inside-toolbar pattern is exactly what this change is removing.

### Decision 4: Save indicator is derived, not a new persistence layer

**Choice:** Track a `pendingWrites` counter (incremented around span create/delete/promote requests) and render "Saving…" / "All changes saved". `handleMarkCompleted` awaits the in-flight request settling before issuing the PATCH.

**Rationale:** Gives the "save" half of the button honest meaning without inventing a dirty buffer. The optimistic span state already exists in `span-reducer`; the counter is display-only.

**Alternatives considered:**
- Buffer edits and flush on click — ruled out: large refactor of span persistence, contradicts current optimistic-write design, risks data loss on navigation.
- No indicator, button label only — ruled out: users lose the signal that edits already persisted.

## Risks / Trade-offs

- [Tasks stuck in `in-progress` because merely opening a task promotes it] → Acceptable and intended by the requirement; `unannotated` remains the pre-open state and the queue filter still distinguishes it.
- [Idempotent self-transition masks a genuine double-submit] → Button disabled while the request is in flight; the write is a no-op either way.
- [Removing `onStatusChange` breaks existing toolbar tests] → `AnnotationToolbar.test.tsx` and `AnnotationPage.test.tsx` updated in the same change; old status-group assertions deleted, not skipped.
- [Completed tasks stay editable, so a "finished" annotation can silently change] → Out of scope per proposal; flagged as an open question rather than silently locked.

## Migration Plan

1. Backend transition-table change first (backward compatible — only widens what is accepted).
2. Portal changes: toolbar strip, selection-time promotion, action bar.
3. Update frontend and backend tests together with the code.
4. No data migration; existing task rows keep their status values.
5. Rollback: revert the portal commit; the backend's extra idempotent transition is harmless if left in place.

## Open Questions

- Should completing a task lock further span edits? Current behaviour (edits allowed) is preserved; if locking is wanted it needs its own change with a status guard on the span endpoints.
- Should a `tenant_admin` be able to reopen a completed task for rework? Deliberately not added — would require a new, explicitly admin-gated transition.
- No in-force ADR needs revisiting for this change.
