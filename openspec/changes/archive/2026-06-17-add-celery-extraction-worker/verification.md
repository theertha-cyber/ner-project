# Verification Plan

**Change:** add-celery-extraction-worker
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-worker-deployment | Extraction worker deployment | Worker connects and processes an extraction task | Given Redis is running, when the extraction worker starts, then it connects to Redis and subscribes to the `extraction` queue | Worker startup log output showing `ready` and `extraction` queue subscription | - [ ] |
| 2 | extraction-worker-deployment | Extraction worker deployment | Batch extraction task is consumed | Given the extraction worker is running, when a `run_batch_extraction` task is sent, then the worker processes it and the run transitions to "completed" | API response showing run status "completed" after task dispatch | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | docker-compose service definition | AI may add incorrect environment variables or miss required ones (e.g., `NER_DATABASE_URL_SYNC` for synchronous DB queries) | Compare the new service's env vars against the existing `celery_worker` — extraction worker needs `NER_DATABASE_URL_SYNC` and `NER_CELERY_BROKER_URL` |
| 2 | Worker pool type | AI may omit `--pool=solo`, causing worker to fail on Windows with `ValueError: not enough values to unpack` | Verify the command includes `--pool=solo` |
| 3 | Queue name mismatch | AI may use a different queue name than what `extraction.py` sends to (`settings.extraction_celery_queue` = `"extraction"`) | Verify `-Q extraction` matches the queue name in `src/extraction_service/api/v1/extraction.py:108` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-006 | Training Infrastructure — Celery-based async GPU workers | Establishes Celery pattern for async workers with Redis broker (MVP relaxation). Extraction worker follows same pattern. | Confirm extraction worker uses same Redis broker URL and Celery conventions as existing training worker |
| ADR-003 | Model Serving Topology — shared serving pool | Extraction worker must call model-serving for inference | Verify model-serving URL env var is set correctly (already in `src/shared/config.py` defaults) |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Worker startup log showing `celery@... ready.` and `extraction` queue subscription
- [ ] API test: POST `/api/v1/extract-batch?documentIds=...` followed by GET `/api/v1/extract-batch/{run_id}` returning `status: "completed"`

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions
- [ ] All ADR compliance steps in Section 3 confirmed
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code

### Edge Case Evidence

- [ ] docker-compose env vars match existing celery_worker pattern with extraction-specific overrides
- [ ] `--pool=solo` is present in the worker command
- [ ] Queue name `-Q extraction` matches the send_task call in `extraction.py`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

**Change slug:** add-celery-extraction-worker
**Proposal:** `openspec/changes/add-celery-extraction-worker/proposal.md`
**Spec files reviewed:**
- specs/extraction-worker-deployment/spec.md

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
