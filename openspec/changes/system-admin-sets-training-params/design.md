## Context

Today `TrainingJobCreate` (`src/training_service/api/v1/schemas.py:6-10`) carries `learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`. The Tenant Admin fills these in via `SubmitJobSlideover` and `POST /api/v1/training-jobs` stores them immediately in `hyperparams` at creation (`repository.py:14-30`), with status hardcoded `pending_approval`. Approval (`POST /api/v1/training-jobs/{job_id}/approve`, `training_jobs.py:226-259`) takes no body — it just flips status to `queued` and dispatches Celery with the tenant-chosen `hyperparams` unchanged (line 244).

This design moves hyperparameter authorship to the System Admin at the approval step, while keeping everything else (submission gate on entity count, reject flow, cancel flow, list/status endpoints, job lifecycle states) untouched.

## Goals / Non-Goals

**Goals:**

- Tenant Admin submission becomes a bare "please train" request — no hyperparameter fields, no client-side hyperparameter validation.
- System Admin approval requires supplying valid hyperparameters; the job is only enqueued once those are validated and persisted.
- `pending_approval` jobs created under this flow have `hyperparams: null` until approved.
- Existing tenant isolation, 403/422 semantics, and audit logging on submission are preserved.

**Non-Goals:**

- No change to reject, cancel, list, or status-lookup endpoints/specs.
- No new "suggested defaults" or per-tenant hyperparameter presets — out of scope, flagged as an open question.
- No backfill/migration of already-existing `pending_approval` jobs that already carry tenant-supplied `hyperparams` from before this change ships — they remain approvable as-is (the approve endpoint's new required body simply becomes the source of truth going forward; already-set values are not a state this design needs to reconcile since approval was not yet possible for them without this change).
- No change to the Celery task contract (`fine_tune_model` still receives a `hyperparams` dict) — only *who* fills that dict, and *when*, changes.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|--------------------------|
| ADR-002-base-model-strategy | All fine-tuning starts from `dslim/bert-base-NER`. | Unaffected — base model choice is not part of the hyperparameter set moved here. |
| ADR-006-training-infrastructure | Celery + RabbitMQ async GPU workers; **states hyperparameters are "submitted with the job request."** | This design directly changes that clause: hyperparameters are now submitted at *approval*, not at job-request time. The pipeline mechanics (queueing, autoscaling, checkpointing) are unaffected. Flagged in Open Questions for supersession. |
| ADR-008-base-model-as-default | Base-model-as-default behavior for jobs that don't specify a model override. | Unaffected — no model-selection field is touched by this change. |

## Decisions

### Decision 1: Where hyperparameter validation lives

**Choice:** Validation (bounds on `learning_rate`, `num_epochs` 1-50, `batch_size`, `max_seq_length` 32-512) moves from `TrainingJobCreate` to a new `ApproveJobRequest` pydantic model, reusing the exact same field constraints. `TrainingJobCreate` becomes an empty (or near-empty) body.

**Rationale:** Keeps a single, already-battle-tested set of bounds; only the schema attachment point moves. Avoids duplicating validation logic in two places.

**Alternatives considered:**
- Keep `TrainingJobCreate` fields but make them optional, and have the tenant's values act as a "suggestion" the System Admin can override: rejected — proposal explicitly wants Tenant Admin out of the hyperparameter business entirely, and an "optional suggestion" channel reintroduces exactly the ambiguity this change removes.

### Decision 2: `hyperparams` nullability

**Choice:** `TrainingJob.hyperparams` (JSON column) becomes nullable; a `pending_approval` job has `hyperparams: null` until approved. A migration is added to relax the column if it is currently `NOT NULL`.

**Rationale:** The domain state genuinely has no hyperparameters yet at submission time — modeling that as `null` is more honest than a sentinel/empty-dict value, and every consumer (job card, detail panel, worker) already has to branch on job status, so branching additionally on "hyperparams present" is a small, well-scoped addition.

**Alternatives considered:**
- Store an empty `{}` instead of `null`: rejected — `null` more clearly signals "not yet set" versus "set to a job with zero hyperparameters," and avoids frontend code accidentally rendering `lr undefined · undefinedep · bs undefined`.

### Decision 3: Approval is a single validated request, not a two-step "propose then confirm"

**Choice:** `POST /api/v1/training-jobs/{job_id}/approve` accepts the hyperparameter body directly and, in one transaction, validates → persists `hyperparams` → transitions status to `queued` → enqueues Celery. No separate "set params" endpoint before "confirm approval."

**Rationale:** Matches the existing single-call approve/reject pattern; avoids a new intermediate job status (e.g. `params_set`) that would ripple through the timeline UI, list filters, and cancel logic described in `training-jobs-screen` spec.

**Alternatives considered:**
- New intermediate status between `pending_approval` and `queued` for "params set, awaiting final confirm": rejected — adds a lifecycle state with no corresponding proposal requirement, and the `training-jobs-screen`'s `JobTimeline` component would need a new step across every scenario.

## Risks / Trade-offs

- [Existing `pending_approval` jobs created before this ships already have non-null tenant-supplied `hyperparams`; the new approve endpoint requires a body — a System Admin approving an old job must re-enter values even though some already exist] → Acceptable one-time friction given the training queue's low volume; the detail panel can display the old tenant-suggested values as a copyable reference (UI nicety, not a hard requirement of this change).
- [Removing client-side hyperparameter validation from the Tenant Admin submit form means all validation now happens at approve time, on the System Admin's side] → This is the intended shift of responsibility; System Admin's approval form reuses the same bounds so no validation coverage is lost, only relocated.
- [`fine_tune_model` Celery task signature is unchanged, but its caller (`approve` endpoint) now builds `hyperparams` from the approval request body instead of reading `row["hyperparams"]` from the stored job] → Low risk; it's a straightforward source-of-data swap at the same call site (`training_jobs.py:244`).

## Migration Plan

1. DB migration: relax `tenant_template.training_jobs.hyperparams` to nullable (new alembic revision alongside `005_training_service_tables.py` / `012_reconcile_training_jobs_columns.py`).
2. Backend: update `TrainingJobCreate` (drop hyperparameter fields), add `ApproveJobRequest`, update submit endpoint to store `hyperparams: null`, update approve endpoint to accept/validate/persist hyperparameters before enqueue.
3. Frontend: simplify `SubmitJobSlideover` to drop hyperparameter inputs (keep span-count preflight display); add hyperparameter inputs to the System Admin approve action (new dialog/form replacing the current one-click approve button); update job card / detail panel hyperparameter rendering to handle `null`.
4. Rollback: revert the four code changes and the migration (nullable→not-null is safe to reverse only if no null rows exist at rollback time — since this is a new-code-path column, rollback should happen before real `pending_approval` jobs accumulate null hyperparams, or the rollback migration must first backfill/reject such rows).

## Open Questions

- ADR-006-training-infrastructure's line "Training hyperparameters submitted with the job request" is now inaccurate; this design proposes a superseding ADR record the new split (Tenant Admin requests → System Admin sets params at approval) once this design is accepted.
- Should the System Admin's approval form pre-fill from the tenant's now-removed suggestion, for already-in-flight jobs created under the old flow? Left to implementation discretion — not a hard requirement.
- Should there be a per-tenant or global default hyperparameter preset the System Admin can select from, to reduce repetitive manual entry? Deferred — out of scope for this change per Non-Goals.
