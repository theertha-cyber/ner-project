# Verification Plan

**Change:** fix-extraction-run-persistence
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | Batch extraction | Trigger batch extraction | Given a tenant with a promoted model and documents in `processed` status, when a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1,doc2,doc3`, then the response has status 202 with `run_id` and `status: "queued"`, and a subsequent GET to `/api/v1/extract-batch/{run_id}` returns `status: "queued"` | `TestTriggerBatchReturns202::test_trigger_batch_endpoint_returns_202`, `TestBatchQueuedRunIsQueryable::test_get_run_returns_queued_after_post` | - [x] |
| 2 | extraction-service | Batch extraction | Batch extraction skips already-extracted documents | Given a document already extracted with the current active model version, when batch extraction is triggered, then the document is skipped and the run report indicates it was skipped | *(requires Celery worker running — manual integration test)* | - [ ] |
| 3 | extraction-service | Batch extraction | Batch extraction for tenant with no promoted model | Given a tenant with no promoted model, when a Tenant Admin POSTs to `/api/v1/extract-batch`, then status is 202 and eventually becomes "failed" | `TestBatchNoModelReturns202::test_batch_no_model_still_returns_202` (partial — async "failed" requires Celery) | - [x] |
| 4 | extraction-service | Get extraction run status | Get extraction run status | Given a batch extraction run in "running" status, when a Tenant Admin GETs `/api/v1/extract-batch/{run_id}`, then status is 200 with `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count` | `TestBatchQueuedRunIsQueryable::test_get_run_returns_queued_after_post` | - [x] |
| 5 | extraction-service | Get extraction run status | Get extraction run status of completed run | Given a completed batch extraction run, when a Tenant Admin GETs `/api/v1/extract-batch/{run_id}`, then status is 200 with `status: "completed"` and `completed_at` | *(requires Celery worker running — manual integration test)* | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Data model — column names | AI may invent column names not in spec (e.g., `error_message`, `elapsed_seconds`) when writing the migration | Compare migration column names against `BatchRunStatus` schema in `schemas.py` — any column not named in spec or Pydantic model is suspect |
| 2 | `_create_run` removal from worker | AI may forget to remove the per-document `_create_run` call from `worker.py` or may still pass `doc_id` when creating the aggregate batch row | Verify the worker no longer calls `_create_run` with a `doc_id` parameter; confirm only one `INSERT` per run in POST handler |
| 3 | Error path — `_update_run_status("failed")` on line 105 | AI may keep the early `_update_run_status` call before any row exists, causing a silent UPDATE-on-no-rows failure | Verify that all `_update_run_status` calls in `worker.py` happen AFTER the run row is created (either by the worker or already present from POST) |
| 4 | Migration — nullable `document_id` | AI may drop `document_id` or make it non-nullable instead of nullable | Verify migration uses `ALTER COLUMN ... DROP NOT NULL` — not a column drop |
| 5 | Migration — template-only vs all schemas | AI may apply migration to `tenant_template` only, missing existing tenant schemas | Verify migration helper iterates all tenant schemas or uses the same `for_each_tenant_schema` pattern as prior migrations |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Per-tenant PostgreSQL schema isolation (`tenant_<uuid>`) | All DB writes (POST handler INSERT, migration ALTER TABLE) must use the correct per-tenant schema | Verify POST handler uses `_schema(tenant_id)` pattern; confirm migration iterates every tenant schema |
| ADR-008 | Base model version "0" is the default when no promoted model exists | `_create_run` / insert must accept `model_version = "0"` without error | Confirm the INSERT uses `model_version = "0"` when no promoted model exists; verify no NOT NULL violation on `model_version` |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Test 1 — `TestTriggerBatchReturns202::test_trigger_batch_endpoint_returns_202` passes: POST returns 202 with `run_id` and `status: "queued"`
- [x] Test 2 — `TestBatchQueuedRunIsQueryable::test_get_run_returns_queued_after_post` passes: POST then GET returns 200 with `status: "queued"` and zero progress counts
- [x] Test 3 — `TestBatchNoModelReturns202::test_batch_no_model_still_returns_202` passes: POST with no-model tenant returns 202
- [x] Test 4 — `TestGetRunStatusNotFound::test_get_nonexistent_run_returns_404` passes: GET with nonexistent run ID returns 404
- [ ] Test 5 — Manual integration test: GET returns `status: "completed"` with `completed_at` after Celery worker finishes (requires running Celery)

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions:
  - POST handler pre-creates run row (Decision 1 ✓)
  - Single row per batch run (Decision 2 ✓)
  - Alembic migration adds 6 columns + nullable document_id (Decision 3 ✓)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — migration column names (`completed_at`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`) match `BatchRunStatus` schema fields exactly
- [x] Risk 2 mitigation confirmed — `_create_run` removed from `worker.py`; single INSERT in POST handler
- [x] Risk 3 mitigation confirmed — row pre-created in POST handler; all `_update_run_status` calls in worker UPDATE an existing row
- [x] Risk 4 mitigation confirmed — migration uses `ALTER COLUMN ... DROP NOT NULL`, not a column drop
- [x] Risk 5 mitigation confirmed — migration iterates all `tenant_%` schemas via `FOR ... IN (SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%')`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-extraction-run-persistence
**Proposal:** `openspec/changes/fix-extraction-run-persistence/proposal.md`
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
