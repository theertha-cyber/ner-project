## Why

The "Assign Task" form let a tenant admin pick exactly one document per submission. Assigning
an annotator a day's worth of documents meant reopening the form and repeating the same
annotator selection once per document — a single-select dropdown offering no way to pick
several at once, direct user feedback confirmed this needed to change.

## What Changes

- Replace the Document dropdown with a checkbox list supporting multiple selections, plus
  "Select all" / "Clear" convenience controls.
- On submit, create one task per selected document for the chosen annotator — sequential
  `POST /api/v1/annotation-tasks` calls against the existing single-document endpoint (no new
  bulk endpoint; each document is still independently subject to the same "one active task per
  document" conflict rule).
- When every document in the batch succeeds, the form closes immediately and every created task
  is prepended to the Task Queue — matching the prior single-document flow's behavior exactly
  when the batch happens to be of size 1.
- When any document in the batch fails (already has an active task, or another error), the form
  stays open and shows a per-document result line (✓ assigned / ✕ reason) instead of closing
  over an error the admin hasn't seen; a "Done" button replaces "Assign"/"Cancel" and closes the
  form with whichever tasks did succeed.
- `AssignTaskForm`'s `onAssign` prop changes from `(task: AnnotationTask) => void` to
  `(tasks: AnnotationTask[]) => void`; its one caller (`AnnotationPage`) is updated to prepend
  the whole array instead of one task.

## Capabilities

### Modified Capabilities

- `task-assignment-ui`: "Task Assignment Form" now describes a multi-select document list, a
  batch submission that creates one task per selected document, and per-document result
  reporting for a batch that partially fails.

## Impact

- Frontend: [components/annotation/AssignTaskForm.tsx](src/portal/src/components/annotation/AssignTaskForm.tsx)
  (rewritten document selection and submit flow),
  [components/annotation/AnnotationPage.tsx](src/portal/src/components/annotation/AnnotationPage.tsx)
  (`handleTaskAssigned` now takes an array).
- Tests: rewrote [AssignTaskForm.test.tsx](src/portal/src/components/annotation/AssignTaskForm.test.tsx)
  for the multi-select UI and batch submission (15 tests, up from 9); confirmed
  [AnnotationPage.test.tsx](src/portal/src/components/annotation/AnnotationPage.test.tsx)
  unaffected (it mocks `AssignTaskForm` entirely and never exercises `onAssign`).
- No backend changes — reuses the existing single-document `POST /api/v1/annotation-tasks`
  endpoint and its existing conflict semantics, called once per selected document.
- While rewriting this test file, corrected a pre-existing assertion bug unrelated to this
  change: the old "Successful task creation" test expected `toast(..., "good")`, but
  `ToastKind` only ever accepts `"ok" | "bad"` — the component has always called `toast(...,
  "ok")`. This was one of the 6 pre-existing baseline test failures tracked throughout this
  session; fixing it here (since the whole file needed rewriting anyway) removes it from that
  baseline going forward.
