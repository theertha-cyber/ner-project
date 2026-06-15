# Verification Plan

**Change:** training-approval-gate
**Generated:** 2026-06-10
**Status:** 🟢 Complete — All artifacts verified, Audit Record signed.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-approval | Approve training job | Approve a pending training job | Given a training job in "pending_approval", when System Admin POSTs to /approve, then status 200 with status:"queued" and a Celery task is enqueued | `test_approve_pending_job` | ✓ |
| 2 | training-approval | Approve training job | Approve a job that is not pending_approval | Given a training job in "queued", when System Admin POSTs to /approve, then status 422 with error indicating job cannot be approved | `test_approve_non_pending` | ✓ |
| 3 | training-approval | Approve training job | Approve as non-system-admin | Given a training job in "pending_approval", when Tenant Admin POSTs to /approve, then status 403 | `test_approve_as_tenant_admin` | ✓ |
| 4 | training-approval | Reject training job | Reject a pending training job | Given a training job in "pending_approval", when System Admin POSTs to /reject with reason, then status 200 with status:"rejected" and error_message matches reason | `test_reject_pending_job` | ✓ |
| 5 | training-approval | Reject training job | Reject a pending training job without reason | Given a training job in "pending_approval", when System Admin POSTs to /reject with no body, then status 200 with status:"rejected" and error_message:null | `test_reject_pending_job_no_reason` | ✓ |
| 6 | training-approval | Reject training job | Reject a job that is not pending_approval | Given a training job in "completed", when System Admin POSTs to /reject, then status 422 with error | `test_reject_non_pending` | ✓ |
| 7 | training-approval | Reject training job | Reject as non-system-admin | Given a training job in "pending_approval", when Tenant Admin POSTs to /reject, then status 403 | `test_reject_as_tenant_admin` | ✓ |
| 8 | training-jobs | Submit training job | Submit a valid training job | Given tenant with 500+ annotated entities, when Tenant Admin POSTs to /training-jobs, then status 201 with status:"pending_approval" and no Celery task enqueued | `test_submit_valid` | ✓ |
| 9 | training-jobs | Submit training job | Submit with insufficient entities | Given tenant with <500 annotated entities, when Tenant Admin POSTs, then status 422 | `test_submit_insufficient_entities` | ✓ |
| 10 | training-jobs | Submit training job | Submit as non-admin | Given an annotator, when they POST, then status 403 | `test_submit_non_admin` | ✓ |
| 11 | training-jobs | Submit training job | Submit with invalid hyperparams | Given sufficient entities, when Tenant Admin POSTs with num_epochs=-1, then status 422 | `test_submit_invalid_hyperparams` | ✓ |
| 12 | training-jobs | Cancel training job | Cancel a pending_approval job | Given a training job in "pending_approval", when Tenant Admin POSTs to /cancel, then status 200 with status:"cancelled" | `test_cancel_pending_approval` | ✓ |
| 13 | training-jobs | Cancel training job | Cancel a queued job | Given a training job in "queued", when Tenant Admin POSTs to /cancel, then status 200 with status:"cancelled" | `test_cancel_queued` | ✓ |
| 14 | training-jobs | Cancel training job | Cancel a completed job returns 422 | Given a training job in "completed", when Tenant Admin POSTs to /cancel, then status 422 | `test_cancel_completed_422` | ✓ |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | System admin tenant scope | AI may assume system admin JWT has a null tenant_id and special-case the middleware, rather than using a tenant-scoped token for the system admin | Verify approve/reject endpoints work with a valid tenant_id in JWT (system admin user belongs to a dedicated tracking tenant) — do not change middleware to bypass tenant check |
| 2 | Celery task lifecycle | AI may forget to set `celery_task_id` on approve, or may set it on create and leave it null | Verify `create_training_job` sets `celery_task_id=NULL`; verify `approve` calls `send_task` and stores the returned task ID |
| 3 | Rejection reason storage | AI may add a separate `rejection_reason` column instead of reusing the existing `error_message` field, or may fail to clear it when the job is later approved | Verify the reject endpoint writes the reason into `error_message` and that `approve` does not clear `error_message` (it starts null for new pending jobs) |
| 4 | Cancel for pending_approval | AI may keep the `celery_app.control.revoke` call even when the job has no celery_task_id (pending_approval), causing a NoneType error | Verify cancel checks `celery_task_id` before attempting revoke — same pattern already exists for jobs with no task |
| 5 | Missing migration | AI may assume the training_jobs table already has space for new statuses but forget existing tenant schemas need the same migration | Verify `fix_schema.py`-style backfill is run, or a new Alembic migration covers existing tenant schemas — not just tenant_template |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Per-tenant database schemas | Approve/reject queries must use tenant-scoped schema; system admin must authenticate as a tenant member | Verify repository methods for approve/reject use `tenant_{tid}.training_jobs` table (same pattern as existing methods) |
| ADR-006 | Celery-based async GPU workers | Celery task enqueue only happens on approve, not on submit | Verify `celery_app.send_task` appears only in the approve handler, not in create |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] `test_approve_pending_job` passes — shows approve transitions pending_approval → queued and enqueues Celery task
- [x] `test_approve_non_pending` passes — shows 422 for non-pending jobs
- [x] `test_approve_as_tenant_admin` passes — shows 403 for non-system-admin
- [x] `test_reject_pending_job` passes — shows reject with reason
- [x] `test_reject_pending_job_no_reason` passes — shows reject without reason
- [x] `test_reject_non_pending` passes — shows 422 for non-pending jobs
- [x] `test_reject_as_tenant_admin` passes — shows 403 for non-system-admin
- [x] `test_submit_valid` passes — shows submit returns pending_approval, no Celery task
- [x] `test_submit_insufficient_entities` passes — existing 422 preserved
- [x] `test_submit_non_admin` passes — existing 403 preserved
- [x] `test_submit_invalid_hyperparams` passes — existing 422 preserved
- [x] `test_cancel_pending_approval` passes — shows cancel works for pending_approval
- [x] `test_cancel_queued` passes — existing cancel preserved
- [x] `test_cancel_completed_422` passes — existing 422 preserved

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] System admin JWT with valid tenant_id works — tests use `make_token(tid, role="system_admin")` with valid tenant; no middleware bypass introduced
- [x] Create sets `celery_task_id=NULL`, approve calls `send_task` and stores the ID — verified by `test_submit_valid` and `test_approve_pending_job`
- [x] Reject writes reason into `error_message` field (not a new column) — verified by `test_reject_pending_job`
- [x] Cancel for pending_approval does not attempt `control.revoke` on None — verified by `test_cancel_pending_approval` passing with no error
- [x] No DDL change needed — `status VARCHAR(20)` already accommodates `pending_approval` (17 chars) and `rejected` (8 chars)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_training_jobs.py -v` — 21/21 passed | All 14 scenarios in §1 | agent | 2026-06-10 |
| 2 | Structural | Code review of `training_jobs.py` — approve/reject endpoints match design.md | §3 ADR-001, ADR-006 compliance | agent | 2026-06-10 |
| 3 | Edge Case | Verified cancel with no celery_task_id works (pending_approval path) | Risk 4 (cancel for pending_approval) | agent | 2026-06-10 |
| 4 | Functional | Confirmed approve transitions job pending_approval→queued, enqueues Celery task via Redis | Scenario 1 | user | 2026-06-11 |
| 5 | Functional | Confirmed reject sets status to rejected with error_message | Scenario 4-5 | user | 2026-06-11 |
| 6 | Operational | Celery worker starts with `--pool=solo` on Windows, connects to Redis, consumes tasks | Workers 24-25 | user | 2026-06-11 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** training-approval-gate
**Proposal:** `openspec/changes/training-approval-gate/proposal.md`
**Spec files reviewed:**
- specs/training-approval/spec.md
- specs/training-jobs/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
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

**Archive approved by:** Theertha Krishna

**Date:** 2026-06-11

**Notes:** Change implements training approval gate (pending_approval → approve/reject workflow). All 21 tests passing. Celery integration verified end-to-end.
