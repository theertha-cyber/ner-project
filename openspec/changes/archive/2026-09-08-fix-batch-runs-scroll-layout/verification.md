# Verification Plan

**Change:** fix-batch-runs-scroll-layout
**Generated:** 2026-08-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Batch Runs tab lists existing runs | Given the user opens or reloads the Batch Runs tab, when it mounts, then `GET /api/v1/extract-batch` is called and each returned run renders as a card with ID, status, progress bar, and footer metadata | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 2 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Run history persists across page reload | Given a batch run previously completed, when the tab mounts after reload, then the run appears in the list and the empty state is not shown | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 3 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Selecting a batch run shows detail | Given multiple run cards, when the user clicks one, then it gets a primary border and the right panel shows its stats | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 4 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Triggering a new batch run | Given the tab is active, when the user clicks "New batch run", then `POST /api/v1/extract-batch` is sent and the new run appears selected at the top of the list with status "queued" | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 5 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | In-progress runs poll for status updates | Given runs with status "running"/"queued", when the tab is mounted, then each polls `GET /api/v1/extract-batch/{run_id}` every 3s until terminal state | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 6 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Status pills use correct visual styles | Given runs with various statuses, when the list renders, then completed/running-queued/failed use good/warn/bad color tokens respectively | `BatchRunsTab.test.tsx` (existing suite) | - [ ] |
| 7 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Long run list scrolls independently of the page | Given more runs than fit the column height, when the user scrolls the run list, then only the run list's internal content moves and the header, tab pills, and detail panel stay in place | Manual browser QA: screenshot/recording with a long run list | - [ ] |
| 8 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Document selection dialog remains centered and independently scrollable | Given the "New batch run" dialog is open with more documents than fit its panel, when it renders, then the dialog stays centered and only its document checklist scrolls | Manual browser QA: screenshot/recording with a long eligible-document list | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Run list scroll boundary | AI may hardcode a `calc(100vh - Npx)` offset that misaligns with actual header/tab-pill height, causing the list to clip content or leave dead space | Resize browser window and visually confirm the run list fills available height with no clipped cards and no excess empty space below the last card |
| 2 | Page-level scroll elimination | AI may accidentally set `overflow: hidden` on `AppShell`'s `<main>` or `ExtractionPage`, breaking scroll behavior for the Playground or Entity Review tabs | Manually switch to Playground and Entity Review tabs after the change and confirm their scroll behavior is unchanged from before |
| 3 | Detail panel independence | AI may couple the right detail panel's height to the run list's bounded height, unintentionally clipping or scroll-locking detail content | Select a run whose detail content is long and confirm the detail panel still displays fully (per Non-Goal, its scroll behavior is explicitly unchanged) |
| 4 | Document selection dialog regression | AI touching shared layout primitives (e.g., a wrapper class reused by both `BatchRunsTab` and `BatchDocumentSelectModal`) could inadvertently change the dialog's centering or scroll behavior | Open "New batch run" dialog with a long document list and confirm it is still centered via `fixed inset-0 flex items-center justify-center` with internal `overflow-y-auto` scrolling, unchanged from before |

---

## 3. Pattern & ADR Compliance

No constraining ADRs.

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Screenshot or manual test log showing run cards render on tab mount with `GET /api/v1/extract-batch` fired
- [ ] Scenario 2: Manual reload test showing prior runs persist and empty state is absent
- [ ] Scenario 3: Screenshot showing selected card border and matching detail panel content
- [ ] Scenario 4: Manual trigger test showing new "queued" run appears at top and auto-selected
- [ ] Scenario 5: Network trace showing 3s polling interval and stop at terminal state
- [ ] Scenario 6: Screenshot showing correct status pill colors across completed/running/queued/failed
- [ ] Scenario 7: Screen recording or before/after screenshots showing run list scrolls independently while header, tab pills, and detail panel remain fixed
- [ ] Scenario 8: Screenshot showing dialog centered with a long document list, with only the checklist scrolling

### Structural Evidence

- [ ] Code review completed — implementation matches design.md Decision 1 (bounded `max-height`/`overflow-y: auto` on the run list column only, no `AppShell`/`ExtractionPage` restructure)
- [ ] All ADR compliance steps in Section 3 confirmed (N/A — no constraining ADRs)
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against `specs/portal-extraction-page/spec.md`)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — run list fills available height correctly at multiple viewport sizes
- [ ] Risk 2 mitigation confirmed — Playground and Entity Review tab scroll behavior unchanged
- [ ] Risk 3 mitigation confirmed — detail panel content displays fully and independently of run list bounding
- [ ] Risk 4 mitigation confirmed — document selection dialog centering/scroll unchanged

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-batch-runs-scroll-layout
**Proposal:** `openspec/changes/fix-batch-runs-scroll-layout/proposal.md`
**Spec files reviewed:**
  - specs/portal-extraction-page/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**

