# Verification Plan

**Change:** model-registry-tenant-scoping-run-naming
**Generated:** 2026-07-29
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-registry-screen | Base Model (Version 0) Entry | Base model card visible to system_admin with no fine-tuned models trained yet | Given a system_admin viewing a tenant with no fine-tuned models, when they navigate to `/models`, then a "Base Model" v0 card is visible and marked active | `ModelRegistryPage.test.tsx` | - [ ] |
| 2 | model-registry-screen | Base Model (Version 0) Entry | Base model card visible to system_admin alongside fine-tuned models | Given a system_admin viewing a tenant with fine-tuned models, when they navigate to `/models`, then fine-tuned cards appear above the base model card shown last | `ModelRegistryPage.test.tsx` | - [ ] |
| 3 | model-registry-screen | Base Model (Version 0) Entry | Base model detail panel shows no action buttons | Given the base model card selected by a system_admin, when the detail panel renders, then no Promote/Demote/Warmup buttons appear and `dslim/bert-base-NER` is visible | `ModelRegistryPage.test.tsx` | - [ ] |
| 4 | model-registry-screen | Base Model (Version 0) Entry | Base model card hidden for tenant_admin | Given a tenant_admin viewing a tenant with no fine-tuned models, when they navigate to `/models`, then no Base Model card appears and the page still renders | `ModelRegistryPage.test.tsx` | - [ ] |
| 5 | model-registry-screen | Base Model (Version 0) Entry | Base model card hidden for business_user and annotator | Given a business_user or annotator on any tenant, when they navigate to `/models`, then no Base Model card appears | `ModelRegistryPage.test.tsx` | - [ ] |
| 6 | model-registry-screen | Base Model (Version 0) Entry | Base model card hidden even when it is the tenant's only active model | Given a tenant_admin whose tenant has no promoted model, when they navigate to `/models`, then no base model card appears and an empty state shows if no fine-tuned models exist | `ModelRegistryPage.test.tsx` | - [ ] |
| 7 | model-registry-screen | Model Version Card | Card displays run name for a completed model version | Given a model version with `run_name: "run-003-20260729"`, when the card renders, then the run name, "Completed" badge, "F1 0.89", and creation date are visible | `ModelVersionCard.test.tsx` | - [ ] |
| 8 | model-registry-screen | Model Version Card | Promoted card has distinct visual treatment | Given a promoted model version with a run name, when the card renders, then a "Promoted" badge with primary color is visible alongside the run name | `ModelVersionCard.test.tsx` | - [ ] |
| 9 | model-registry-screen | Model Version Card | Card for training version shows F1 as pending | Given a "training" status model version with a run name, when the card renders, then "F1 —" is shown | `ModelVersionCard.test.tsx` | - [ ] |
| 10 | model-registry-screen | Model Version Card | Legacy model version without a run name falls back to version-number display | Given a model version with `run_name: null` and `version_number: 1`, when the card renders, then "v1" is shown | `ModelVersionCard.test.tsx` | - [ ] |
| 11 | model-registry | List model versions | List model versions with MLflow links | Given a tenant with 3 model versions and MLflow enabled, when a Tenant Admin GETs `/api/v1/models`, then status 200 and each version includes `version_number, status, training_job_id, created_at, metrics, mlflow_run_id, mlflow_run_url, run_name` | `tests/training_service/test_models_api.py` | - [ ] |
| 12 | model-registry | List model versions | List models as annotator | Given an annotator, when they GET `/api/v1/models`, then status 200 with the same response as a Tenant Admin | `tests/training_service/test_models_api.py` | - [ ] |
| 13 | model-registry | List model versions | List models when MLflow server is unavailable | Given MLflow unreachable, when listing, then status 200 from local cache with `X-Info: mlflow-unavailable` header | `tests/training_service/test_models_api.py` | - [ ] |
| 14 | model-registry | List model versions | List all versions when multiple exist in same MLflow stage | Given 3 versions all in stage `None`, when listed, then all 3 returned with full field set including `run_name` | `tests/training_service/test_models_api.py` | - [ ] |
| 15 | model-registry | List model versions | Model version created via a run-numbered training job exposes a run name | Given a training job with `run_number: 3` submitted 2026-07-29 that completes, when GETting `/api/v1/models`, then that version has `run_name: "run-003-20260729"` | `tests/training_service/test_models_api.py` | - [ ] |
| 16 | model-registry | List model versions | Legacy model version with no run_number exposes a null run name | Given a legacy model version with no `run_number`, when GETting `/api/v1/models`, then `run_name: null` | `tests/training_service/test_models_api.py` | - [ ] |
| 17 | model-registry | Base model omits run name | Active model endpoint returns null run name for the base model | Given a tenant with no promoted model, when GETting `/api/v1/models/active`, then status 200 with `version_number: 0, run_name: null` | `tests/training_service/test_models_api.py` | - [ ] |
| 18 | training-jobs | Submit training job | Submit a valid training job | Given ≥500 annotated entities, when POSTing valid hyperparams, then status 201 with `id, status, created_at, run_number, run_name`, no `celery_task_id`, no Celery task enqueued | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 19 | training-jobs | Submit training job | Submit training job with insufficient entities | Given <500 entities, when POSTing, then status 422 indicating threshold not met | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 20 | training-jobs | Submit training job | Submit training job as non-admin | Given an annotator, when POSTing, then status 403 | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 21 | training-jobs | Submit training job | Submit training job with invalid hyperparameters | Given sufficient entities, when POSTing `num_epochs: -1`, then status 422 describing the invalid parameter | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 22 | training-jobs | Submit training job | Sequential run numbers assigned per tenant, starting at 1 | Given a tenant with no prior jobs, when 3 jobs are submitted in sequence, then run_numbers are 1, 2, 3 with matching dated run_names | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 23 | training-jobs | Submit training job | Run numbers are not reused after cancellation, rejection, or failure | Given the latest job has `run_number: 4` and is cancelled, when a new job is submitted, then it receives `run_number: 5` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 24 | training-jobs | Get training job status | Get status of queued job | Given a "queued" job, when GET by Tenant Admin, then status 200 with `status, hyperparams, tenant_id, created_at, run_number, run_name` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 25 | training-jobs | Get training job status | Get status of running job | Given a "running" job, when GET, then status 200 with `status, current_epoch, current_loss, started_at` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 26 | training-jobs | Get training job status | Get status of completed job | Given a "completed" job, when GET, then status 200 with `status, metrics, model_version, completed_at` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 27 | training-jobs | Get training job status | Get status of failed job | Given a "failed" job, when GET, then status 200 with `status, error_message, failed_at` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 28 | training-jobs | Get training job status | Get training job as non-owner tenant | Given a job owned by tenant A, when a tenant B user GETs it, then status 404 with no existence leak | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 29 | training-jobs | Get training job status | System Admin gets a job with the correct tenant_id | Given a job owned by tenant A, when System Admin GETs with `tenant_id=<A>`, then status 200 with matching `tenant_id` | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 30 | training-jobs | Get training job status | System Admin gets a job without providing tenant_id | Given a job owned by tenant A, when System Admin GETs with no `tenant_id`, then status 400 indicating it's required | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 31 | training-jobs | Get training job status | System Admin gets a job with the wrong tenant_id | Given a job owned by tenant A, when System Admin GETs with `tenant_id=<B>`, then status 404 | `tests/training_service/test_training_jobs_api.py` | - [ ] |
| 32 | training-jobs | Model version reuses its training job's run number | Completed job's model version shares the job's run name | Given a job with `run_number: 7, run_name: "run-007-20260729"` completes, when the ModelVersion is created, then its `run_number` is 7 and `run_name` matches exactly | `tests/training_service/test_worker_run_naming.py` | - [ ] |
| 33 | training-jobs-screen | Detail panel header shows the full job id and creation timestamp | Detail header shows the run name and a creation date | Given a selected job with a `run_name` and `created_at`, when the detail panel renders, then the header shows the run name and a right-aligned formatted date | `JobDetailPanel.test.tsx` | - [ ] |
| 34 | training-jobs-screen | Detail panel header shows the full job id and creation timestamp | Detail header falls back to the full job id for legacy jobs | Given a selected job with `run_name: null`, when the detail panel renders, then the full untruncated UUID is shown | `JobDetailPanel.test.tsx` | - [ ] |
| 35 | training-jobs-screen | Job list card content | Running job card shows full summary with run name | Given a running job with a `run_name` and hyperparams, when the JobCard renders, then the run name, pulsing dot, hyperparameter line, and "—" F1 are shown | `job-card.test.tsx` | - [ ] |
| 36 | training-jobs-screen | Job list card content | Completed job card shows F1 score | Given a completed job with `metrics.eval_f1: 0.90`, when the JobCard renders, then "0.90" is shown and the dot is not pulsing | `job-card.test.tsx` | - [ ] |
| 37 | training-jobs-screen | Job list card content | Non-running job still shows a status-colored dot | Given a "pending_approval" job, when the JobCard renders, then a non-pulsing status-colored dot is shown | `job-card.test.tsx` | - [ ] |
| 38 | training-jobs-screen | Job list card content | Legacy job card falls back to job id when run_name is absent | Given a job with `run_name: null`, when the JobCard renders, then the job id is shown in place of a run name | `job-card.test.tsx` | - [ ] |
| 39 | training-jobs-screen | Dataset-to-model lineage diagram | Training job and model version boxes show their sublabels | Given the lineage diagram renders, when the TRAINING JOB and MODEL VERSION boxes render, then sublabels "dslim/bert-base-NER" and "registry" are shown respectively | `JobDetailPanel.test.tsx` | - [ ] |
| 40 | training-jobs-screen | Dataset-to-model lineage diagram | Lineage renders for a completed job with a promoted model, using matching run names | Given a job and its model version share `run_name: "run-006-20260729"`, when the detail panel renders, then all three boxes read "Annotated Documents", "run-006-20260729", "run-006-20260729" | `JobDetailPanel.test.tsx` | - [ ] |
| 41 | training-jobs-screen | Dataset-to-model lineage diagram | Lineage renders "pending" for a job with no model version yet | Given a job with no matching model version, when the detail panel renders, then the third box reads "pending" | `JobDetailPanel.test.tsx` | - [ ] |
| 42 | training-jobs-screen | Dataset-to-model lineage diagram | Lineage falls back to job id and version-number label for legacy entries | Given a legacy job and model version both with `run_name: null`, when the detail panel renders, then the TRAINING JOB box shows the job id and the MODEL VERSION box shows "v1" | `JobDetailPanel.test.tsx` | - [ ] |
| 43 | portal-extraction-page | Base model confirmation gate on extraction runs | Playground run proceeds without a dialog when a fine-tuned model is promoted | Given the active model has `version_number: 3`, when "Run extraction" is clicked, then no dialog appears and `POST /api/v1/extract` is sent immediately | `Playground.test.tsx` | - [ ] |
| 44 | portal-extraction-page | Base model confirmation gate on extraction runs | Playground run shows confirmation dialog when only the base model is available | Given the active model has `version_number: 0`, when "Run extraction" is clicked, then a confirmation dialog appears and no request is sent until the user responds | `Playground.test.tsx` | - [ ] |
| 45 | portal-extraction-page | Base model confirmation gate on extraction runs | Confirming the dialog proceeds with the base-model extraction | Given the dialog is shown, when the user confirms, then `POST /api/v1/extract` is sent and results render as normal | `Playground.test.tsx` | - [ ] |
| 46 | portal-extraction-page | Base model confirmation gate on extraction runs | Declining the dialog cancels the Playground run | Given the dialog is shown, when the user declines, then no request is sent and the results panel is unchanged | `Playground.test.tsx` | - [ ] |
| 47 | portal-extraction-page | Base model confirmation gate on extraction runs | Batch Runs shows confirmation dialog when only the base model is available | Given the active model has `version_number: 0`, when "New batch run" is clicked, then a confirmation dialog appears and no request is sent until the user responds | `BatchRuns.test.tsx` | - [ ] |
| 48 | portal-extraction-page | Base model confirmation gate on extraction runs | Declining the dialog cancels the batch run | Given the dialog is shown, when the user declines, then no `POST /api/v1/extract-batch` is sent and no new run entry appears | `BatchRuns.test.tsx` | - [ ] |
| 49 | portal-extraction-page | Base model confirmation gate on extraction runs | Confirming the dialog proceeds with the batch run | Given the dialog is shown, when the user confirms, then `POST /api/v1/extract-batch` is sent and the new run appears queued at the top of the list | `BatchRuns.test.tsx` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `run_number` assignment concurrency (Decision 1/2) | AI may implement `MAX(run_number)+1` as an unlocked read-modify-write, letting two concurrent submissions from the same tenant collide on the same `run_number` | Load-test or code-review the submission handler for an explicit row lock / `SERIALIZABLE` transaction around the `run_number` assignment query; confirm a concurrent-submission test produces two distinct sequential numbers, not a duplicate |
| 2 | Role gating of the base model card (Decision 4) | AI may implement the gate as a route-level `RequireAuth` that blocks the entire `/models` page for tenant_admin/business_user/annotator instead of only omitting the base-model card | Log in as tenant_admin and confirm `/models` renders normally (fine-tuned models visible, no redirect) with only the base-model card absent |
| 3 | Legacy row fallback (`run_name: null`) | AI may assume `run_name` is always present and skip the fallback-to-`v{version_number}`/job-id rendering path, causing a crash or blank label on pre-migration rows | Seed a model version and training job with `run_number: null` and verify the UI renders `v{version_number}` / raw id instead of erroring or showing "undefined" |
| 4 | Extraction confirmation gate scope (Decision 5) | AI may implement the gate by changing the backend `/api/v1/extract` or `/api/v1/extract-batch` contract (e.g. requiring a new query param) instead of a purely client-side pre-flight check, breaking other API consumers (embeddable widget) | Diff the backend extraction endpoints against their pre-change contract — confirm no new required parameters or response shape changes; confirm the embeddable widget's extraction path (no dialog) still works unmodified |
| 5 | Run number reuse on model-version creation (Decision 1, training-jobs ADDED requirement) | AI may keep `worker.py`'s original `MAX(version_number)+1` naming logic in parallel with the new `run_number` copy, producing a `run_name` that doesn't actually match its training job's `run_name` | Trace a single training job end-to-end (submit → complete) and confirm the job's `run_name` and its resulting model version's `run_name` are byte-identical, not independently computed |
| 6 | Base model `run_name` invariant (ADR-008 compliance) | AI may accidentally assign a synthetic `run_number`/`run_name` to the base model (e.g. defaulting nulls to `run-000-...`) since it shares the same response schema as real model versions | Inspect `_base_model_metadata()` / the active-model response for a tenant with no promoted model and confirm `run_name` is exactly `null`, not a placeholder string |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-001-tenant-data-isolation | Per-tenant schema isolation | `run_number` sequencing must be scoped per-tenant, not global | Query two different tenant schemas and confirm each has its own `run_number` sequence starting at 1, not sharing a counter |
| ADR-002-base-model-strategy (partially superseded by ADR-008) | Single curated base model for all training | Run-naming change must not alter base-model selection or training job base-model reference | Confirm training job creation still validates/records `dslim/bert-base-NER` as `base_model`, unchanged by this change |
| ADR-003-model-serving-topology | Per-tenant model serving | Confirmation dialog is portal-only; model-serving inference path must be untouched | Diff `src/model_serving/` — confirm zero code changes in that service for this change |
| ADR-006-training-infrastructure | Async Celery/RabbitMQ pipeline; artifact path `tenant-<uuid>/models/v<version>/` | `run_number` must be assignable at submission (before the async job runs); artifact paths keep the numeric `v{version_number}` form internally | Confirm artifact storage paths are unchanged (still numeric) while only the API-exposed `run_name` differs; confirm `run_number` is present on the job row immediately after the 201 response, before any Celery task exists |
| ADR-008-base-model-as-default | Base model = synthetic version 0, no DB row, shared singleton | Base model must never receive a run name; confirmation dialog fires exactly when resolution lands on version 0 | Verify `_base_model_metadata()` returns `run_name: null`; verify the confirmation dialog trigger condition is strictly `version_number === 0`, matching ADR-008's version-0 fallback definition |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1–6 (Base Model Entry, all roles): screenshots or component test output showing the base model card present for system_admin and absent for tenant_admin/business_user/annotator, including the "only active model" edge case
- [ ] Scenario 7–10 (Model Version Card): component test output showing run-name rendering and legacy fallback to `vN`
- [ ] Scenario 11–17 (model-registry backend): API test/integration test output (e.g. pytest) showing `run_name` present/null as specified across MLflow-available, MLflow-unavailable, and legacy-row cases
- [ ] Scenario 18–23 (Submit training job): API test output showing 201/422/403 responses and correct sequential/non-reused `run_number` assignment, including a concurrency test if feasible
- [ ] Scenario 24–31 (Get training job status): API test output covering each status and system_admin tenant_id branching, unchanged from prior behavior plus new `run_number`/`run_name` fields
- [ ] Scenario 32 (model version reuses run number): end-to-end test output tracing a job from submission to completion, asserting job and model version `run_name` equality
- [ ] Scenario 33–38 (Training Jobs screen cards/header): component test output or screenshots showing run-name display and legacy fallback
- [ ] Scenario 39–42 (lineage diagram): component test output or screenshot showing matching run names across the three lineage boxes and the legacy/pending fallback cases
- [ ] Scenario 43–49 (extraction confirmation gate): component/E2E test output or screen recording showing the dialog appearing only when `version_number === 0`, and confirm/decline branches for both Playground and Batch Runs

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — concurrent run_number assignment test/review outcome documented
- [ ] Risk 2 mitigation confirmed — tenant_admin `/models` page access (minus base card) verified
- [ ] Risk 3 mitigation confirmed — legacy null-`run_name` rendering verified without errors
- [ ] Risk 4 mitigation confirmed — backend extraction endpoint contracts confirmed unchanged; embeddable widget path unaffected
- [ ] Risk 5 mitigation confirmed — job/model-version `run_name` equality traced end-to-end
- [ ] Risk 6 mitigation confirmed — base model response confirmed to carry `run_name: null`, never a synthetic run label

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

**Change slug:** model-registry-tenant-scoping-run-naming
**Proposal:** `openspec/changes/model-registry-tenant-scoping-run-naming/proposal.md`
**Spec files reviewed:**
  - specs/model-registry-screen/spec.md
  - specs/model-registry/spec.md
  - specs/training-jobs/spec.md
  - specs/training-jobs-screen/spec.md
  - specs/portal-extraction-page/spec.md

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
