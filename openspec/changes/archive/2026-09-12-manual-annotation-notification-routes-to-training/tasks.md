## 1. Fix

- [x] 1.1 `NotificationBell.tsx`'s `hrefFor`: route `resource_type === "annotation_task"` to
  `/training-jobs?source=manual` instead of `/annotate/automated/retrain`.

## 2. Tests

- [x] 2.1 New `NotificationBell.test.tsx`: the manual-annotation-task notification routes to
  `/training-jobs?source=manual` and marks itself read; the automated-batch notification still
  routes a `tenant_admin` to `/annotate/automated/retrain` and an `annotator` to
  `/annotate/review-batch/{id}` (regression coverage for the branch that was already correct).

## 3. Verification & Evidence

- [x] 3.1 Run the new test file against the portal test container; confirm all pass.
- [x] 3.2 Run the full portal suite; confirm the failing-file set is exactly the known
  pre-existing 6-file baseline, with no new regressions.
- [x] 3.3 Rebuild and restart the `portal` container.
- [ ] 3.4 Live-verify by clicking an actual completed-manual-annotation-task notification in the
  browser — not done this session: no such notification exists in the current seed data (the
  bell shows "Nothing new" for the logged-in tenant admin), and generating one requires
  completing a real manual annotation task through the full workflow. Covered instead by the
  unit test in 2.1, which asserts the exact routing logic directly.
