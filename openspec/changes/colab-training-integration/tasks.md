## 1. Database Migration

- [ ] 1.1 Add Alembic migration adding `compute_backend VARCHAR(20) NOT NULL DEFAULT 'platform'` and `last_heartbeat_at TIMESTAMPTZ NULL` to `training_jobs`, applied to `tenant_template` and all existing `tenant_*` schemas (following the loop pattern in `alembic/versions/012_reconcile_training_jobs_columns.py`).
- [ ] 1.2 In the same migration, add `training_job_colab_tokens` table (`id`, `training_job_id` FK, `key_hash`, `key_prefix`, `expires_at`, `created_at`, `revoked_at`), applied to the same set of schemas.
- [ ] 1.3 Add `NER_COLAB_HEARTBEAT_TIMEOUT_MINUTES` (and any related interval settings) to `src/shared/config.py`, following the existing `NER_`-prefixed settings convention.

## 2. Backend: Job Creation & Notebook/Credential Generation

- [ ] 2.1 Add `compute_backend` (optional, default `"platform"`) to `TrainingJobCreate` in `src/training_service/api/v1/schemas.py`.
- [ ] 2.2 In `POST /api/v1/training-jobs`, keep the existing entity-count preflight check ahead of any backend branching, then branch: `platform` → existing `pending_approval` creation (unchanged); `colab` → create in `awaiting_notebook_launch`, generate the notebook and scoped credential synchronously, and return both in the response.
- [ ] 2.3 Implement notebook generation by importing/sharing the training logic already in `src/training_service/worker.py` (per design.md Decision 2 / Risk 2) rather than duplicating it — extract shared pieces into a common module if needed so the notebook template and the Celery worker cannot drift independently.
- [ ] 2.4 Implement scoped credential minting: `raw_token = f"ner_colab_{uuid4().hex}"`, store only `sha256(raw_token)` + prefix + `training_job_id` + `expires_at` in `training_job_colab_tokens`, embed the raw token in the generated notebook's config cell, and never persist or log the raw value.
- [ ] 2.5 Add `test_training_jobs_colab.py::test_notebook_and_credential_generated_on_create` and `::test_credential_resolves_to_single_job`.

## 3. Backend: Callback & Heartbeat Endpoint

- [ ] 3.1 Add a new endpoint (e.g. `POST /api/v1/training-jobs/{job_id}/colab-callback`) accepting heartbeat, progress, completion, and failure payload shapes.
- [ ] 3.2 Authenticate the callback by hashing the presented credential and matching it to a non-expired, non-revoked `training_job_colab_tokens` row whose `training_job_id` matches the path parameter; derive tenant scope exclusively from that row (per design.md Decision 1 / Risk 1) — reject with 401/403 and no state change on any mismatch, including credential valid-but-wrong-job.
- [ ] 3.3 On heartbeat: update `last_heartbeat_at`; transition `awaiting_notebook_launch` → `running` if applicable.
- [ ] 3.4 On progress: update `current_epoch`/`current_loss` (and `last_heartbeat_at`).
- [ ] 3.5 On completion: persist artifacts to the existing `tenant-<uuid>/models/v<version>/` MinIO path convention and register the model via the existing MLflow/Model Registry call path already used by `worker.py`, then set `completed`, `metrics`, `completed_at`. Confirm no new MinIO/MLflow-facing credentials or URLs are ever returned to the caller (per design.md Decision 7 / Risk 4).
- [ ] 3.6 On failure: set `failed`, `error_message` from the payload, `failed_at`.
- [ ] 3.7 Add `test_training_jobs_colab.py::test_heartbeat_updates_timestamp_and_transitions_to_running`, `::test_progress_callback_updates_epoch_and_loss`, `::test_completion_callback_relays_artifacts_and_registers_model`, `::test_failure_callback_sets_failed_status_and_error_message`, `::test_callback_rejected_for_invalid_or_revoked_credential`, `::test_callback_rejected_for_job_credential_mismatch`.

## 4. Backend: Stall Detection

- [ ] 4.1 Add a periodic Celery beat task (on the existing `training_service` Celery app, per design.md's leaning) scanning `colab`-backed jobs in `awaiting_notebook_launch`/`running` status.
- [ ] 4.2 For jobs whose `last_heartbeat_at` (or `created_at` if never set) exceeds `NER_COLAB_HEARTBEAT_TIMEOUT_MINUTES`, transition to `failed` with a descriptive `error_message` distinguishing "never launched" vs "stopped reporting".
- [ ] 4.3 Add `test_training_jobs_colab.py::test_stall_check_fails_job_never_launched`, `::test_stall_check_fails_job_silent_running`, `::test_stall_check_does_not_affect_active_job` — including a test with zero external requests made to any endpoint, to confirm the check runs independent of user traffic (per Risk 7).

## 5. Backend: Submit & Cancel Behavior Changes

- [ ] 5.1 Confirm (add tests, no new code expected) that `/approve` and `/reject` already reject jobs not in `pending_approval` — including `awaiting_notebook_launch` colab jobs — via the existing status check, with no colab-specific branch added (per Risk 6).
- [ ] 5.2 Update the cancel endpoint to branch on `compute_backend`: `platform` → existing Celery revoke (unchanged); `colab` → revoke the job's `training_job_colab_tokens` row (set `revoked_at`) instead of any Celery call.
- [ ] 5.3 Extend the allowed-cancel-status set to include `awaiting_notebook_launch`.
- [ ] 5.4 Add `test_training_jobs.py::test_submit_colab_job_awaiting_notebook_launch`, `::test_submit_colab_job_insufficient_entities`, `::test_submit_defaults_compute_backend_platform`, `::test_cancel_colab_job_awaiting_launch`, `::test_cancel_colab_job_running`.
- [ ] 5.5 Re-run existing `test_training_jobs.py::test_submit_valid_platform_job`, `::test_submit_insufficient_entities`, `::test_submit_as_non_admin`, `::test_submit_invalid_hyperparameters`, `::test_cancel_pending_approval_job`, `::test_cancel_queued_job`, `::test_cancel_completed_job_422` to confirm no regression.

## 6. Networking: Gateway Route

- [ ] 6.1 Add a new gateway route proxying only `POST /api/v1/training-jobs/{job_id}/colab-callback` to `training_service` — explicitly not a wildcard proxy for the rest of `training_service` (per design.md Decision 6 / Risk 3).
- [ ] 6.2 Confirm via route configuration review that no other `training_service` path becomes newly reachable through the gateway as a side effect.

## 7. Frontend

- [ ] 7.1 Add a compute-backend choice (platform/colab) to `src/portal/src/components/training-jobs/submit-job-slideover.tsx`.
- [ ] 7.2 Add UI for downloading the generated notebook and displaying colab-specific status (`awaiting_notebook_launch`, stalled-`failed`) in the training jobs list/detail views.
- [ ] 7.3 Ensure cancel UI works for colab jobs in `awaiting_notebook_launch` status (not just `pending_approval`/`queued`/`running` as today).

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 8.6 Run `openspec validate colab-training-integration --type change --strict` and confirm it exits clean before archive.
