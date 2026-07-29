## Why

The annotation toolbar exposes a three-way status switcher (`pending` / `in_progress` / `completed`) that lets annotators attempt transitions the backend rejects — clicking `in_progress` on a finished task produces `Cannot transition from 'completed' to 'in-progress'`. Status is workflow bookkeeping, not a control the annotator should operate; the conventional pattern is to work on a task and explicitly complete it.

## What Changes

- **BREAKING (UI)**: Remove the status button group from the annotation toolbar. Status is displayed as a read-only badge only.
- Opening a task puts it in `in-progress` immediately (single `PATCH` on task selection) instead of lazily on first span edit. Tasks already `completed` stay `completed`.
- Add a persistent **Mark as Completed** action in a new bottom action bar of the annotation workspace, alongside the save/status affordance.
- Clicking **Mark as Completed** flushes pending span writes and `PATCH`es the task to `completed`; on success the badge shows `completed` and the task queue entry updates.
- `completed` is terminal. No UI path transitions a task back to `in-progress`, and the backend continues to reject that transition.
- Revisiting a completed task loads it read-write (span editing already permitted); the annotator may edit and press **Mark as Completed** again. Re-completing a `completed` task is idempotent and SHALL NOT error.
- Backend: allow `completed` → `completed` as an idempotent no-op (200). All other transitions out of `completed` stay rejected with `INVALID_TRANSITION`.
- The existing `NO_SPANS` guard still applies: completing with zero confirmed spans fails with a toast and the task stays `in-progress`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `portal-annotation`: Toolbar requirement loses the status button group; new requirement for the bottom action bar and the **Mark as Completed** action; auto-promotion requirement changes from "on first span edit" to "on task open"; the existing "There SHALL NOT be a separate Mark Complete button" statement is inverted.
- `annotation-workspace`: `PATCH /api/v1/annotation-tasks/{id}` transition table gains the idempotent `completed` → `completed` case.

## Impact

- `src/portal/src/components/annotation/AnnotationToolbar.tsx` — remove status group, `handleStatusClick`, `onStatusChange` prop; keep badge.
- `src/portal/src/components/annotation/AnnotationPage.tsx` — promote on task select; add bottom action bar with **Mark as Completed**; `handleStatusChange` replaced by a `handleMarkCompleted` callback.
- New component `src/portal/src/components/annotation/AnnotationActionBar.tsx`.
- `src/annotation_service/api/v1/tasks.py` — `valid_transitions` gains `"completed": ["completed"]`, with the `NO_SPANS` guard preserved.
- Tests: `AnnotationToolbar.test.tsx`, `AnnotationPage.test.tsx`, `TaskQueue.test.tsx`, `tests/test_annotation_workspace.py`.
- Grid layout of the workspace already reserves a fourth row (`auto`) — the action bar occupies it.

## Open Questions

- Assumption: annotators may keep editing spans on a `completed` task (current span endpoints have no status guard). If completion should freeze edits, that is a separate change.
- Assumption: the action bar renders for every role that can open a task; no role gating beyond existing task visibility filters.
