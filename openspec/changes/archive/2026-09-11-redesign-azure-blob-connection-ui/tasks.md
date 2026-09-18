## 1. Shared focus-trap extraction

- [x] 1.1 Extract `useFocusTrap` (focus trap, Escape-to-close, return-focus-to-trigger, portal helpers) out of `src/portal/src/components/ui/slide-over.tsx` into a shared hook, with `SlideOver` refactored to consume it and its public API/behavior unchanged.
- [x] 1.2 Run `slide-over.test.tsx` unmodified and confirm it still passes with no test edits.

## 2. Lifecycle panel: merge test + attestation + activation into one sequential control

- [x] 2.1 In `src/portal/src/components/data-sources/lifecycle.tsx`, replace the separate "Secure test" and "Activation evidence" panels in `LifecyclePanel` with one panel containing a single sequential control (`untested/failed → "Test connection"/"Retry test", no checkboxes`, `testing → disabled "Testing…", no checkboxes`, `passed & not active → passed result + both attestation checkboxes + "Activate" (disabled until both checked)`, `active → disabled "Activated", both checkboxes shown checked+disabled`).
- [x] 2.2 Keep the `evidence`/checkbox state and the `network_approved`/`governance_approved` checkbox inputs — do not remove them. Rename/reposition them into the merged control (no longer a standalone `<fieldset>` panel), with each checkbox individually labeled with what it confirms. Keep the `activate` action's submitted body as `activation_evidence: [...REQUIRED_ACTIVATION_EVIDENCE].sort()`, sent only once "Activate" is enabled (both checkboxes checked).
- [x] 2.3 Ensure "Activate" is disabled whenever `connection.last_test.outcome !== "passed"` OR either checkbox is unchecked, matching the existing `Activation is blocked safely` behavior (safe blocking notice, no secret/provider detail) for the test-not-passed case.
- [x] 2.4 Ensure a test failure (including a retest of a previously passed connection) resets both checkboxes to unchecked and hides them, returning the control to the retry state.
- [x] 2.5 Update `lifecycle.tsx`'s existing unit tests (or the co-located test file covering `LifecyclePanel`) to assert: the untested state shows no checkboxes/no Activate; the passed state shows both checkboxes unchecked and Activate disabled; Activate enables only once both are checked; the submitted `activation_evidence` body; and a failed retest clears/hides the checkboxes.

## 3. Detail page: reorder panels, drop redundant Activation fact

- [x] 3.1 In `src/portal/src/app/(auth)/settings/data-sources/[connectionId]/page.tsx`, reorder `DetailContent`'s render so `SyncActivitySummary` renders before `LifecyclePanel` (final order: connection details/config → Sync activity → Lifecycle) for both Azure Blob and Azure PostgreSQL connections.
- [x] 3.2 Remove the `Activation` row from `SafeFacts` (`connection.activation.outcome · reason_code`) since that state now surfaces inline in the merged Lifecycle control; keep `Configured fields`, `Secret references`, `Test`, `Updated`, and the replace/replaced-by rows unchanged.
- [x] 3.3 Update `[connectionId]/page.test.tsx` to assert the new DOM order and the removed `Activation` fact row, for both providers.

## 4. New-connection modal

- [x] 4.1 Build `CreateConnectionModal` (or similarly named component) using `useFocusTrap` and reusing `ProviderConfigForm` unchanged in its body, rendered as a centered dialog per the approved mockup.
- [x] 4.2 In `src/portal/src/app/(auth)/settings/data-sources/page.tsx`, replace the inline `creating`-driven `<section aria-label="Create connection">` panel with the modal; keep the "New connection" button as the modal's trigger and confirm it returns focus to that button on close.
- [x] 4.3 Ensure modal cancel / `Escape` discards in-progress form values (fresh `ProviderConfigForm` state on next open) and sends no request; ensure successful create still navigates to the new connection's detail route with a fresh `Idempotency-Key`.
- [x] 4.4 Update `data-sources/page.test.tsx` to drive the modal open/submit/cancel paths instead of the inline panel.

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. (Scenarios 1–3, 6–11 map to existing/updated `lifecycle.tsx` and `[connectionId]/page.test.tsx` test files per task 2.4/3.3; scenarios 4–5 map to `data-sources/page.test.tsx` per task 4.4; scenario 12 maps to `[connectionId]/page.test.tsx` per task 3.3.)
- [x] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 5.6 Run `openspec validate redesign-azure-blob-connection-ui --type change --strict` and confirm it exits clean before archive.
