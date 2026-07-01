## 1. Data Fetching Hooks

- [x] 1.1 Create a `useDocuments` hook (or inline React Query in the component) that fetches `GET /api/v1/documents` using `authFetch`, enabled only when the assignment form is open. Return the filtered list of documents with `status === "processed"`.
- [x] 1.2 Create a `useAnnotatorUsers` hook (or inline React Query in the component) that fetches `GET /api/v1/users` using `authFetch`, enabled only when the assignment form is open. Return the filtered list of users with `role === "annotator"`.

## 2. AssignTaskForm Component

- [x] 2.1 Create `src/portal/src/components/annotation/AssignTaskForm.tsx` — an inline form component with a Document `<select>` dropdown and an Annotator `<select>` dropdown, an "Assign" submit button, and a "Cancel" link. Props: `onAssign(documentId, annotatorUserId)`, `onCancel()`, loading and error states.
- [x] 2.2 Populate the Document dropdown from the filtered documents list (status === "processed"). Show a loading indicator while fetching. If empty, show a placeholder "No processed documents" option and disable the Assign button.
- [x] 2.3 Populate the Annotator dropdown from the filtered users list (role === "annotator"). Show a loading indicator while fetching. If empty, show the message "No annotators available — invite users first" within the dropdown and disable the Assign button.
- [x] 2.4 Disable the "Assign" submit button until both a document and an annotator have been selected.
- [x] 2.5 On submit, call `POST /api/v1/annotation-tasks` with `{ document_id, annotator_user_id }`. Show a loading state on the button during the in-flight request.
- [x] 2.6 On 201 success: invoke `onAssign` with the response task object; show a success toast.
- [x] 2.7 On 409 response: keep the form open and render an inline error message below the dropdowns ("This document already has an active task"). Do not close the form or update the task list.
- [x] 2.8 On other errors (5xx, network): show a generic inline error message; keep the form open.

## 3. Task Queue Panel Integration

- [x] 3.1 In `AnnotationPage.tsx`, add an `isAssignFormOpen` boolean state (default false). Gate the state and the "＋ Assign Task" button on `user.role === "tenant_admin"`.
- [x] 3.2 In the Task Queue panel header area (inside the `data-testid="task-queue-column"` div), render the "＋ Assign Task" button above the task list only when `user.role === "tenant_admin"`. Clicking the button sets `isAssignFormOpen = true`.
- [x] 3.3 When `isAssignFormOpen` is true, render `<AssignTaskForm>` below the "＋ Assign Task" button and above the task list.
- [x] 3.4 On successful task creation (`onAssign` callback): prepend the new task to the local tasks list state (or invalidate the `annotation-tasks` React Query cache so it refetches), set `isAssignFormOpen = false`.
- [x] 3.5 On cancel (`onCancel` callback): set `isAssignFormOpen = false` without modifying the task list.

## 4. AnnotationTask Type Update

- [x] 4.1 Verify the `AnnotationTask` interface in `TaskQueue.tsx` includes all fields returned by `POST /api/v1/annotation-tasks` (id, document_id, annotator_user_id, status, created_at, updated_at, filename, document_status, span_count). Add any missing optional fields so the optimistic task renders correctly in the queue.

## 5. Component Tests — task-assignment-ui Scenarios

- [x] 5.1 Write a test for Scenario 1: renders "＋ Assign Task" button when `user.role === "tenant_admin"` (verification.md row 1)
- [x] 5.2 Write a test for Scenario 2: "＋ Assign Task" button is absent from DOM when `user.role === "annotator"` (verification.md row 2)
- [x] 5.3 Write a test for Scenario 3: clicking button expands the inline form (verification.md row 3)
- [x] 5.4 Write a test for Scenario 4: Document dropdown shows only `processed` documents; `pending`/`failed` excluded (verification.md row 4)
- [x] 5.5 Write a test for Scenario 5: Annotator dropdown shows only `annotator`-role users (verification.md row 5)
- [x] 5.6 Write a test for Scenario 6: Assign button disabled when one or both fields unselected (verification.md row 6)
- [x] 5.7 Write a test for Scenario 7: 201 response prepends task to queue, collapses form, fires success toast (verification.md row 7)
- [x] 5.8 Write a test for Scenario 8: 409 response keeps form open, shows inline error, queue unchanged (verification.md row 8)
- [x] 5.9 Write a test for Scenario 9: Cancel collapses form, no POST sent (verification.md row 9)
- [x] 5.10 Write a test for Scenario 10: empty annotator list shows "No annotators available" message and disables Assign button (verification.md row 10)

## 6. Component Tests — portal-annotation Delta Scenarios

- [x] 6.1 Confirm existing TaskQueue tests cover Scenarios 11–15 (rows 11–15 in verification.md); if any test is missing, add it.
- [x] 6.2 Write a test for Scenario 16: tenant_admin sees "＋ Assign Task" button in Task Queue panel (verification.md row 16)
- [x] 6.3 Write a test for Scenario 17: annotator does not see "＋ Assign Task" button (verification.md row 17)

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 7.6 Run `openspec validate assign-annotation-tasks --type change --strict` and confirm it exits clean before archive.
