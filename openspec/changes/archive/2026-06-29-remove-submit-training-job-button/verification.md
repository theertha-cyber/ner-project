# Verification Plan

**Change:** remove-submit-training-job-button
**Generated:** 2026-06-29
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-jobs | Hide submit job action for non-tenant-admin roles | Submit button visible for tenant_admin | Given an authenticated tenant_admin on the Training Queue page, the `+ Submit Job` button is present and visible in the page header | | - [ ] |
| 2 | training-jobs | Hide submit job action for non-tenant-admin roles | Submit button hidden for system_admin | Given an authenticated system_admin on the Training Queue page, the `+ Submit Job` button is not rendered in the DOM | | - [ ] |
| 3 | training-jobs | Hide submit job action for non-tenant-admin roles | Submit slideover not accessible for system_admin | Given an authenticated system_admin on the Training Queue page, no element or mechanism that triggers the submit job slideover exists in the DOM | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Role comparison | AI may use loose equality or wrong property (e.g., `user.role == "tenant_admin"` with coercion, or checking `user.roles` as an array) instead of the strict `user?.role === "tenant_admin"` pattern used in the rest of the codebase | Inspect the generated guard in `page.tsx` — confirm it reads `user?.role === "tenant_admin"` consistent with `useAuth` return shape |
| 2 | Partial removal | AI may remove the button but leave the `SubmitJobSlideover` rendered unconditionally, or vice versa, creating a state where the slideover can be triggered via URL manipulation or keyboard | Confirm both the button AND the `<SubmitJobSlideover>` render are gated by the same role check |
| 3 | Over-restriction | AI may also remove the approve/reject actions or hide the entire page header for system_admin, going beyond what the spec requires | Verify approve/reject job actions still render normally for system_admin; only the submit button/slideover is affected |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| No constraining ADRs | — | This is a UI-only visibility fix with no architectural implications; design.md identifies no in-force ADRs that apply. | N/A |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 1 (tenant_admin sees button): Screenshot or DOM inspection showing `+ Submit Job` button present when logged in as tenant_admin
- [ ] Scenario 2 (system_admin button hidden): Screenshot or DOM inspection showing button absent when logged in as system_admin
- [ ] Scenario 3 (system_admin slideover not accessible): DOM inspection confirming `SubmitJobSlideover` is not mounted for system_admin

### Structural Evidence

- [ ] Code review completed — role guard in `training-jobs/page.tsx` uses `user?.role === "tenant_admin"` and wraps both the button and `SubmitJobSlideover`
- [ ] No ADR compliance issues (none constraining this change)
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (role comparison): Confirmed the guard uses `user?.role === "tenant_admin"` matching the `useAuth` return shape
- [ ] Risk 2 (partial removal): Confirmed both the button render and `<SubmitJobSlideover>` are inside the same role guard
- [ ] Risk 3 (over-restriction): Confirmed approve/reject actions in `JobActions` remain visible and functional for system_admin

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

**Change slug:** remove-submit-training-job-button
**Proposal:** `openspec/changes/remove-submit-training-job-button/proposal.md`
**Spec files reviewed:**
- specs/training-jobs/spec.md

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
