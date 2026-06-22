## Why

When an annotator uses the "Pre-label" button and promotes a suggested span to confirmed, the annotation task never transitions from `unannotated` to `in-progress` — leaving the DB status stuck. When the annotator then clicks "Mark Complete", the backend rejects with 422 (`INVALID_TRANSITION`) because the only valid next step from `unannotated` is `in-progress`, not `completed`. The bug exists because the `unannotated → in-progress` PATCH is only triggered by direct token-click and drag span creation, but not by the promote-suggestion path.

## What Changes

- In `AnnotationPage.tsx`, `handlePromote`: after a successful span promotion, check if the current task status is `unannotated` and send the `PATCH /annotation-tasks/{id}` with `{ status: "in-progress" }` (same guard as token-click and drag handlers).
- Add `taskStatuses` to the `useCallback` dependency array of `handlePromote`.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `portal-annotation`: The Task Status Lifecycle requirement must explicitly cover the promote-suggestion path as a trigger for the `unannotated → in-progress` transition, not just direct token-click span creation.

## Impact

- **File**: `src/portal/src/components/annotation/AnnotationPage.tsx` — `handlePromote` callback only.
- **API**: No change. `PATCH /api/v1/annotation-tasks/{id}` already supports `in-progress`; no backend changes needed.
- **Spec**: `openspec/specs/portal-annotation/spec.md` — Task Status Lifecycle requirement and its first-span scenario need updating to include promote as a trigger.

## Open Questions

_(none — root cause is confirmed, fix is self-contained)_
