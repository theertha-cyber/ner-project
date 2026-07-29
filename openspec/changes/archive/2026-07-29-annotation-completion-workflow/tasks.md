## 1. Backend — terminal completed state

- [x] 1.1 In `src/annotation_service/api/v1/tasks.py`, add `"completed": ["completed"]` to `valid_transitions`, keeping `unannotated: ["in-progress"]` and `in-progress: ["completed"]` unchanged.
- [x] 1.2 Confirm the `NO_SPANS` span-count guard still runs for every request whose `new_status == "completed"`, including the idempotent re-completion path.
- [x] 1.3 Add pytest cases in `tests/test_annotation_workspace.py`: completed → completed returns 200 with status unchanged (scenario 19), and completed → in-progress returns 422 with code `INVALID_TRANSITION` (scenario 20).
- [x] 1.4 Re-run the existing task-status pytest cases (scenarios 13–18) and confirm none regressed.

## 2. Portal — strip the status switcher from the toolbar

- [x] 2.1 In `AnnotationToolbar.tsx`, delete the status button group markup (`data-testid="status-group"` and its buttons), the `statuses` array, `handleStatusClick`, `optimisticStatus` state, and the `authFetch`/`useToast` imports if they become unused.
- [x] 2.2 Remove `onStatusChange` from `AnnotationToolbarProps`; keep `currentStatus` and render the read-only badge from it via `STATUS_LABELS`.
- [x] 2.3 In `AnnotationPage.tsx`, drop the `onStatusChange={handleStatusChange}` prop from `<AnnotationToolbar>`.
- [x] 2.4 Update `AnnotationToolbar.test.tsx`: replace status-group tests with assertions for scenarios 1, 2, and 3 (elements present, `status-group` absent, no PATCH issued, completed badge with no transition control). No skipped tests.

## 3. Portal — promote to in-progress on task open

- [x] 3.1 In `AnnotationPage.tsx`, add the `unannotated` → `in-progress` PATCH to the task-selection path, guarded by `sentInProgressRef`, updating `taskStatuses` on success.
- [x] 3.2 Remove the three inline promotion blocks from `handleTokenClick`, the drag mouseup handler, and `handlePromote`; drop the now-unused `taskStatuses` entries from those callbacks' dependency arrays.
- [x] 3.3 Verify by grep that `"in-progress"` appears at exactly one PATCH site in `AnnotationPage.tsx`.
- [x] 3.4 Add `AnnotationPage.test.tsx` cases for scenarios 4, 5, 6, and 7 (promotion on open, once per session, no PATCH for a completed task, no status PATCH on span creation).

## 4. Portal — bottom action bar with Mark as Completed

- [x] 4.1 Create `src/portal/src/components/annotation/AnnotationActionBar.tsx` — presentational component with props `task`, `saveState`, `isCompleting`, `onMarkCompleted`; renders save indicator left, primary "Mark as Completed" button right; button disabled when `!task` or `isCompleting`.
- [x] 4.2 Mount it in `AnnotationPage.tsx` at `gridColumn: "1 / -1", gridRow: 4` with a top border matching the toolbar.
- [x] 4.3 Add a `pendingWrites` counter in `AnnotationPage.tsx`, incremented/decremented around span create, delete, and promote requests; derive `saveState` ("Saving…" vs "All changes saved") from it.
- [x] 4.4 Implement `handleMarkCompleted` in `AnnotationPage.tsx`: await in-flight span writes settling, set `isCompleting`, PATCH `{status: "completed"}`, on 200 update `taskStatuses` + invalidate the `annotation-tasks` query + success toast, on error toast the response message and leave status unchanged; always clear `isCompleting`.
- [x] 4.5 Create `AnnotationActionBar.test.tsx` covering scenarios 8 and 12 (bar renders with indicator and button; button disabled and inert with no task).
- [x] 4.6 Add `AnnotationPage.test.tsx` cases for scenarios 9, 10, and 11 (successful completion, 422 no-spans path leaves status and re-enables the button, idempotent re-completion of a completed task).

## 5. Cleanup and cross-checks

- [x] 5.1 Confirm no task-status guard was added to the span endpoints (completed tasks stay editable — explicit non-goal).
- [x] 5.2 Run the portal test suite and the annotation pytest module; both clean.
- [x] 5.3 Fill in the Verification Artifact column in `verification.md` § Spec Alignment with the test name/file that satisfies each of rows 1–20.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 6.6 Run `openspec validate annotation-completion-workflow --type change --strict` and confirm it exits clean before archive.
