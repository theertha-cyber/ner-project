## 1. Database Migration

- [x] 1.1 Add a new alembic revision (after `025_add_run_number_columns.py`) that relaxes `tenant_template.training_jobs.hyperparams` to nullable, applied per-tenant via the existing `_schema()`/tenant migration mechanism.
- [x] 1.2 Run the migration against the local dev DB (`scripts/setup_test_db.py` or existing migration runner) and confirm the column accepts `NULL`. Verified via `docker compose run --rm db-init` — alembic applied `030 -> 031` cleanly, seed and schema verification passed.

## 2. Backend: Submit Endpoint

- [x] 2.1 In `src/training_service/api/v1/schemas.py`, remove `learning_rate`, `num_epochs`, `batch_size`, `max_seq_length` from `TrainingJobCreate` (leave it an effectively-empty body model; do not accept unknown extra fields).
- [x] 2.2 In `src/training_service/infra/repository.py`, update `TrainingJobRepository.create` so the inserted row's `hyperparams` is `NULL` at creation (no longer sourced from the request body).
- [x] 2.3 In `src/training_service/api/v1/training_jobs.py`, update the `POST /api/v1/training-jobs` handler (~lines 110-148) to stop reading hyperparameters off the request body; keep the existing minimum-entity preflight check and audit-log call unchanged.

## 3. Backend: Approve Endpoint

- [x] 3.1 In `src/training_service/api/v1/schemas.py`, add `ApproveJobRequest` with required `learning_rate` (gt=0), `num_epochs` (1-50), `batch_size` (ge=1), `max_seq_length` (32-512) — same bounds as the removed `TrainingJobCreate` fields.
- [x] 3.2 In `src/training_service/api/v1/training_jobs.py`, update the `POST /api/v1/training-jobs/{job_id}/approve` handler (~lines 226-259) to accept `ApproveJobRequest` as its body, validate it (pydantic handles bounds; return 422 on failure per FastAPI defaults), persist the values onto the job's `hyperparams`, then enqueue `fine_tune_model` using those values (replacing the `row["hyperparams"]` read at line 244) and transition status to `queued`.
- [x] 3.3 In `src/training_service/infra/repository.py`, add/update the method used by the approve path so it writes both the new `hyperparams` and the `queued` status transition together (single UPDATE), matching design.md Decision 3.

## 4. Backend Tests

- [x] 4.1 Update `tests/test_training_jobs_api.py` (or the appropriate test module) to cover: submit endpoint no longer requires/stores hyperparameters (scenarios 1-4); approve endpoint requires and validates hyperparameters (scenarios 5-9). Ran via `poetry run pytest tests/test_training_jobs_api.py`: 15/16 pass; the 1 failure (`test_system_admin_get_job_with_wrong_tenant_id_404`) is a pre-existing bug unrelated to this change (untouched test, unset-up tenant schema causes a 500 instead of 404).
- [x] 4.2 Update `tests/test_training_jobs.py` for any repository-level assertions that assumed hyperparameters were present at creation. No change needed — this file exercises the worker's `_update_job_progress`/model-version lifecycle only and never asserts on hyperparameters at creation.
- [x] 4.3 Confirm the `training-approval` capability's duplicate scenarios (13-17) are exercised by the same approve-endpoint tests added in 4.1 — no separate test module needed since it's the same code path.

## 5. Frontend: Submit Slideover

- [x] 5.1 In `src/portal/src/components/training-jobs/submit-job-slideover.tsx`, remove the `learning_rate` input, epoch range slider, batch-size selector, and max-sequence-length selector; keep the span-count preflight fetch/display unchanged.
- [x] 5.2 Remove any submit-disabled logic tied to hyperparameter validity; Submit SHALL be gated only on in-flight state.
- [x] 5.3 In `src/portal/src/hooks/use-submit-training-job.ts`, update the payload shape to no longer send hyperparameter fields.

## 6. Frontend: System Admin Approval Form

- [x] 6.1 Add a hyperparameter form (dialog or inline, per existing UI patterns in `src/portal/src/components/training-jobs/`) triggered by the System Admin's approve action in `job-actions.tsx`, with fields for learning rate, epochs (1-50), batch size (`[4,8,16,32]`), and max sequence length (`[64,128,256]`).
- [x] 6.2 Disable the form's submit control until all four fields hold valid values.
- [x] 6.3 Update `src/portal/src/hooks/use-approve-training-job.ts` to accept and POST the hyperparameter payload to `/api/v1/training-jobs/{job_id}/approve`.
- [x] 6.4 On a 422 response, display the backend's error message on the form and keep it open with entered values intact.

## 7. Frontend: Null-Hyperparameter Rendering

- [x] 7.1 In the `JobCard` component, render "awaiting hyperparameters" (or equivalent) in place of the `lr … · …ep · bs …` summary line when `hyperparams` is `null`.
- [x] 7.2 In the job detail panel's hyperparameters section, render a placeholder message ("Hyperparameters not yet set — awaiting System Admin approval") instead of a 4-column grid of empty values when `hyperparams` is `null`; keep the 4-column grid layout for jobs that do have `hyperparams`.

## 8. Frontend Tests

- [x] 8.1 Update `src/portal/src/components/training-jobs/submit-job-slideover.test.tsx` for scenario 18 (no hyperparameter fields rendered, preflight still works).
- [x] 8.2 Update `src/portal/src/components/training-jobs/job-card.test.tsx` for scenarios 19-22 (including the new null-hyperparams placeholder case).
- [x] 8.3 Update `src/portal/src/components/training-jobs/job-detail-panel.test.tsx` for scenarios 23-24 (4-column grid; null-hyperparams placeholder).
- [x] 8.4 Update `src/portal/src/components/training-jobs/job-actions.test.tsx` (and/or add a new test file for the approval form) for scenarios 25-28 (form opens, submit-disabled until valid, submits correct payload, surfaces backend validation errors). All 4 frontend suites run via `npx vitest run`: 46/46 pass.

## 9. Architecture Documentation

- [x] 9.1 Record a superseding ADR (new `docs/adr/00X-*.md` with `Supersedes: ADR-006`) documenting that training hyperparameters are now supplied by the System Admin at approval time rather than by the Tenant Admin at submission time; leave all other ADR-006 decisions (Celery/RabbitMQ, GPU autoscaling, checkpointing) intact and referenced as still in force. Recorded as `docs/adr/009-system-admin-sets-training-hyperparameters.md`.

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. Backend: 15/16 (1 pre-existing, unrelated failure). Frontend: 80/80.
- [x] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 10.6 Run `openspec validate system-admin-sets-training-params --type change --strict` and confirm it exits clean before archive. Output: "Change 'system-admin-sets-training-params' is valid".
