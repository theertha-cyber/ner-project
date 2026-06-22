## Context

The annotation workspace (`AnnotationPage.tsx`) manages a task status lifecycle: `unannotated → in-progress → completed`. The frontend tracks this locally via `taskStatuses` (a state map) and `sentInProgressRef` (a Set that prevents duplicate PATCHes). The `unannotated → in-progress` transition is triggered on the first confirmed span and guarded so it fires at most once per task per session.

There are currently three paths that create a confirmed span:
1. **Token click** (`handleTokenClick`) — has the in-progress guard
2. **Drag selection** (mouseup handler) — has the in-progress guard
3. **Promote suggestion** (`handlePromote`) — **missing the guard**

Because `handlePromote` skips the transition, a task can accumulate confirmed spans (enabling the "Mark Complete" button via `confirmedCount > 0`) while the DB task status remains `unannotated`. The backend correctly rejects `PATCH { status: "completed" }` from `unannotated` with 422 `INVALID_TRANSITION`.

## Goals / Non-Goals

**Goals:**
- `handlePromote` triggers `unannotated → in-progress` on the first successful span promotion, identical to the existing token-click and drag paths.
- The guard logic (ref + state check) is consistent across all three span-creation paths.

**Non-Goals:**
- No backend changes.
- No refactoring of the guard into a shared utility (three call sites is manageable; premature abstraction adds scope).
- No changes to drag or token-click paths (they are correct as-is).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-005-opencode-agent-boundaries | Agent edits are scoped to the repo; no infrastructure or DB changes without explicit approval | This fix is frontend-only, no infra or DB involvement — compliant |

All other ADRs (001–004, 006–008) cover tenant isolation, model strategy, serving topology, OpenSpec governance, training infrastructure, chatbot architecture, and base model defaults — none constrain a single-file frontend bug fix.

## Decisions

### Decision 1: Fix in `handlePromote`, not in `handleMarkComplete`

**Choice:** Add the `unannotated → in-progress` guard to `handlePromote`, immediately after a successful span promotion API call.

**Rationale:** The in-progress transition semantically belongs at "first confirmed span created", not at "Mark Complete clicked". If the transition were moved to `handleMarkComplete`, the DB task would jump directly from `unannotated → completed`, skipping `in-progress` entirely. This would silently bypass any future business logic or observability hooks that depend on a task entering `in-progress` (webhooks, audit logs, reporting).

**Alternatives considered:**
- **Fix in `handleMarkComplete` (two-step: in-progress then completed)** — Would mask the gap and produce incorrect lifecycle data; `in-progress` entry time would be identical to `completed` time.
- **Loosen backend to allow `unannotated → completed`** — Destroys the state machine invariant and could produce tasks that are never recorded as in-progress.
- **Extract `ensureInProgress()` shared utility** — Cleaner long-term, but adds scope for a three-line bug fix; deferred until there's a fourth call site.

### Decision 2: Reuse the existing `sentInProgressRef` + `taskStatuses` guard pattern unchanged

**Choice:** The guard added to `handlePromote` uses the same pattern as the existing handlers: check `(currentStatus === "unannotated" && !sentInProgressRef.current.has(task.id))`, add to ref before the request, update `taskStatuses` on success.

**Rationale:** The pattern already handles idempotency (no double-PATCHes), session reset on page reload, and partial failure (if the PATCH fails, `taskStatuses` doesn't get updated, but the ref is set — this is acceptable because the backend will still reject `completed` from `unannotated`, surfacing the error to the user via the existing `"Failed to complete task"` toast).

**Alternatives considered:**
- **Remove ref from `handlePromote`, rely only on `taskStatuses`** — Creates a race condition: if `handleMarkComplete` fires quickly before `taskStatuses` updates, two in-progress PATCHes could be sent.

## Risks / Trade-offs

- [Ref set before request means failed in-progress PATCH silences the promote-path transition permanently for that session] → Acceptable — the existing handlers have the same behavior; the user's session will retry on next load; the in-progress transition failure is non-blocking to span creation.
- [Three duplicated copies of the guard logic] → Low risk now; if a fourth path is added, extract to a utility then.

## Migration Plan

1. Edit `handlePromote` in `AnnotationPage.tsx`: add `taskStatuses` to the dependency array and add the guard block after a successful promote.
2. No DB migration, no API change, no environment config change.
3. Rollback: revert the single edit. The bug pre-existed; reverting restores original behavior.

## Open Questions

_(none)_
