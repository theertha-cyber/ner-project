## 1. Database Migration

- [x] 1.1 Add nullable `run_number INTEGER` column to `training_jobs` in the tenant-schema migration set (per `tenant-schema-migrations` capability), applied per-tenant.
- [x] 1.2 Add nullable `run_number INTEGER` column to `model_versions` in the same migration set.
- [x] 1.3 Verify migration is additive/reversible (plain `DROP COLUMN` rollback), per design.md Migration Plan step 7.

## 2. Backend — Training Job Run Numbers

- [x] 2.1 In `src/training_service/api/v1/training_jobs.py`, assign `run_number` at job creation via a per-tenant `MAX(run_number)+1` query wrapped in a row lock / `SERIALIZABLE` transaction (design.md Decision 1 & 2, Risk 1). (Implemented via `pg_advisory_xact_lock` in `TrainingJobRepository.create`.)
- [x] 2.2 Compute and expose `run_name = f"run-{run_number:03d}-{created_at:%Y%m%d}"` in the job creation (201) response and in `_row_to_response` for `GET /api/v1/training-jobs/{job_id}` and `GET /api/v1/training-jobs`.
- [x] 2.3 Confirm `run_number` is never reassigned or reclaimed when a job is cancelled, rejected, or fails (no code path decrements or reuses the counter).
- [x] 2.4 Add/update backend tests in `tests/test_training_jobs_api.py` covering scenarios: submit valid job (with `run_number`/`run_name`), insufficient entities, non-admin, invalid hyperparameters, sequential run numbers across 3 submissions, and non-reuse after cancellation.
- [x] 2.5 Add/update backend tests in `tests/test_training_jobs_api.py` for `GET` status/list scenarios (queued/non-owner/system_admin tenant_id branches) confirming `run_number`/`run_name` are present without breaking existing fields.

## 3. Backend — Model Version Run Names

- [x] 3.1 In `src/training_service/worker.py`, when creating a `ModelVersion` on job completion, copy the owning `TrainingJob.run_number` onto the new row instead of computing an independent naming value (keep the existing `MAX(version_number)+1` logic only for the numeric `version_number`/artifact-path/MLflow purposes, per design.md Decision 1 and Non-Goals).
- [x] 3.2 In `src/training_service/api/v1/models.py`, compute and expose `run_name` in `_row_to_response` for `GET /api/v1/models` and `GET /api/v1/models/active`, `null` for rows with no `run_number` (legacy) and for `_base_model_metadata()` (design.md Decision 4).
- [x] 3.3 Add/update backend tests in `tests/test_model_registry.py` covering: MLflow-linked list, annotator read access, MLflow-unavailable cache fallback, multiple-versions-same-stage, run-numbered version exposes `run_name`, legacy version exposes `run_name: null`, and base model active-model response has `run_name: null`.
- [x] 3.4 Add a backend test tracing a single job end-to-end (submit → worker completion) asserting the job's `run_name` and its resulting model version's `run_name` are identical (design.md Risk 5). (`tests/test_training_jobs.py::TestModelVersionRunNumberInheritance`)

## 4. Frontend — Model Registry Screen Role Gating

- [x] 4.1 In `src/portal/src/components/model-registry/ModelRegistryPage.tsx`, read the authenticated user's role and only call/append `buildBaseModelEntry()` to the rendered list when `role === "system_admin"` (design.md Decision 4; keep the page itself accessible to all roles).
- [x] 4.2 Update `src/portal/src/types/model-registry.ts` (or equivalent) to add `run_name: string | null` to the `ModelVersion` type.
- [x] 4.3 In `src/portal/src/components/model-registry/ModelVersionCard.tsx`, render `run_name` when present, falling back to `v{version_number}` for legacy rows (base model keeps its static "Base Model" label, unaffected).
- [x] 4.4 Add/update tests in `src/portal/src/components/model-registry/ModelRegistryPage.test.tsx` covering: base model visible for system_admin (with and without fine-tuned models), no action buttons on base model detail, base model hidden for tenant_admin, hidden for business_user/annotator, and hidden even when it's the tenant's only active model.
- [x] 4.5 Add/update tests in `src/portal/src/components/model-registry/ModelVersionCard.test.tsx` covering: run-name display for completed/promoted/training statuses, and legacy fallback to `vN`.

## 5. Frontend — Training Jobs Screen Run Names

- [x] 5.1 Update `src/portal/src/types/training-jobs.ts` (or equivalent) to add `run_number: number | null` and `run_name: string | null` to the `TrainingJob` type.
- [x] 5.2 In the training-jobs detail panel header component, render `run_name` as the primary identifier, falling back to the full untruncated job id when absent.
- [x] 5.3 In `src/portal/src/components/training-jobs/job-card.tsx`, render `run_name` in place of the job id, falling back to the id for legacy jobs; keep the existing status dot, hyperparameter line, and F1 display unchanged.
- [x] 5.4 In the lineage diagram component (`LineageFlow` usage inside the job detail panel), use the model version's `run_name` (falling back to `v{version_number}`) for the MODEL VERSION box and the job's `run_name` (falling back to job id) for the TRAINING JOB box, keeping the "pending" case for no matching model version.
- [x] 5.5 Add/update tests in `src/portal/src/components/training-jobs/job-detail-panel.test.tsx` covering: header shows run name and creation date, header falls back to full id for legacy jobs, lineage sublabels, lineage renders matching run names for job+model version, lineage renders "pending" with no model version, and lineage legacy fallback (job id + `vN`).
- [x] 5.6 Add/update tests in `src/portal/src/components/training-jobs/job-card.test.tsx` covering: running job card with run name, completed job F1 display, non-running status dot, and legacy fallback to job id.

## 6. Frontend — Extraction Base-Model Confirmation Dialog

- [x] 6.1 Add a reusable confirmation dialog component (`src/portal/src/components/extractions/BaseModelConfirmDialog.tsx`) presenting "A fine-tuned model isn't available yet. Use the base model for this run?" with confirm/decline actions.
- [x] 6.2 In the Playground tab's "Run extraction" handler, read the tenant's active model (existing `useModelVersions()`/active-model query); if `version_number === 0`, show the dialog before calling `POST /api/v1/extract`; on decline, skip the call entirely (design.md Decision 5).
- [x] 6.3 In the Batch Runs tab's "New batch run" handler, apply the same check/dialog gate before calling `POST /api/v1/extract-batch`; on decline, skip the call and do not add a run to the list.
- [x] 6.4 Add/update tests in `src/portal/src/components/extractions/PlaygroundTab.test.tsx` covering: no dialog when a fine-tuned model is active, dialog shown when base model is active, confirm proceeds with the extraction call, decline cancels with no call sent.
- [x] 6.5 Add/update tests in `src/portal/src/components/extractions/BatchRunsTab.test.tsx` covering: dialog shown when base model is active, decline cancels with no call and no new run entry, confirm proceeds and the new run appears queued.

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 7.6 Run `openspec validate model-registry-tenant-scoping-run-naming --type change --strict` before archive.
