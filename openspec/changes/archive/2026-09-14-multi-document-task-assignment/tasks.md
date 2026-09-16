## 1. Component rewrite

- [x] 1.1 Replace the single `<select>` document dropdown with a checkbox list
  (`document-checkbox-list`, one `document-checkbox-{id}` per document), backed by a
  `Set<string>` of selected ids.
- [x] 1.2 Add "Select all" and "Clear" controls above the list; show the selected count in the
  section label.
- [x] 1.3 Rewrite the submit handler to loop sequentially over selected document ids, POSTing
  each to the existing `/api/v1/annotation-tasks` endpoint with the same annotator, collecting
  a per-document outcome (`success` | `conflict` | `error`).
- [x] 1.4 Full-success path: close immediately (unchanged from the prior single-document
  behavior), toast naming the count, call `onAssign` with every created task.
- [x] 1.5 Partial/full-failure path: keep the form open, render `assign-results` with one
  `assign-result-{id}` line per document; replace the Assign/Cancel actions with a "Done"
  button that calls `onAssign` with whichever tasks succeeded.
- [x] 1.6 Change `AssignTaskFormProps.onAssign` to `(tasks: AnnotationTask[]) => void`; update
  `AnnotationPage.tsx`'s `handleTaskAssigned` to prepend the array.

## 2. Tests

- [x] 2.1 Rewrite `AssignTaskForm.test.tsx` for the checkbox-list UI: document list scenario,
  annotator dropdown scenario (unchanged), Assign-button-disabled scenarios (single and
  multiple checked), Select all / Clear, single- and multi-document success, single- and
  mixed-outcome failure (including the "Done" button path), Cancel, empty-annotators.
- [x] 2.2 Confirm `AnnotationPage.test.tsx` is unaffected (it mocks `AssignTaskForm` and never
  calls `onAssign` directly).

## 3. Verification & Evidence

- [x] 3.1 Run `AssignTaskForm.test.tsx` and `AnnotationPage.test.tsx` against the portal test
  container; confirm all pass except the 3 already-known pre-existing `AnnotationPage.test.tsx`
  layout-scenario failures (unrelated — Scenario 1/2/3 default-layout/Focus-mode tests).
- [x] 3.2 Run the full portal suite; confirm the failing-file set matches the known pre-existing
  baseline with one fewer failure (the stale `toast(..., "good")` assertion this change's
  rewrite corrected as a side effect).
- [x] 3.3 Rebuild and restart the `portal` container.
- [x] 3.4 Live-verify in the browser: opened Assign Task on the annotation workspace, clicked
  "Select all (3)", chose an annotator, clicked "Assign 3 documents" — all 3 tasks were created
  in one action, toast read "3 tasks assigned successfully", and the form closed automatically.
