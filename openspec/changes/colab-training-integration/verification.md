# Verification Plan

**Change:** colab-training-integration
**Generated:** 2026-07-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | colab-training-integration | Generate Colab notebook and scoped credential on job creation | Notebook and credential generated on colab job creation | Given a tenant meeting the entity minimum, when a Tenant Admin submits a job with compute_backend=colab, then the response is 201 with a downloadable notebook containing an embedded credential, and that raw credential is never retrievable again | `test_training_jobs_colab.py::test_notebook_and_credential_generated_on_create` | - [ ] |
| 2 | colab-training-integration | Generate Colab notebook and scoped credential on job creation | Credential resolves to exactly one training job | Given a credential generated for job A, when it is presented on a callback, then it resolves only to job A and job A's tenant, never a caller-supplied tenant | `test_training_jobs_colab.py::test_credential_resolves_to_single_job` | - [ ] |
| 3 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Heartbeat updates last-heartbeat timestamp | Given a job in awaiting_notebook_launch or running with a valid credential, when a heartbeat callback arrives, then last-heartbeat is updated and status becomes running if it was awaiting_notebook_launch | `test_training_jobs_colab.py::test_heartbeat_updates_timestamp_and_transitions_to_running` | - [ ] |
| 4 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Progress update reflected in job status | Given a running colab job, when a progress callback arrives, then GET on the job reflects the updated current_epoch and current_loss | `test_training_jobs_colab.py::test_progress_callback_updates_epoch_and_loss` | - [ ] |
| 5 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Terminal success relays artifacts and metrics server-side | Given a running colab job, when a completion callback arrives with metrics and artifacts, then artifacts are persisted at the standard storage location, a model version is registered, and status becomes completed | `test_training_jobs_colab.py::test_completion_callback_relays_artifacts_and_registers_model` | - [ ] |
| 6 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Terminal failure reported by the notebook | Given a running colab job, when a failure callback arrives with an error message, then status becomes failed and error_message reflects the reported error | `test_training_jobs_colab.py::test_failure_callback_sets_failed_status_and_error_message` | - [ ] |
| 7 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Callback rejected with invalid or revoked credential | Given an expired, revoked, or unrecognized credential, when a callback is made with it, then the response is 401/403 and no job state changes | `test_training_jobs_colab.py::test_callback_rejected_for_invalid_or_revoked_credential` | - [ ] |
| 8 | colab-training-integration | Callback endpoint accepts heartbeats, progress, and terminal results | Callback rejected when credential and job id mismatch | Given a credential scoped to job A, when a callback is made against job B's URL using job A's credential, then the response is 403 and no job state changes | `test_training_jobs_colab.py::test_callback_rejected_for_job_credential_mismatch` | - [ ] |
| 9 | colab-training-integration | Stalled colab jobs automatically fail | Job never launched times out | Given a colab job in awaiting_notebook_launch past the timeout window, when the stall check runs, then status becomes failed with a "no launch detected" error message | `test_training_jobs_colab.py::test_stall_check_fails_job_never_launched` | - [ ] |
| 10 | colab-training-integration | Stalled colab jobs automatically fail | Running job goes silent and times out | Given a running colab job whose last heartbeat is past the timeout window, when the stall check runs, then status becomes failed with a "stopped reporting" error message | `test_training_jobs_colab.py::test_stall_check_fails_job_silent_running` | - [ ] |
| 11 | colab-training-integration | Stalled colab jobs automatically fail | Active job is not affected by the stall check | Given a running colab job whose last heartbeat is within the timeout window, when the stall check runs, then status is unchanged | `test_training_jobs_colab.py::test_stall_check_does_not_affect_active_job` | - [ ] |
| 12 | colab-training-integration | Colab job credential revocation on cancel | Cancelling a colab job revokes its credential | Given a colab job in awaiting_notebook_launch or running, when a Tenant Admin cancels it, then status becomes cancelled and the credential is revoked (rejected on subsequent use) | `test_training_jobs_colab.py::test_cancel_colab_job_revokes_credential` | - [ ] |
| 13 | training-jobs | Submit training job | Submit a valid training job | Given a tenant with sufficient entities, when a Tenant Admin submits with default backend, then response is 201 with status pending_approval, no celery_task_id, and no Celery task enqueued | `test_training_jobs.py::test_submit_valid_platform_job` | - [ ] |
| 14 | training-jobs | Submit training job | Submit training job with insufficient entities | Given a tenant below the entity minimum, when submitting, then response is 422 indicating the threshold is not met | `test_training_jobs.py::test_submit_insufficient_entities` | - [ ] |
| 15 | training-jobs | Submit training job | Submit training job as non-admin | Given an annotator, when they submit a job, then response is 403 | `test_training_jobs.py::test_submit_as_non_admin` | - [ ] |
| 16 | training-jobs | Submit training job | Submit training job with invalid hyperparameters | Given sufficient entities, when submitting invalid hyperparameters, then response is 422 describing the invalid field | `test_training_jobs.py::test_submit_invalid_hyperparameters` | - [ ] |
| 17 | training-jobs | Submit training job | Submit a valid training job with compute_backend colab | Given sufficient entities, when a Tenant Admin submits with compute_backend=colab, then response is 201 with status awaiting_notebook_launch, no celery_task_id, no Celery task enqueued, and no approval required | `test_training_jobs.py::test_submit_colab_job_awaiting_notebook_launch` | - [ ] |
| 18 | training-jobs | Submit training job | Submit a colab training job with insufficient entities | Given a tenant below the entity minimum, when submitting with compute_backend=colab, then response is 422 indicating the threshold is not met, same as the platform path | `test_training_jobs.py::test_submit_colab_job_insufficient_entities` | - [ ] |
| 19 | training-jobs | Submit training job | compute_backend defaults to platform when omitted | Given sufficient entities, when submitting without compute_backend, then the job is created with compute_backend=platform and unchanged existing behavior | `test_training_jobs.py::test_submit_defaults_compute_backend_platform` | - [ ] |
| 20 | training-jobs | Cancel training job | Cancel a pending_approval job | Given a job in pending_approval, when a Tenant Admin cancels it, then response is 200 with status cancelled | `test_training_jobs.py::test_cancel_pending_approval_job` | - [ ] |
| 21 | training-jobs | Cancel training job | Cancel a queued job | Given a job in queued, when a Tenant Admin cancels it, then response is 200 with status cancelled | `test_training_jobs.py::test_cancel_queued_job` | - [ ] |
| 22 | training-jobs | Cancel training job | Cancel a completed job returns 422 | Given a job in completed, when a Tenant Admin cancels it, then response is 422 indicating it cannot be cancelled | `test_training_jobs.py::test_cancel_completed_job_422` | - [ ] |
| 23 | training-jobs | Cancel training job | Cancel a colab job in awaiting_notebook_launch status | Given a colab job in awaiting_notebook_launch, when cancelled, then response is 200 with status cancelled, the credential is revoked, and no Celery revoke is attempted | `test_training_jobs.py::test_cancel_colab_job_awaiting_launch` | - [ ] |
| 24 | training-jobs | Cancel training job | Cancel a colab job in running status | Given a colab job in running, when cancelled, then response is 200 with status cancelled, the credential is revoked, and a subsequent callback using it is rejected | `test_training_jobs.py::test_cancel_colab_job_running` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change appears above (24/24). A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Credential-to-tenant resolution | AI may resolve the acting tenant from a client-supplied field (e.g. a tenant_id in the callback body) instead of deriving it solely from the credential lookup, allowing a caller to spoof another tenant's job | Read the callback handler implementation and confirm tenant/job identity is derived exclusively from the DB row matched by the hashed credential, never from request body/path values taken at face value |
| 2 | Notebook template drift | AI may hand-copy `worker.py`'s training logic into the notebook template once, creating two divergent copies of the fine-tuning code that drift apart on future changes | Confirm the notebook-generation code imports/shares logic with `worker.py` (or a common module) rather than duplicating it inline |
| 3 | Gateway route over-exposure | AI may add a gateway proxy rule that forwards all of `training_service`'s paths instead of only the colab-callback route, newly exposing approve/reject/cancel/list endpoints to the public internet | Inspect the gateway route configuration and confirm only the specific colab-callback path is proxied, not a wildcard `training_service` prefix |
| 4 | MinIO/MLflow exposure shortcut | AI may implement artifact return via a presigned MinIO URL handed to the notebook (simpler to code) instead of the server-side relay decided in design.md, quietly exposing MinIO to the internet | Confirm the callback handler receives artifact bytes/data in the request itself and performs the MinIO put/MLflow registration server-side; confirm no presigned URL or MinIO endpoint is ever returned to the notebook |
| 5 | Status value invention | AI may introduce a new status string (e.g. `colab_running`, `colab_completed`) instead of reusing the existing `running`/`completed`/`failed` values as specified, breaking existing frontend status-based filtering/coloring | Query the `training_jobs.status` values produced by colab-path tests and confirm only `awaiting_notebook_launch`, `running`, `completed`, `failed`, `cancelled` appear — no colab-prefixed variants |
| 6 | Approve/reject gap for colab jobs | AI may add an explicit new branch to reject colab jobs at `/approve`/`/reject`, but implement it checking `compute_backend` instead of relying on `awaiting_notebook_launch` never being `pending_approval` — a subtle bug could let a colab job be manually forced into `pending_approval` and then approved into a non-existent Celery dispatch path | Attempt to call `/approve` and `/reject` against a job in `awaiting_notebook_launch` status directly; confirm both return the existing "wrong status" 422 with no code path that enqueues a Celery task for a colab-backed job under any status |
| 7 | Stall-check task placement | AI may implement the stall check as inline logic inside an existing request-handling endpoint (only triggered when someone happens to call it) rather than a genuinely periodic background task, leaving stalled jobs undetected until unrelated traffic occurs | Confirm a scheduled/periodic task (Celery beat or equivalent) exists and runs independent of any user-triggered request, and that a job left completely untouched (no polling, no requests) still transitions to failed after the timeout in a test that doesn't call any other endpoint |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|---------------------------|--------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via per-tenant Postgres schema; all queries scoped via `search_path`/`tenant_context`; object storage uses `tenant-<uuid>/` prefixes | The new credential table, callback endpoint, and notebook-generation code must resolve tenant scope from the matched credential/job row, never from client input, and any new object storage writes must use the existing tenant-prefixed path convention | Review the callback handler and credential lookup code for tenant scoping; confirm new DB access goes through the existing tenant_context mechanism; confirm artifact writes use `tenant-<uuid>/` paths |
| ADR-003-model-serving-topology | Model artifacts land at `s3://ner-platform/tenant-<uuid>/models/v<version>/`; Model Registry resolves active version at inference time; Serving Layer is agnostic to training origin | Colab-trained models must be written to the identical path convention and registered identically to platform-trained models, with no Colab-specific branch in Model Serving code | Trigger a colab job through to completion in a test environment and confirm the resulting artifact path and Model Registry entry are indistinguishable in shape from a platform-trained model's; grep Model Serving code for any `colab`/`compute_backend` references (should be none) |
| ADR-006-training-infrastructure | 500-entity minimum threshold before training is permitted; hyperparameters submitted with the job request; Celery/GPU-worker path for the platform backend unchanged | The entity-count minimum must be enforced identically for `colab` and `platform` submissions; the existing Celery/K8s execution path must remain completely unmodified by this change | Confirm the entity-count preflight check runs before backend branching (same code path for both); run the existing platform-path test suite unmodified and confirm it still passes after this change |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing `test_notebook_and_credential_generated_on_create` passes, including confirmation the raw credential appears exactly once in the response
- [ ] Scenario 2: Test output showing `test_credential_resolves_to_single_job` passes
- [ ] Scenario 3: Test output showing `test_heartbeat_updates_timestamp_and_transitions_to_running` passes
- [ ] Scenario 4: Test output showing `test_progress_callback_updates_epoch_and_loss` passes
- [ ] Scenario 5: Test output showing `test_completion_callback_relays_artifacts_and_registers_model` passes, including artifact path and Model Registry entry confirmation
- [ ] Scenario 6: Test output showing `test_failure_callback_sets_failed_status_and_error_message` passes
- [ ] Scenario 7: Test output showing `test_callback_rejected_for_invalid_or_revoked_credential` passes
- [ ] Scenario 8: Test output showing `test_callback_rejected_for_job_credential_mismatch` passes
- [ ] Scenario 9: Test output showing `test_stall_check_fails_job_never_launched` passes
- [ ] Scenario 10: Test output showing `test_stall_check_fails_job_silent_running` passes
- [ ] Scenario 11: Test output showing `test_stall_check_does_not_affect_active_job` passes
- [ ] Scenario 12: Test output showing `test_cancel_colab_job_revokes_credential` passes
- [ ] Scenario 13: Test output showing `test_submit_valid_platform_job` passes (regression)
- [ ] Scenario 14: Test output showing `test_submit_insufficient_entities` passes (regression)
- [ ] Scenario 15: Test output showing `test_submit_as_non_admin` passes (regression)
- [ ] Scenario 16: Test output showing `test_submit_invalid_hyperparameters` passes (regression)
- [ ] Scenario 17: Test output showing `test_submit_colab_job_awaiting_notebook_launch` passes
- [ ] Scenario 18: Test output showing `test_submit_colab_job_insufficient_entities` passes
- [ ] Scenario 19: Test output showing `test_submit_defaults_compute_backend_platform` passes
- [ ] Scenario 20: Test output showing `test_cancel_pending_approval_job` passes (regression)
- [ ] Scenario 21: Test output showing `test_cancel_queued_job` passes (regression)
- [ ] Scenario 22: Test output showing `test_cancel_completed_job_422` passes (regression)
- [ ] Scenario 23: Test output showing `test_cancel_colab_job_awaiting_launch` passes
- [ ] Scenario 24: Test output showing `test_cancel_colab_job_running` passes

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — tenant/job resolution traced to credential lookup only, not client input
- [ ] Risk 2 mitigation confirmed — notebook generation shares code with `worker.py` rather than duplicating it
- [ ] Risk 3 mitigation confirmed — gateway route proxies only the colab-callback path, not a `training_service` wildcard
- [ ] Risk 4 mitigation confirmed — no presigned MinIO URL or direct MinIO/MLflow endpoint is ever returned to the notebook
- [ ] Risk 5 mitigation confirmed — only the specified status values appear in colab-path test data, no colab-prefixed variants
- [ ] Risk 6 mitigation confirmed — `/approve` and `/reject` against an `awaiting_notebook_launch` job return the existing wrong-status 422 with no Celery dispatch path reachable for colab jobs
- [ ] Risk 7 mitigation confirmed — a job with zero external requests still transitions to failed after the timeout, proving the stall check runs independently of user traffic

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

**Change slug:** colab-training-integration
**Proposal:** `openspec/changes/colab-training-integration/proposal.md`
**Spec files reviewed:**
  - specs/colab-training-integration/spec.md
  - specs/training-jobs/spec.md

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
