# Verification Plan

**Change:** fix-worker-text-shadowing
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | Batch extraction | Trigger batch extraction | Given a tenant with a promoted model and documents in `processed` status, when a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1`, then the response has status 202 and contains `run_id` and `status: "queued"` | — | - [ ] |
| 2 | extraction-service | Batch extraction | Batch extraction persists extracted entities | Given a tenant with a promoted model and one document in `processed` status, when batch extraction completes, then `processed_count = 1`, `failed_count = 0`, and at least one row exists in `extracted_entities` linked to the `run_id` with non-null `entity_id`, `value`, and `confidence` | — | - [ ] |
| 3 | extraction-service | Batch extraction | Batch extraction skips already-extracted documents | Given a document already extracted with the current model version, when batch extraction is triggered, then the document is skipped and the run report shows `skipped_count > 0` | — | - [ ] |
| 4 | extraction-service | Batch extraction | Batch extraction for tenant with no promoted model | Given a tenant with no promoted model, when a Tenant Admin triggers batch extraction, then the response is 202 and the run status eventually becomes "failed" | — | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Variable rename scope | Agent may rename only one of the two assignment sites, leaving the other still shadowing `text` | Grep `worker.py` for `text =` — only SQLAlchemy import lines should use bare `text`; document-body assignments must use `doc_text` |
| 2 | Reference completeness | Agent may miss the `text.split()` usage after the rename, leaving a `NameError` | Read the full loop body in `worker.py` and confirm all references to the old `text` variable are updated to `doc_text` |
| 3 | Unintended scope change | Agent may accidentally rename the SQLAlchemy `text` import or wrap the SQL strings differently | Confirm `from sqlalchemy import text, create_engine` is unchanged and every `conn.execute(text(...))` call still uses the imported helper |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

No constraining ADRs — design.md confirms this is a single-file variable rename with no architectural implications.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| None | — | — | — |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 2 (entity persistence): Trigger a batch extraction run against a real document; confirm via DB query that rows exist in `extracted_entities` with the `run_id` and that `processed_count = 1`, `failed_count = 0` in `extraction_runs`
- [ ] Scenario 1 (trigger): API returns 202 with `run_id` and `status: "queued"`
- [ ] Scenario 3 (skip): Re-run extraction for same document and confirm `skipped_count = 1`, `processed_count = 0`
- [ ] Scenario 4 (no model): Run against tenant with no promoted model; confirm run reaches "failed" status

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 confirmed: `grep -n "text =" src/extraction_service/worker.py` shows no assignment to bare `text` inside the loop body
- [ ] Risk 2 confirmed: all usages of the former `text` variable (including `.split()`) reference `doc_text`
- [ ] Risk 3 confirmed: `from sqlalchemy import text, create_engine` line is unchanged; all SQL statements still pass through the `text()` helper

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

**Change slug:** fix-worker-text-shadowing
**Proposal:** `openspec/changes/fix-worker-text-shadowing/proposal.md`
**Spec files reviewed:**
- specs/extraction-service/spec.md

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
