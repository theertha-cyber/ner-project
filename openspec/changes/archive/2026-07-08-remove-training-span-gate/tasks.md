## 1. Remove the client-side threshold

- [x] 1.1 In `src/portal/src/components/training-jobs/submit-job-slideover.tsx`, delete the `meetsThreshold` computation and update `canSubmit` to depend only on `Object.keys(errors).length === 0` (and submit-in-flight state, as today).
- [x] 1.2 Update the preflight banner JSX (currently branching on `meetsThreshold` for both container `className` and copy) so it always renders a neutral style, and shows: loading state while `spanLoading`, `"${spanCount} confirmed spans"` when the count is known, and an "unavailable" message when `spanCount` is `null` post-fetch — with no pass/fail wording or threshold number.
- [x] 1.3 Confirm no other reference to `meetsThreshold` or a hardcoded `500` remains in the component file.

## 2. Update component tests

- [x] 2.1 In `src/portal/src/components/training-jobs/submit-job-slideover.test.tsx`, replace the "shows warning for insufficient spans" test (currently asserts `/requires 500 minimum/`) with a test asserting the Submit button is enabled and the banner shows the plain span count when the mocked span count is below 500.
- [x] 2.2 Replace the "shows field-level validation for negative epochs" test (currently mislabeled — it actually asserts `/meets the 500-span minimum/`) with a test asserting the banner shows the plain span count with no threshold language when the count is high.
- [x] 2.3 Add a test asserting the Submit button's enabled state is unaffected when the span-count fetch fails (mock `fetch` to reject/return non-OK for `/api/v1/annotation-export`), covering the "unavailable" preflight state.
- [x] 2.4 Add a test asserting that when `POST /api/v1/training-jobs` responds 422 with an insufficient-entities message, the form surfaces that message via the existing `serverError` display and the form remains open with entered hyperparameters intact.
- [x] 2.5 Review the existing "calls onClose after successful submission" test — confirm it still passes without relying on the 600-line span mock being load-bearing for enabling Submit (it may now use a smaller mocked span list).

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [x] 3.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [x] 3.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [x] 3.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [x] 3.6 Run `openspec validate remove-training-span-gate --type change --strict` and confirm
         it exits clean before archive.