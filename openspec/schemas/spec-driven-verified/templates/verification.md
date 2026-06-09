# Verification Plan

**Change:** <!-- change-slug -->
**Generated:** <!-- YYYY-MM-DD -->
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | <!-- e.g., data-export --> | <!-- Requirement: User can export data --> | <!-- Scenario: Successful CSV export --> | <!-- Given a logged-in user with saved data, when they request CSV export, then a CSV file is returned containing all user records --> | <!-- e.g., unit test: `given_logged_in_user_when_export_requested_then_csv_returned` --> | - [ ] |
| 2 | | | | | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | <!-- e.g., Data model fields --> | <!-- e.g., AI may invent field names not present in spec → could introduce `exportedAt` without specification --> | <!-- Compare generated schema/model against spec.md §Requirement X — any field not named in a SHALL clause is suspect --> |
| 2 | <!-- e.g., Error path handling --> | <!-- e.g., AI may omit the THEN clause for failure scenarios, implementing only the happy path --> | <!-- Verify each WHEN/THEN failure scenario in Section 1 has a corresponding code path and a failing test --> |
| 3 | <!-- e.g., ADR compliance --> | <!-- e.g., AI may apply a pattern that was superseded by a more recent ADR --> | <!-- Re-read docs/adr/ supersession graph — confirm no superseded ADR's pattern appears in generated code --> |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| <!-- ADR-NNN-<title> --> | <!-- brief one-line summary --> | <!-- what must hold in the implementation --> | <!-- concrete check: e.g., "grep codebase for direct DB calls — none should bypass the repository layer" --> |

> If design.md references no constraining ADRs, state "No constraining ADRs" here.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] <!-- Scenario 1: [describe observable proof — e.g., "Test output showing `given_logged_in_user_when_export_requested_then_csv_returned` passes with exit 0"] -->
- [ ] <!-- Scenario 2: [describe proof] -->

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] <!-- Risk 1 mitigation confirmed — [describe what was checked and the outcome] -->
- [ ] <!-- Risk 2 mitigation confirmed — [describe what was checked and the outcome] -->
- [ ] <!-- Risk 3 mitigation confirmed — [describe what was checked and the outcome] -->

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | <!-- Functional / Structural / Edge Case --> | <!-- test run output, screenshot path, log snippet, or link --> | <!-- Scenario name(s) from Section 1 --> | <!-- reviewer name/alias --> | <!-- YYYY-MM-DD --> |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** <!-- change-slug -->
**Proposal:** `openspec/changes/<change-slug>/proposal.md`
**Spec files reviewed:**
<!-- List all spec files, e.g.:
  - specs/data-export/spec.md
  - specs/user-auth/spec.md
-->

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
