# Verification Plan

**Change:** fix-seed-promoted-model-conflict
**Generated:** 2026-07-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

No spec-level requirements or scenarios are defined — this is an infrastructure bug fix with no capability changes.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Existence check query | AI may write a `SELECT` with wrong WHERE clause (e.g., checking `tenant_id` only, missing `status = 'promoted'`) | Verify the SELECT checks both `tenant_id = 'demo-tenant'` AND `status = 'promoted'` |

---

## 3. Pattern & ADR Compliance

No constraining ADRs.

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Run `docker-compose up -d --build db-init` — confirm exit 0 and "Seeded promoted model" is NOT printed (skipped because already exists)
- [ ] `docker logs ner-project-db-init-1` shows no IntegrityError

### Structural Evidence

- [ ] Code review completed — existence check matches pattern used by other seed inserts
- [ ] No documented architectural patterns introduced

### Edge Case Evidence

- [ ] Risk 1 (existence check query) — confirm WHERE clause includes both `tenant_id` and `status = 'promoted'`

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
> `/opsx:archive` is run.**

**Change slug:** fix-seed-promoted-model-conflict
**Proposal:** `openspec/changes/fix-seed-promoted-model-conflict/proposal.md`
**Spec files reviewed:**
  - specs/seed-script/spec.md

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
