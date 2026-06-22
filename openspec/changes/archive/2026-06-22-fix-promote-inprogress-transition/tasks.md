## 1. Frontend Fix — `handlePromote` In-Progress Transition

- [x] 1.1 In `src/portal/src/components/annotation/AnnotationPage.tsx`, add the `unannotated → in-progress` guard to `handlePromote`: after the successful `dispatch({ type: "SUGGESTION_PROMOTE" })` call, add the same guard block used in `handleTokenClick` — check `(currentStatus === "unannotated" && !sentInProgressRef.current.has(selectedTask.id))`, add to ref before the fetch, call `authFetch` with `{ status: "in-progress" }`, and update `taskStatuses` on `patchRes.ok` (covers scenarios 2, 3)
- [x] 1.2 Add `taskStatuses` to the `useCallback` dependency array of `handlePromote` so the guard reads the current status without stale closure (covers hallucination risk 1)
- [x] 1.3 Verify the guard block is placed after `dispatch({ type: "SUGGESTION_PROMOTE", ... })` (i.e., after the successful promote is confirmed), not inside the error branch or before the dispatch (covers hallucination risk 3)
- [x] 1.4 Verify `sentInProgressRef.current.add(selectedTask.id)` is called before the `await authFetch(...)` for the in-progress PATCH, matching the ordering in `handleTokenClick` (covers hallucination risk 2)

## 2. Verification — Spec Scenarios

- [ ] 2.1 Manual browser test (Scenario 2): With a task in `unannotated` status, run Pre-label then promote one suggestion — confirm network tab shows `PATCH /annotation-tasks/{id}` `{status: "in-progress"}` returning 200 and the queue badge updates (covers verification.md row 2)
- [ ] 2.2 Manual browser test (Scenario 6): After the promote-only flow above, click "Mark Complete" — confirm `PATCH /annotation-tasks/{id}` `{status: "completed"}` returns 200 with no error toast (covers verification.md row 6)
- [ ] 2.3 Manual browser test (Scenario 3): Promote a second suggestion on the same task — confirm only one in-progress PATCH appears in the network tab (covers verification.md row 3)
- [ ] 2.4 Manual browser test (Scenario 1): On a fresh `unannotated` task, create a span via token click — confirm the in-progress PATCH still fires via the token-click path (covers verification.md row 1)
- [ ] 2.5 Manual browser test (Scenarios 4 & 5): Confirm "Mark Complete" is visibly disabled with zero spans and becomes enabled/highlighted after at least one span exists (covers verification.md rows 4, 5)

## 3. Verification & Evidence

- [ ] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 3.6 Run `openspec validate fix-promote-inprogress-transition --type change --strict` and confirm it exits clean before archive.
