## 1. Event Coordination

- [x] 1.1 Update `AnnotationPage.tsx` so a same-token click is owned by the token click path and is not submitted again by document mouseup.
- [x] 1.2 Ensure multi-token mouseup remains the sole range-save path, preserving inclusive min/max offsets and optimistic/error handling.

## 2. Regression Tests

- [x] 2.1 Extend `AnnotationPage.test.tsx` with a browser-event-level single-token click plus mouseup test asserting exactly one POST and one confirmation.
- [x] 2.2 Add a browser-event-level drag test asserting exactly one inclusive range POST, including the existing reverse-direction behavior.
- [x] 2.3 Run the focused portal annotation tests and retain the existing error and guard coverage.

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 3.2 Collect functional evidence (test output) for each scenario and record one entry per row in verification.md § Evidence Log.
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 3.5 Complete Audit Record sign-off in verification.md § Audit Record.
- [x] 3.6 Run `openspec validate cap-5-single-request-manual-annotation-gestures --strict` before archive.
