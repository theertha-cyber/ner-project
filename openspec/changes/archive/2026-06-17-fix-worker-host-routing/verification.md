# Verification Plan

**Change:** fix-worker-host-routing
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | worker-network-config | Worker host service connectivity | Worker processes a batch document from Docker | Given the worker is running in Docker with `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL` set to `host.docker.internal` ports, when a batch task processes a document, then the run completes with `processed_count=1` and `failed_count=0` | Manual: trigger batch extraction via API → GET run status → confirm processed_count=1, failed_count=0 | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Hardcoded URL replacement | AI may forget to update the hardcoded `http://document_service:8001` in worker.py, leaving the old URL in place | Grep worker.py for `document_service:8001` — should be gone after apply |
| 2 | Docker compose env vars | AI may add env vars to the wrong docker-compose service or miss `extra_hosts` | Verify `celery_worker_extraction` service has both `NER_DOCUMENT_SERVICE_URL`, `NER_MODEL_SERVING_URL`, and `extra_hosts` |
| 3 | Local dev regression | Env var overrides may have no defaults, breaking local `uvicorn` development | Run the extraction service locally and confirm `settings.document_service_url` defaults to `http://localhost:8001` |
| 4 | Container rebuild not done | Code changes applied but old image still used | Run `docker exec` to verify new env vars are present in the running container |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-003 Model Serving Topology | Extraction Service MUST route all inference through Serving Layer's internal endpoint | The routing path is preserved — we only change the hostname | Confirm `settings.model_serving_url` is used in worker.py and points to `/internal/v1/infer` |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Trigger a batch extraction with a valid document and running host services, then GET the run status — confirm `processed_count=1` and `failed_count=0`

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (configurable URLs via settings, host.docker.internal, extra_hosts)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — grepped worker.py for `document_service:8001` — no remaining hardcoded references
- [ ] Risk 2 mitigation confirmed — docker-compose.yml `celery_worker_extraction` has env vars and `extra_hosts`
- [ ] Risk 3 mitigation confirmed — `settings.document_service_url` defaults to `http://localhost:8001` in config.py
- [ ] Risk 4 mitigation confirmed — container rebuilt and `docker exec` shows env vars

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |

---

## 6. Audit Record

> **GATE: This section must be completed and signed by a human reviewer before archive.**

**Change slug:** fix-worker-host-routing
**Proposal:** `openspec/changes/fix-worker-host-routing/proposal.md`
**Spec files reviewed:**
- specs/worker-network-config/spec.md

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
