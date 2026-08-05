# Verification Plan

**Change:** system-admin-sets-training-params
**Generated:** 2026-08-05
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-jobs | Submit training job | Submit a valid training job | Given a tenant with ≥500 annotated entities, when a Tenant Admin POSTs a hyperparameter-free body to `/api/v1/training-jobs`, then a 201 is returned with `status: "pending_approval"`, `hyperparams: null`, no `celery_task_id`, and no Celery task enqueued | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 2 | training-jobs | Submit training job | Submit training job with insufficient entities | Given a tenant with <500 annotated entities, when a Tenant Admin POSTs to `/api/v1/training-jobs`, then a 422 is returned indicating the entity threshold is not met | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 3 | training-jobs | Submit training job | Submit training job as non-admin | Given an annotator, when they POST to `/api/v1/training-jobs`, then a 403 is returned | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 4 | training-jobs | Submit training job | Submit training job body with hyperparameters is ignored or rejected | Given a tenant with sufficient entities, when a Tenant Admin POSTs a body containing hyperparameter fields, then either the fields are ignored (201, `hyperparams: null`) or the request is rejected (422) — but `hyperparams` is never populated from this request | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 5 | training-jobs | Approve training job | Approve a pending training job with valid hyperparameters | Given a `pending_approval` job with `hyperparams: null`, when a System Admin POSTs valid hyperparameters to `/api/v1/training-jobs/{job_id}/approve`, then a 200 is returned with `status: "queued"`, `hyperparams` matching the submitted values, and a Celery task enqueued using those values | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 6 | training-jobs | Approve training job | Approve without supplying hyperparameters | Given a `pending_approval` job, when a System Admin POSTs an empty body to approve, then a 422 is returned indicating hyperparameters are required | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 7 | training-jobs | Approve training job | Approve with invalid hyperparameters | Given a `pending_approval` job, when a System Admin POSTs `{"num_epochs": -1}` to approve, then a 422 is returned describing the invalid parameter and the job remains `pending_approval` with `hyperparams` unchanged | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 8 | training-jobs | Approve training job | Approve a job that is not pending_approval | Given a `queued` job, when a System Admin POSTs valid hyperparameters to approve, then a 422 is returned indicating the job cannot be approved in its current state | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 9 | training-jobs | Approve training job | Approve as non-system-admin | Given a `pending_approval` job, when a Tenant Admin POSTs valid hyperparameters to approve, then a 403 is returned | tests/test_training_jobs_api.py (task 4.1) | - [ ] |
| 10 | training-jobs | Submit form span preflight is informational only | Submit enabled with span count below the legacy 500 threshold | Given a tenant with <500 confirmed spans, when the Tenant Admin opens the submit form, then the Submit button is enabled and the preflight display shows the span count with no pass/fail language | src/portal/src/components/training-jobs/submit-job-slideover.test.tsx (task 8.1) | - [ ] |
| 11 | training-jobs | Submit form span preflight is informational only | Preflight display shows span count while loading and on fetch failure | Given the submit form is open, when the span count request is in flight, then a loading state is shown; when it fails, an "unavailable" state is shown; in neither case is the Submit button's enabled state affected | src/portal/src/components/training-jobs/submit-job-slideover.test.tsx (task 8.1) | - [ ] |
| 12 | training-jobs | Submit form span preflight is informational only | Backend rejection for insufficient entities is surfaced after submit | Given a tenant below the backend's minimum, when the Tenant Admin submits and the backend returns 422, then the form displays the backend's error message and remains open | src/portal/src/components/training-jobs/submit-job-slideover.test.tsx (task 8.1) | - [ ] |
| 13 | training-approval | Approve training job | Approve a pending training job with valid hyperparameters | Given a `pending_approval` job with `hyperparams: null`, when a System Admin POSTs valid hyperparameters to approve, then a 200 is returned with `status: "queued"`, matching `hyperparams`, and a Celery task enqueued using those values | tests/test_training_jobs_api.py (task 4.1, shared with row 5) | - [ ] |
| 14 | training-approval | Approve training job | Approve without supplying hyperparameters | Given a `pending_approval` job, when a System Admin POSTs an empty body to approve, then a 422 is returned indicating hyperparameters are required | tests/test_training_jobs_api.py (task 4.1, shared with row 6) | - [ ] |
| 15 | training-approval | Approve training job | Approve with invalid hyperparameters | Given a `pending_approval` job, when a System Admin POSTs `{"num_epochs": -1}` to approve, then a 422 is returned describing the invalid parameter and the job remains `pending_approval` with `hyperparams` unchanged | tests/test_training_jobs_api.py (task 4.1, shared with row 7) | - [ ] |
| 16 | training-approval | Approve training job | Approve a job that is not pending_approval | Given a `queued` job, when a System Admin POSTs valid hyperparameters to approve, then a 422 is returned indicating the job cannot be approved in its current state | tests/test_training_jobs_api.py (task 4.1, shared with row 8) | - [ ] |
| 17 | training-approval | Approve training job | Approve as non-system-admin | Given a `pending_approval` job, when a Tenant Admin POSTs valid hyperparameters to approve, then a 403 is returned | tests/test_training_jobs_api.py (task 4.1, shared with row 9) | - [ ] |
| 18 | training-jobs-screen | Submit slide-over visual parity without behavior change | Slide-over still performs span preflight check, with no hyperparameter fields | Given a Tenant Admin opens the submit slide-over, when it mounts, then the span-count preflight still fetches/displays and no learning-rate, epoch, batch-size, or max-sequence-length input is rendered; Submit is enabled based only on in-flight state | src/portal/src/components/training-jobs/submit-job-slideover.test.tsx (task 8.1) | - [ ] |
| 19 | training-jobs-screen | Job list card content | Running job card shows full summary | Given a running job with hyperparams and no metrics, when its `JobCard` renders, then the job ID, a pulsing dot, hyperparameter summary line "lr 0.00002 · 3ep · bs 8", and F1 "—" are shown | src/portal/src/components/training-jobs/job-card.test.tsx (task 8.2) | - [ ] |
| 20 | training-jobs-screen | Job list card content | Completed job card shows F1 score | Given a completed job with `metrics.eval_f1: 0.90`, when its `JobCard` renders, then "0.90" is shown and the dot does not pulse | src/portal/src/components/training-jobs/job-card.test.tsx (task 8.2) | - [ ] |
| 21 | training-jobs-screen | Job list card content | Non-running job still shows a status-colored dot | Given a `pending_approval` job, when its `JobCard` renders, then a non-pulsing dot colored per that status is shown | src/portal/src/components/training-jobs/job-card.test.tsx (task 8.2) | - [ ] |
| 22 | training-jobs-screen | Job list card content | Pending-approval job with no hyperparameters yet shows a placeholder, not undefined | Given a `pending_approval` job with `hyperparams: null`, when its `JobCard` renders, then "awaiting hyperparameters" (or equivalent) is shown instead of a summary line, with no literal "undefined"/"null" text | src/portal/src/components/training-jobs/job-card.test.tsx (task 8.2) | - [ ] |
| 23 | training-jobs-screen | Hyperparameters render as a single 4-column row | Hyperparameters grid has 4 columns | Given a job with hyperparams set, when the detail panel renders the hyperparameters section, then its grid has 4 columns | src/portal/src/components/training-jobs/job-detail-panel.test.tsx (task 8.3) | - [ ] |
| 24 | training-jobs-screen | Hyperparameters render as a single 4-column row | Detail panel shows a placeholder when hyperparameters are not yet set | Given a `pending_approval` job with `hyperparams: null`, when the detail panel renders the hyperparameters section, then a placeholder message is shown instead of four empty/undefined values | src/portal/src/components/training-jobs/job-detail-panel.test.tsx (task 8.3) | - [ ] |
| 25 | training-jobs-screen | System Admin approval form collects hyperparameters | Approve action opens a hyperparameter form | Given a System Admin views a `pending_approval` job, when they click approve, then a form with the four hyperparameter inputs appears and no approval happens yet | src/portal/src/components/training-jobs/job-actions.test.tsx (task 8.4) | - [ ] |
| 26 | training-jobs-screen | System Admin approval form collects hyperparameters | Approve submit is disabled until all fields are valid | Given the approval form is open, when any of the four fields is empty or out of range, then the submit control is disabled | src/portal/src/components/training-jobs/job-actions.test.tsx (task 8.4) | - [ ] |
| 27 | training-jobs-screen | System Admin approval form collects hyperparameters | Approve form submits entered hyperparameters | Given all four fields are valid, when the System Admin submits, then those exact values are POSTed to `/api/v1/training-jobs/{job_id}/approve` and on success the UI reflects `status: "queued"` and the new `hyperparams` | src/portal/src/components/training-jobs/job-actions.test.tsx (task 8.4) | - [ ] |
| 28 | training-jobs-screen | System Admin approval form collects hyperparameters | Backend validation error is surfaced on the approval form | Given the System Admin submits the form, when the backend returns a 422, then the form displays the error and remains open with entered values intact | src/portal/src/components/training-jobs/job-actions.test.tsx (task 8.4) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `hyperparams` nullability (Decision 2) | AI may forget to make the DB column nullable, causing submission inserts to fail with a NOT NULL constraint violation, or may silently default to `{}` instead of `null` | Confirm a new alembic migration relaxes `tenant_template.training_jobs.hyperparams` to nullable, and confirm submission actually persists `null` (not `{}`) by inspecting the created row |
| 2 | Schema split (Decision 1) | AI may leave hyperparameter fields on `TrainingJobCreate` "just in case" instead of fully removing them, or may forget to add the same validation bounds (`num_epochs` 1-50, `max_seq_length` 32-512) to the new `ApproveJobRequest` | Diff `TrainingJobCreate` and the new `ApproveJobRequest` against schemas.py — confirm hyperparameter fields exist only on the approve schema, with matching bounds to the old `TrainingJobCreate` |
| 3 | Approve endpoint atomicity (Decision 3) | AI may persist `hyperparams` and enqueue Celery as two separate, non-atomic steps, risking a job stuck "queued" with no dispatched task if the process fails between them | Review the approve endpoint implementation for a single transaction/consistent ordering (persist then enqueue, or enqueue then persist with a compensating check) and confirm no intermediate state leaks to the API response |
| 4 | Old in-flight jobs (Non-Goals) | AI may write a migration/backfill script for pre-existing `pending_approval` jobs that already carry tenant-supplied `hyperparams`, contradicting the explicit Non-Goal of no backfill | Confirm no data migration/backfill script was added for existing `hyperparams` values; confirm the approve endpoint's new required body works for old and new `pending_approval` jobs alike without special-casing |
| 5 | Frontend null-handling (training-jobs-screen deltas) | AI may render `undefined`/`NaN` in the job card hyperparameter summary or the detail panel's 4-column grid when `hyperparams` is `null`, instead of the specified placeholder text | Manually load a freshly-submitted (un-approved) job in the UI and visually confirm the card and detail panel show placeholder text, not blank/undefined values |
| 6 | Removed client-side validation (Risk 2 in design.md) | AI may leave stale hyperparameter-validation logic in `SubmitJobSlideover` (e.g. disabled-button logic still referencing removed fields) after deleting the input elements, causing the Submit button to be permanently disabled | Grep `submit-job-slideover.tsx` for any remaining references to `learning_rate`, `num_epochs`, `batch_size`, `max_seq_length` after the edit — none should remain |
| 7 | ADR-006 supersession (Open Question) | AI may implement the code change without recording a superseding ADR for ADR-006's now-inaccurate "hyperparameters submitted with the job request" clause, leaving architecture docs inconsistent with the shipped behavior | Confirm a new ADR (or an amendment via supersession) exists in `docs/adr/` that documents hyperparameters now being set by the System Admin at approval time |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|--------------------------|-------------------|
| ADR-002-base-model-strategy | All fine-tuning starts from `dslim/bert-base-NER` | Unaffected — must confirm no base-model field was accidentally touched | Confirmed: `git diff` shows no changes to `worker.py`'s base-model reference or `job-detail-panel.tsx`'s `dslim/bert-base-NER` lineage sublabel |
| ADR-006-training-infrastructure | Celery + RabbitMQ async GPU workers; hyperparameters previously "submitted with the job request" | The queueing/autoscaling/checkpointing pipeline must remain unaffected; the hyperparameter-submission clause is intentionally superseded by this change | Confirmed: `celery_app.send_task("fine_tune_model", ...)` call site unchanged in mechanism (only the source of the `hyperparams` dict changed, from `row.get("hyperparams")` to the validated request body); `docs/adr/009-system-admin-sets-training-hyperparameters.md` records the supersession |
| ADR-008-base-model-as-default | Base-model-as-default behavior for jobs without a model override | Unaffected — no model-selection field is touched | Confirmed: `git diff` shows no changes to any model-selection/model-serving code path |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (Submit a valid training job): API test output showing 201, `hyperparams: null`, `status: "pending_approval"`, no Celery enqueue — `test_submit_valid_job_returns_run_number_and_run_name` passes
- [x] Scenario 2 (Submit with insufficient entities): API test output showing 422 with entity-threshold error — `test_submit_insufficient_entities_422` passes
- [x] Scenario 3 (Submit as non-admin): API test output showing 403 — `test_submit_as_non_admin_403` passes
- [x] Scenario 4 (Submit body with hyperparameters ignored/rejected): API test output confirming `hyperparams` is never populated from the submit body — `test_submit_with_hyperparameters_is_ignored_or_rejected` passes (422, extra fields forbidden)
- [x] Scenario 5 (Approve with valid hyperparameters): API test output showing 200, `status: "queued"`, matching `hyperparams`, and Celery enqueue call with those values — `test_approve_pending_job_with_valid_hyperparameters` passes
- [x] Scenario 6 (Approve without hyperparameters): API test output showing 422 — `test_approve_without_hyperparameters_422` passes
- [x] Scenario 7 (Approve with invalid hyperparameters): API test output showing 422 and unchanged job state — `test_approve_with_invalid_hyperparameters_422` passes
- [x] Scenario 8 (Approve a non-pending job): API test output showing 422 — `test_approve_job_not_pending_approval_422` passes
- [x] Scenario 9 (Approve as non-system-admin): API test output showing 403 — `test_approve_as_non_system_admin_403` passes
- [x] Scenario 10 (Submit enabled below legacy threshold): UI test — `submit-job-slideover.test.tsx > enables submit with span count below 500` passes
- [x] Scenario 11 (Preflight loading/failure states): UI test — `shows preflight check with span count` / `keeps submit enabled when span count fetch fails` pass
- [x] Scenario 12 (Backend rejection surfaced): UI test — `surfaces server error and keeps form open on 422 insufficient entities` passes
- [x] Scenarios 13-17 (training-approval capability, duplicate of 5-9): same `test_training_jobs_api.py` approve tests cover this identical code path
- [x] Scenario 18 (Slide-over no hyperparameter fields): UI test — `renders no hyperparameter inputs and submits a hyperparameter-free body` passes
- [x] Scenario 19 (Running job card summary): UI test — `job-card.test.tsx > shows run name, hyperparameter line, and F1 '—'...` passes
- [x] Scenario 20 (Completed job card F1): UI test — `shows F1 score to two decimal places...` passes
- [x] Scenario 21 (Non-running dot, no pulse): UI test — `shows a status-colored dot even when the job is not running` passes
- [x] Scenario 22 (Pending-approval placeholder, no "undefined"): UI test — `shows a placeholder instead of undefined/null when hyperparams is null` passes
- [x] Scenario 23 (4-column grid): UI test — `renders the hyperparameters grid as a single 4-column row` passes
- [x] Scenario 24 (Detail panel placeholder for null hyperparams): UI test — `shows a placeholder instead of an empty grid when hyperparams is null` passes
- [x] Scenario 25 (Approve form opens): UI test — `opens a hyperparameter form when Approve is clicked...` passes
- [x] Scenario 26 (Approve submit disabled until valid): UI test — `disables the approve form submit until all fields are valid` passes
- [x] Scenario 27 (Approve form submits values): UI test — `submits the entered hyperparameters to the approve endpoint` passes
- [x] Scenario 28 (Backend validation error surfaced on approval form): UI test — `surfaces a backend validation error on the approve form and keeps it open` passes

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations) — schema split (Decision 1), nullable `hyperparams` (Decision 2), single-UPDATE approve (Decision 3) all implemented as designed
- [x] All ADR compliance steps in Section 3 confirmed ✓ (see below)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — migration `031_training_jobs_hyperparams_nullable.py` applied via `docker compose run --rm db-init` (alembic `030 -> 031`); submission persists `hyperparams: null` (verified by `test_submit_valid_job_returns_run_number_and_run_name`)
- [x] Risk 2 mitigation confirmed — `TrainingJobCreate` (schemas.py) has no hyperparameter fields; `ApproveJobRequest` carries the same bounds the old `TrainingJobCreate` had (`gt=0`, `1-50`, `ge=1`, `32-512`)
- [x] Risk 3 mitigation confirmed — `TrainingJobRepository.approve()` writes `status`, `hyperparams`, and `celery_task_id` in a single UPDATE statement; Celery `send_task` is called before the DB write so a crash after enqueue-but-before-persist is the only inconsistent window, matching design.md's accepted trade-off
- [x] Risk 4 mitigation confirmed — no backfill/data migration script was added; migration 031 only relaxes the column constraint
- [x] Risk 5 mitigation confirmed — `job-card.tsx` renders "awaiting hyperparameters"; `job-detail-panel.tsx` renders "Hyperparameters not yet set — awaiting System Admin approval" instead of undefined/blank values (both covered by UI tests)
- [x] Risk 6 mitigation confirmed — `submit-job-slideover.tsx` was fully rewritten with no remaining references to `learning_rate`/`num_epochs`/`batch_size`/`max_seq_length`
- [x] Risk 7 mitigation confirmed — `docs/adr/009-system-admin-sets-training-hyperparameters.md` records the supersession of ADR-006's hyperparameter-submission clause

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `poetry run pytest tests/test_training_jobs_api.py -q` — 15/16 passed (1 pre-existing, unrelated failure: `test_system_admin_get_job_with_wrong_tenant_id_404`) | Scenarios 1-9, 13-17 | AI (Claude) | 2026-08-05 |
| 2 | Functional | `npx vitest run` on `src/portal/src/components/training-jobs/*` and `src/portal/src/hooks/use-{submit,approve}-training-job.test.tsx` — 80/80 passed | Scenarios 10-12, 18-28 | AI (Claude) | 2026-08-05 |
| 3 | Structural | `docker compose run --rm db-init` output — alembic `Running upgrade 030 -> 031, relax training_jobs.hyperparams to nullable`, seed + schema verification passed | Risk 1 (Section 2), Migration Plan step 1 | AI (Claude) | 2026-08-05 |
| 4 | Structural | `npx tsc --noEmit` in `src/portal` — no new type errors introduced by this change (one pre-existing, unrelated error remains in `job-list.test.tsx`) | Structural Evidence | AI (Claude) | 2026-08-05 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** system-admin-sets-training-params
**Proposal:** `openspec/changes/system-admin-sets-training-params/proposal.md`
**Spec files reviewed:**
- specs/training-jobs/spec.md
- specs/training-approval/spec.md
- specs/training-jobs-screen/spec.md

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
