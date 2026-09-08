## Why

Tenant Admins currently pick training hyperparameters (`learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`) when they submit a training job, and System Admin approval is a rubber-stamp that just enqueues whatever the tenant chose. This puts GPU-cost and model-quality-sensitive decisions in the hands of tenants who lack visibility into cluster capacity and training best practices. Hyperparameter selection should be a System Admin responsibility exercised at approval time; Tenant Admins should only be requesting that a training run happen.

## What Changes

- **BREAKING**: `POST /api/v1/training-jobs` (Tenant Admin submission) no longer accepts `learning_rate`, `num_epochs`, `batch_size`, or `max_seq_length`. The request body carries no hyperparameters; the created job SHALL have `hyperparams: null` while in `pending_approval` status.
- **BREAKING**: `POST /api/v1/training-jobs/{job_id}/approve` (System Admin approval) now requires a body containing `learning_rate`, `num_epochs`, `batch_size`, and `max_seq_length`. The System Admin's values are validated (same bounds as today: `num_epochs` 1-50, `max_seq_length` 32-512, etc.), persisted onto the job's `hyperparams`, and only then is the job transitioned to `queued` and enqueued to Celery with those System-Admin-supplied values.
- The minimum-annotated-entity preflight check on submission is unchanged — it still runs at Tenant Admin submit time, independent of hyperparameters.
- Reject, cancel, list, and status-lookup behavior are unchanged.
- Frontend: `SubmitJobSlideover` (Tenant Admin) drops the learning-rate field, epoch slider, batch-size selector, and max-sequence-length selector — it becomes a lightweight "request training" action (still runs the informational span-count preflight display).
- Frontend: the System Admin approval action gains a form (learning rate, epochs, batch size, max sequence length) that must be filled in before an approval can be submitted; reject remains a single action with an optional reason, unchanged.

## Capabilities

### New Capabilities

(none — this reshapes who supplies hyperparameters and when, it doesn't add a new domain capability)

### Modified Capabilities

- `training-jobs`: "Submit training job" requirement drops hyperparameter fields from the tenant-facing create payload; "Approve training job" requirement (duplicated in this spec) gains a required hyperparameter body and validation; "Submit form span preflight is informational only" requirement's enabled/disabled logic for the Submit button no longer depends on hyperparameter form validation, since that form no longer exists on the submit side.
- `training-approval`: "Approve training job" requirement gains a required hyperparameter payload, validation rules, and persistence of those values onto the job before enqueue; adds a new scenario for approval attempted with missing/invalid hyperparameters.
- `training-jobs-screen`: "Submit slide-over visual parity without behavior change" requirement changes — the slide-over no longer renders the epoch slider or batch-size/max-sequence-length dropdowns. Job-list/detail rendering of hyperparameters (job card summary line, detail panel's 4-column hyperparameter grid) must tolerate `hyperparams: null` for jobs still in `pending_approval`. A new requirement covers the System Admin's approval form (fields, validation, submit-disabled state).

## Impact

- Backend: `src/training_service/api/v1/schemas.py` (`TrainingJobCreate`, new `ApproveJobRequest`), `src/training_service/api/v1/training_jobs.py` (submit endpoint lines ~110-148, approve endpoint lines ~226-259), `src/training_service/infra/repository.py` (`create` no longer takes hyperparams as required input; `approve`/status-transition path needs to persist hyperparams), `src/training_service/domain/training_job.py` (`hyperparams` column becomes nullable, if not already).
- DB: `tenant_template.training_jobs.hyperparams` must permit `NULL` for jobs in `pending_approval`; likely needs a migration if the column is currently `NOT NULL`.
- Frontend: `src/portal/src/components/training-jobs/submit-job-slideover.tsx` (remove hyperparameter inputs), `src/portal/src/hooks/use-submit-training-job.ts` (payload shape), `src/portal/src/components/training-jobs/job-actions.tsx` and `use-approve-training-job.ts` (approve now needs a form/dialog collecting hyperparameters, not a one-click action), job card / detail panel components that currently assume `hyperparams` is always present.
- No change to reject, cancel, list, or status-lookup endpoints or their specs.

## Open Questions

- Should the System Admin's approval form pre-fill with any defaults (e.g. last-used values, or a tenant-tier default), or start blank every time? Assumed: start blank, no defaults, until told otherwise.
- Should Tenant Admins be able to see what hyperparameters a System Admin ultimately used, once approved/queued? Assumed: yes — the existing status/detail endpoints already return `hyperparams` once set, no new exposure needed.
- Is there an existing in-flight job (created under the old flow) migration concern, or is this rolled out for new submissions only? Assumed: no backfill needed since `pending_approval` jobs under the old flow already carry tenant-chosen hyperparams; the new "supply hyperparams at approval" path only exercises for jobs created after this change ships (existing pending jobs already have non-null hyperparams and can still be approved as-is under the same endpoint, since approval now accepts a body but the persisted values simply overwrite the null-only case).
