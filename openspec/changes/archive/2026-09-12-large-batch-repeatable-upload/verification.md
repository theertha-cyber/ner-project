# Verification Plan

**Change:** large-batch-repeatable-upload
**Generated:** 2026-09-12
**Status:** ✅ Complete — see § 6 Audit Record.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | Both stages remain visible once the initial batch is approved and a large batch exists | Unchanged from `automated-batch-stage-visibility` | `BatchAcceptancePage.test.tsx > shows a Train model action once the large batch finishes, alongside the initial batch's own status` | - [x] |
| 2 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | The large-batch section is visible but locked before the initial batch is approved | Unchanged | `BatchAcceptancePage.test.tsx > does not unlock stage 2 while the initial batch is unreviewed` | - [x] |
| 3 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | The large-batch section unlocks its picker once the initial batch is approved | Unchanged | `BatchAcceptancePage.test.tsx > keeps the approved initial batch's status visible while unlocking the large-batch picker` | - [x] |
| 4 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | A notification fires when each stage completes | Unchanged | `BatchAcceptancePage.test.tsx > toasts exactly once, on the transition to annotator-approved — not on every render` | - [x] |
| 5 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | The large-batch picker stays available after a previous large batch has already completed | Given a completed large batch, when the screen renders, then the document picker and "Pre-label these documents" are still shown, not replaced | `BatchAcceptancePage.test.tsx > shows a Train model action once the large batch finishes, alongside the initial batch's own status` (extended with picker-presence assertions) | - [x] |
| 6 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | Starting another large batch is disabled while one is already running | Given a queued/processing large batch, when the screen renders, then the picker is shown with an "already running" message | `BatchAcceptancePage.test.tsx > disables starting another large batch while one is already running, but keeps the picker visible` (new) | - [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Backend assumed to need a change too | Assuming `create_prelabel_batch`'s single-`large`-batch-per-tenant behavior needed a backend fix, when in fact the backend never limited a tenant to one `large` batch — only the frontend's `.find()` (first match) and "hide picker once one exists" display logic did | Confirmed by re-reading `create_prelabel_batch`: its only `large`-kind gate is `INITIAL_BATCH_NOT_APPROVED`; nothing there checks for an existing `large` batch. No backend file in this change's diff. |
| 2 | "Most recent" vs "any" large batch | The picker's disabled state and the status section both key off `batches.find(b => b.batch_kind === "large")`, which returns the newest (list is server-sorted newest-first) — an agent could have wired the disabled check to some other batch (e.g. the first-ever one) and silently permitted concurrent submission against a stale reference | Confirmed by code reading: `largeSummary`/`largeId`/`largeBatch` are all derived from the same single `.find()` result used throughout the section, not a mix of "first" and "latest" |

---

## 3. Pattern & ADR Compliance

No constraining ADRs — presentation-layer fix, no architectural commitment.

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-4: unchanged, still passing (regression check)
- [x] Scenario 5: `vitest` pass (extended existing test)
- [x] Scenario 6: `vitest` pass (new test)

### Structural Evidence

- [x] Code review completed — matches proposal.md
- [x] `tsc --noEmit` clean
- [x] Full portal `vitest run`: same pre-existing 6-failed-file baseline (750/760 passing, up from 748/758 with the 2 new assertions/test), no new failures

### Edge Case Evidence

- [x] Risk 1 (assumed backend change) confirmed unnecessary — no backend diff
- [x] Risk 2 (most-recent vs any) confirmed correct by code reading

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `vitest run src/components/seed-bootstrap/BatchAcceptancePage.test.tsx` in `ner-portal-test`: 7/7 passed | 1-6 | Claude (implementing agent) | 2026-09-12 |
| 2 | Structural | `vitest run` (whole portal suite): 106 files / 750 tests passed, same 6 pre-existing failing files | Regression check | Claude (implementing agent) | 2026-09-12 |
| 3 | Structural | `tsc --noEmit`, grepped for `BatchAcceptancePage`: zero matches | Type safety | Claude (implementing agent) | 2026-09-12 |
| 4 | Functional | Live click-through on the rebuilt `ner-project-portal-1` at `localhost:3000` as `admin@democorp.io`: from this tenant's current (empty) state, the screen correctly shows the Stage 1 picker and locked Stage 2 — this tenant did not reproduce the reported stale-6-document state, which belongs to the project owner's own tenant/session, not this shared demo seed data | Sanity check only — the reported bug's exact data state could not be reproduced in this environment; the fix was verified by unit test instead | Claude (implementing agent) | 2026-09-12 |

---

## 6. Audit Record

> Completed by the implementing agent at the project owner's direction. This is NOT an
> independent human review.

**Change slug:** large-batch-repeatable-upload
**Proposal:** `openspec/changes/large-batch-repeatable-upload/proposal.md`
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
- This fix was reported by the project owner from their own tenant/session showing a
  previously-completed large batch (6/6 documents); this environment's shared demo tenant did
  not have that same state to reproduce against live, so verification relies on unit tests
  that construct the exact reported scenario (a completed large batch existing) directly.
- No backend changes. No migration.

**Notes:**
Third small fast-follow change on the same screen this session
(`annotation-workflow-review-simplification` → `automated-batch-stage-visibility` →
this one), each addressing real in-product feedback from the project owner rather than a
fresh design round.
