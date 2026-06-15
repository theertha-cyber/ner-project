## 1. Backend Implementation — Training Jobs Router

- [x] 1.1 Add `require_system_admin` function in `training_jobs.py` (parallel to existing `require_tenant_admin`)
- [x] 1.2 Modify `create_training_job` — remove `celery_app.send_task` call, insert job with `status='pending_approval'` and `celery_task_id=NULL`
- [x] 1.3 Add `POST /{job_id}/approve` endpoint — validates status is `pending_approval`, calls `celery_app.send_task`, updates status to `queued` with the returned task ID, returns updated job
- [x] 1.4 Add `POST /{job_id}/reject` endpoint — validates status is `pending_approval`, updates status to `rejected`, optionally stores reason in `error_message`, returns updated job
- [x] 1.5 Add `RejectJobRequest` schema in `schemas.py` with optional `reason: str | None = None`
- [x] 1.6 Update `TrainingJobResponse` to include `rejection_reason` if needed (or reuse `error_message`)
- [x] 1.7 Update cancel endpoint — allow `pending_approval` in the valid statuses check, skip `celery_app.control.revoke` if `celery_task_id` is null

## 2. Tests — Modified Existing Scenarios

- [x] 2.1 Update `test_submit_valid` — assert status is `"pending_approval"` instead of `"queued"`; verify no Celery task was enqueued (mock `send_task` should NOT be called)
- [x] 2.2 Update `test_status_queued` — rename to `test_status_pending_approval`; seed job as `pending_approval`, assert status matches
- [x] 2.3 Update `test_cancel_queued` — rename to `test_cancel_pending_approval`; after create (now `pending_approval`), cancel should still return 200

## 3. Tests — New Approve/Reject Scenarios

- [x] 3.1 `test_approve_pending_job` — create pending job, approve as system_admin, assert 200 and status="queued"
- [x] 3.2 `test_approve_non_pending` — seed job as "queued", approve, assert 422
- [x] 3.3 `test_approve_as_tenant_admin` — create pending job, approve as tenant_admin, assert 403
- [x] 3.4 `test_reject_pending_job` — create pending job, reject with reason, assert 200 and status="rejected" and error_message matches
- [x] 3.5 `test_reject_pending_job_no_reason` — create pending job, reject without body, assert 200 and status="rejected"
- [x] 3.6 `test_reject_non_pending` — seed job as "completed", reject, assert 422
- [x] 3.7 `test_reject_as_tenant_admin` — create pending job, reject as tenant_admin, assert 403
- [x] 3.8 `test_cancel_pending_approval` — create pending job, cancel as tenant_admin, assert 200 and status="cancelled"

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 4.6 Run `openspec validate training-approval-gate --type change --strict` and confirm it exits clean before archive.
