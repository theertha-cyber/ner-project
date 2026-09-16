# Verification Plan

**Change:** automated-batch-stage-visibility
**Generated:** 2026-09-12
**Status:** ✅ Complete — see § 6 Audit Record.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | Both stages remain visible once the initial batch is approved and a large batch exists | Given an approved initial batch and a completed large batch, when the screen renders, then both the initial approval confirmation and the large batch's completion + Train model action are visible together | `BatchAcceptancePage.test.tsx > shows a Train model action once the large batch finishes, alongside the initial batch's own status` | - [x] |
| 2 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | The large-batch section is visible but locked before the initial batch is approved | Given an unapproved initial batch, when the screen renders, then a large-batch section is visible showing a locked explanation, not a picker | `BatchAcceptancePage.test.tsx > does not unlock stage 2 while the initial batch is unreviewed` | - [x] |
| 3 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | The large-batch section unlocks its picker once the initial batch is approved | Given a freshly-approved initial batch, when the screen renders, then the large-batch picker (no cap) is shown and the initial batch's approval confirmation is still visible | `BatchAcceptancePage.test.tsx > keeps the approved initial batch's status visible while unlocking the large-batch picker` | - [x] |
| 4 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | A notification fires when each stage completes | Given the screen open, when the initial batch's `annotator_review_status` or the large batch's `state` transitions to its approved/terminal value, then a toast fires exactly once, not on every render | `BatchAcceptancePage.test.tsx > toasts exactly once, on the transition to annotator-approved — not on every render` (rerenders through not-approved → not-approved → approved → approved, asserting the call count at each step) | - [x] |

Every scenario has a passing, purpose-built test.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Two `usePrelabelBatch` calls per render (one per stage) instead of one | Assuming this doubles network/query load without checking that each is conditionally `enabled` only when its batch id is non-null, and that react-query dedupes by key | Confirmed by code reading: at most 2 polling queries per tenant (one per stage), never per render — bounded, not unbounded |
| 2 | The large-batch section's "locked" message could be shown even when a large batch already exists, if the unlock condition is checked incorrectly | The condition is `largeUnlocked` (from `annotator_review_status`), independent of whether `largeId` is already set — a wrong precedence could show "locked" over an existing batch's own status | Confirmed by test 2 (locked state, no large batch yet) and test 4 (large batch exists and visible) both passing — the two states are mutually exclusive in the render logic (`!largeUnlocked && !largeId` vs `largeId && largeBatch`) |

---

## 3. Pattern & ADR Compliance

No constraining ADRs — this is a presentation-layer change with no new architectural
commitment. `docs/adr/` already has entries so the pipeline's ADR step is satisfied without a
new one.

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: `vitest` pass
- [x] Scenario 2: `vitest` pass
- [x] Scenario 3: `vitest` pass
- [x] Scenario 4: `vitest` pass (rerender-based transition test)

### Structural Evidence

- [x] Code review completed — matches proposal.md's described restructuring
- [x] `tsc --noEmit` clean for `BatchAcceptancePage.tsx` and `use-prelabel-batch.ts`
- [x] Full portal `vitest run`: same pre-existing 6-failed-file baseline, no new failures

### Edge Case Evidence

- [x] Risk 1 (double query load) confirmed acceptable by design, bounded
- [x] Risk 2 (locked/unlocked precedence) confirmed by passing tests covering both states

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `vitest run src/components/seed-bootstrap/BatchAcceptancePage.test.tsx` in `ner-portal-test`: 6/6 passed | 1, 2, 3, 4 | Claude (implementing agent) | 2026-09-12 |
| 2 | Structural | `vitest run` (whole portal suite): 106 files / 748+ tests passed, same 6 pre-existing failing files, none referencing this change | Regression check | Claude (implementing agent) | 2026-09-12 |
| 3 | Structural | `tsc --noEmit`, grepped for `BatchAcceptancePage|use-prelabel-batch`: zero matches | Type safety | Claude (implementing agent) | 2026-09-12 |
| 4 | Functional | Live click-through on the rebuilt `ner-project-portal-1` at `localhost:3000` as `admin@democorp.io`: from a clean tenant with no batches, the screen renders "1 · Initial validation batch (up to 5 documents)" with its picker and "2 · Large batch (100+ documents, no review needed)" showing "Locked until the initial validation batch above is approved by an Annotator Admin." | 2 (real-data confirmation) | Claude (implementing agent) | 2026-09-12 |

---

## 6. Audit Record

> Completed by the implementing agent at the project owner's direction. This is NOT an
> independent human review.

**Change slug:** automated-batch-stage-visibility
**Proposal:** `openspec/changes/automated-batch-stage-visibility/proposal.md`
**Spec files reviewed:** specs/seed-bootstrap/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] (none apply) |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** Claude (implementing agent), at the direction of the project owner (theertha@inapp.com), 2026-09-12.

**Date:** 2026-09-12

**Caveats carried into the archive:**
- No backend changes. No migration. Purely how already-specified batch state is displayed.
- This change was driven directly by the project owner's in-product feedback on the
  already-archived `annotation-workflow-review-simplification`, not a fresh mockup round —
  the same fast-follow pattern as that change itself.

**Notes:**
None.
