## Why

When an annotator completes a manual annotation task, the backend already writes a persistent
notification addressed to `tenant_admin` ("Annotation task completed... eligible for model
training") — the annotator's completion is final, with no second Tenant Admin review. The
frontend bell's click-through for that exact notification (`resource_type: "annotation_task"`)
sent the Tenant Admin to `/annotate/automated/retrain` — the Automated flow's retrain page,
unrelated to the manual annotation that was just completed. This looks like a copy-paste
artifact from the `prelabel_batch` branch directly above it. Found and confirmed while
answering a direct question about whether this notify-then-train path already existed.

## What Changes

- Fix the notification bell's navigation target for `resource_type: "annotation_task"`:
  `/training-jobs?source=manual` instead of `/annotate/automated/retrain` — the same
  destination the Manual landing page's own "Train model" button already uses, so clicking
  either one lands the Tenant Admin in the same place with the same source locked.

## Capabilities

### Modified Capabilities

- `notifications`: "Notification Bell" gains scenarios pinning down each notification kind's
  click-through destination, correcting the manual-annotation-task case.

## Impact

- Frontend: [components/app-shell/NotificationBell.tsx](src/portal/src/components/app-shell/NotificationBell.tsx)
  (one-line routing fix in `hrefFor`).
- Tests: new [NotificationBell.test.tsx](src/portal/src/components/app-shell/NotificationBell.test.tsx)
  covering all three existing `resource_type` branches (`annotation_task`, `prelabel_batch` for
  both roles, `import_file` is unchanged and not separately asserted here since it was already
  correct).
- No backend changes — the notification itself was already correct; only the frontend's
  navigation target for it was wrong.
