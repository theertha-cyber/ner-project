## Why

Any tenant admin can currently push a training job directly to the Celery queue with no system admin oversight. This means tenants could consume shared GPU/compute resources without authorisation, and there's no central control over which training jobs actually run. We need an approval gate so tenant admins submit jobs for review, and system admins approve or reject them.

## What Changes

- Add `pending_approval` and `rejected` statuses to the training job lifecycle
- Tenant admin `POST /api/v1/training-jobs` now creates a job in `pending_approval` status — it does NOT enqueue a Celery task
- New `POST /api/v1/training-jobs/{job_id}/approve` endpoint (system admin only) moves the job to `queued` and enqueues the Celery task
- New `POST /api/v1/training-jobs/{job_id}/reject` endpoint (system admin only) moves the job to `rejected` with an optional reason
- Existing cancel endpoint remains tenant-admin-only; its behaviour for `pending_approval` is now also valid (cancel without a Celery task to revoke)
- The existing training-jobs spec gets behavioural changes (not just new endpoints), so we need a delta spec
- The status field on `training_jobs` table is widened to accommodate the new values (already VARCHAR(20) — `pending_approval` is 17 chars, `rejected` is 8 chars, so no migration needed)

## Capabilities

### New Capabilities

- `training-approval`: System admin approval/rejection of training jobs submitted by tenant admins

### Modified Capabilities

- `training-approval`: The existing training-jobs capability's requirements change — job submission no longer immediately enqueues work; it enters `pending_approval` instead

## Impact

- `src/training_service/api/v1/training_jobs.py`: new approve/reject endpoints, modify create endpoint to not send Celery task immediately
- `src/training_service/infra/repository.py`: may need helper for approval/rejection status transitions
- `tests/test_training_jobs.py`: update existing ACs, add scenarios for approval/rejection flow
- `training_jobs` table: status column already VARCHAR(20), no DDL change needed
- `worker.py`: no change — it only picks up jobs that are `queued`

## Open Questions

- Should the reject endpoint accept a reason/message body? (Assumption: yes, optional string)
- Should system admins see all pending jobs across all tenants? (Assumption: yes — likely via a new query or the list endpoint with no tenant scoping for system admin role)
- Does the system admin need a dedicated endpoint to list all `pending_approval` jobs across tenants? (Assumption: the list endpoint will return all when the caller is a system admin, or we add a system admin filter — yes)
