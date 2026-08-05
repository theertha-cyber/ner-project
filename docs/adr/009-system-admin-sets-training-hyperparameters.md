# ADR-009: System Admin Sets Training Hyperparameters at Approval

**Status**: Accepted

**Supersedes**: ADR-006 (partially — overrides the "hyperparameters submitted with the job request" clause only)

**Date**: 2026-08-05

## Context

ADR-006 established the Celery/RabbitMQ async GPU worker pipeline for training jobs and stated: "Training hyperparameters submitted with the job request: learning_rate, num_epochs, batch_size, max_seq_length." Under that design, the Tenant Admin who requests a training run also chooses its hyperparameters, and System Admin approval was a rubber-stamp that enqueued whatever the tenant selected.

This puts GPU-cost- and model-quality-sensitive decisions in the hands of tenants who lack visibility into cluster capacity and training best practices. See `openspec/changes/system-admin-sets-training-params/proposal.md` and `design.md` for the full rationale.

## Decision

**Training hyperparameters are now supplied by the System Admin at approval time, not by the Tenant Admin at submission time.**

- `POST /api/v1/training-jobs` (Tenant Admin submission) no longer accepts hyperparameters; the created job has `hyperparams: null` while `pending_approval`.
- `POST /api/v1/training-jobs/{job_id}/approve` (System Admin approval) now requires `learning_rate`, `num_epochs`, `batch_size`, `max_seq_length` in its request body, validates them, persists them onto the job, and only then enqueues the Celery task and transitions the job to `queued`.

All other decisions in ADR-006 remain in force and unchanged by this ADR:

- Celery-based async GPU workers with a RabbitMQ broker, backed by K8s GPU node pools.
- GPU node pool autoscaling 0 → N based on queue depth.
- Model checkpointing at each epoch; failed jobs resume from last checkpoint.
- The 500-entity minimum dataset threshold enforced before a submission is accepted.

## Consequences

### Positive
- Hyperparameter selection — a GPU-cost- and model-quality-sensitive decision — now sits with the role that has visibility into cluster capacity and training best practices.
- Tenant Admin submission becomes a simple, low-friction request; no hyperparameter validation burden on tenants.

### Negative
- System Admin approval is no longer a single-click action — it requires filling in four fields per job, adding friction to the approval queue.
- Training jobs created before this change already carry tenant-supplied hyperparameters; approving them under the new endpoint still requires the System Admin to re-enter values (no backfill of old values into the approval form is mandated by this ADR).

### Mitigations
- The approval endpoint reuses the exact same validation bounds the tenant-facing schema previously enforced (`num_epochs` 1-50, `max_seq_length` 32-512, etc.), so no validation coverage is lost — only relocated.

## Compliance

- `TrainingJob.hyperparams` MUST be nullable to represent the pre-approval `pending_approval` state.
- The approve endpoint MUST validate hyperparameters before persisting them or enqueuing the Celery task.
- Reject, cancel, list, and status-lookup endpoints are unaffected and MUST continue to operate exactly as specified in ADR-006 and the `training-jobs` / `training-approval` specs.

## References

- `openspec/changes/system-admin-sets-training-params/proposal.md`
- `openspec/changes/system-admin-sets-training-params/design.md`
- `openspec/specs/training-jobs/spec.md`, `openspec/specs/training-approval/spec.md`
- ADR-006-training-infrastructure (partially superseded)
