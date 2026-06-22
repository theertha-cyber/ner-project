# Verification Plan

**Change:** fix-promote-inprogress-transition
**Generated:** 2026-06-22
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-annotation | Task Status Lifecycle | First span creation via token click triggers in-progress transition | Given a task with status `unannotated` and no spans, when the user creates the first confirmed span via token click, then a `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}` is sent and the task badge updates | | - [ ] |
| 2 | portal-annotation | Task Status Lifecycle | Promoting a suggestion triggers in-progress transition | Given a task with status `unannotated` and no confirmed spans, when the user promotes a suggested span, then a `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}` is sent and the task badge updates to "in-progress" | | - [ ] |
| 3 | portal-annotation | Task Status Lifecycle | In-progress transition fires only once per session | Given a task with status `unannotated`, when the user creates or promotes multiple spans in the same session, then the in-progress PATCH is sent exactly once | | - [ ] |
| 4 | portal-annotation | Task Status Lifecycle | Mark Complete button is visible but disabled with no spans | Given an active task with zero confirmed spans, when the toolbar renders, then the "Mark Complete" button is visible with a distinct border and text and a tooltip "Add at least one confirmed span before completing" | | - [ ] |
| 5 | portal-annotation | Task Status Lifecycle | Mark Complete becomes enabled when spans exist | Given an active task with at least one confirmed span, when the toolbar renders, then the "Mark Complete" button is enabled and styled with the primary action color | | - [ ] |
| 6 | portal-annotation | Task Status Lifecycle | Mark Complete transitions task to completed | Given a task with status `in-progress` and at least one confirmed span, when the user clicks "Mark Complete", then `PATCH /annotation-tasks/{id}` with `{status: "completed"}` is sent, the badge updates to "completed", and the next non-completed task is auto-selected | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Guard pattern replication | Agent copies the guard block but forgets to add `taskStatuses` to `handlePromote`'s `useCallback` dependency array, causing stale closure bugs where the guard reads the wrong status | Inspect the `useCallback` dependency array of `handlePromote` — `taskStatuses` must be present alongside `selectedTask`, `spanState.suggested`, and `toast` |
| 2 | Ref mutation order | Agent places `sentInProgressRef.current.add(selectedTask.id)` after the `if (patchRes.ok)` check instead of before the fetch, breaking the idempotency guarantee and allowing duplicate in-progress PATCHes on concurrent promotions | Verify that `sentInProgressRef.current.add(...)` is called before `await authFetch(...)` in `handlePromote`, matching the same order in `handleTokenClick` |
| 3 | Placement of guard block | Agent adds the guard inside the `if (!res.ok)` error branch or before the `dispatch({ type: "SUGGESTION_PROMOTE" })` call, so it fires even on failed promotes | Confirm the in-progress guard runs only after the `dispatch({ type: "SUGGESTION_PROMOTE" })` call (i.e., after a verified successful promote) |
| 4 | Scenario 3 (fires once) misread | Agent adds a check for `confirmedCount === 0` instead of using `sentInProgressRef`, causing the guard to fire on every promote when spans are deleted and re-added | Confirm the guard uses `!sentInProgressRef.current.has(selectedTask.id)` — not a count check |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-005-opencode-agent-boundaries | Agent edits are scoped to the repository; infrastructure and DB changes require explicit approval | This change must touch only `AnnotationPage.tsx` — no migrations, no backend files, no infra config | Confirm git diff contains only changes to `src/portal/src/components/annotation/AnnotationPage.tsx` and spec/planning artifacts |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 2 (Promote triggers in-progress): In the browser, with a task in `unannotated` status, run Pre-label, promote one suggestion — confirm the network tab shows a `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}` returning 200, and the task badge in the queue updates to "in-progress"
- [ ] Scenario 6 (Mark Complete succeeds after promote-only flow): After the above, click "Mark Complete" — confirm a `PATCH /annotation-tasks/{id}` with `{status: "completed"}` returns 200 and no "Failed to complete task" toast appears
- [ ] Scenario 3 (fires once): Promote a second suggestion on the same task — confirm only one in-progress PATCH appears in the network tab (not two)
- [ ] Scenario 1 (token click still works): On a fresh `unannotated` task, click a token to create a span — confirm the in-progress transition still fires correctly via the token-click path
- [ ] Scenario 4 (disabled button): With zero confirmed spans, confirm "Mark Complete" is visible and has a border/text but is not clickable
- [ ] Scenario 5 (enabled button): After at least one span exists, confirm "Mark Complete" is highlighted and clickable

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — `taskStatuses` is present in `handlePromote`'s `useCallback` dependency array
- [ ] Risk 2 mitigation confirmed — `sentInProgressRef.current.add(selectedTask.id)` appears before `await authFetch(...)` in `handlePromote`
- [ ] Risk 3 mitigation confirmed — guard block runs only after `dispatch({ type: "SUGGESTION_PROMOTE" })` succeeds
- [ ] Risk 4 mitigation confirmed — guard uses `!sentInProgressRef.current.has(selectedTask.id)`, not a span count comparison

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-promote-inprogress-transition
**Proposal:** `openspec/changes/fix-promote-inprogress-transition/proposal.md`
**Spec files reviewed:**
- specs/portal-annotation/spec.md

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
