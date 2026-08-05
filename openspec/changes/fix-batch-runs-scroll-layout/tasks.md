## 1. Layout Change

- [x] 1.1 In `src/portal/src/components/extractions/BatchRunsTab.tsx`, wrap the two-column grid in a layout that lets the left column (run list) bound its own height and scroll independently — e.g., make the grid row a flex/height-constrained container (`min-height: 0` on the grid, `flex: 1` + `min-height: 0` on the left column) and add `overflow-y: auto` to the left column's run-card list div.
- [x] 1.2 Ensure the right-hand detail panel and the page header/tab pills (`ExtractionPage.tsx`) are untouched — no changes to `ExtractionPage.tsx` or `AppShell.tsx`.
- [x] 1.3 Verify no regression to `BatchDocumentSelectModal.tsx` — no edits needed there; confirm visually it still centers via `fixed inset-0 flex items-center justify-center` with its own `overflow-y-auto` document list.

## 2. Existing Behavior Regression Checks

- [x] 2.1 Run `BatchRunsTab.test.tsx` and confirm all existing tests still pass unmodified (covers scenarios: lists runs, persists across reload, selecting shows detail, triggering new run, polling, status pill colors).

## 3. Verification & Evidence

- [ ] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. Scenarios 1–6: `BatchRunsTab.test.tsx` output. Scenarios 7–8: manual browser screenshots/recording (long run list scroll isolation; dialog centering/scroll).
- [ ] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (N/A — no constraining ADRs).
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 3.6 Run `openspec validate fix-batch-runs-scroll-layout --type change --strict` and confirm it exits clean before archive.
