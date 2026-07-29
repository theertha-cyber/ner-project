## Context

Today the Model Registry (`/models`) shows the synthetic base model (ADR-008, version 0, `dslim/bert-base-NER`) as a peer card to every role — the frontend synthesizes it client-side (`ModelRegistryPage.tsx: buildBaseModelEntry()`) with no role check, and the page itself has no `RequireAuth` guard. Model versions are named `v{version_number}`, where `version_number` is a per-tenant sequential integer assigned at **training completion** (`worker.py: MAX(version_number)+1 FROM model_versions WHERE tenant_id = ...`). Training jobs are identified only by a UUID (`job_id = str(uuid.uuid4())`), with no visible link to the version number their completion will eventually produce. Extraction (Playground / Batch Runs) silently uses the base model when no fine-tuned model is promoted — this is the existing, correct fallback behavior (ADR-008) and stays unchanged; only a user-facing confirmation gate is added in front of it.

Constraints:
- The base model has no DB row (ADR-008: "Version 0 is synthetic"), so any run-naming scheme must special-case it (it never gets a `run-NNN-YYYYMMDD` name).
- `version_number` is used today as the join key between `ModelVersion` and MLflow stage transitions (`STAGE_TO_STATUS`) and as the artifact path segment (`tenants/{tenant_id}/models/v{version_number}/`) — changing its type or semantics has broad blast radius, so we keep the numeric column and add a display-name concept alongside it rather than replacing it.
- Training job submission and model version creation are two different lifecycle events, separated by an async Celery pipeline (ADR-006) — a run number assigned at submission must survive job failure/cancellation/rejection without collision.

## Goals / Non-Goals

**Goals:**
- Base model card invisible to `tenant_admin` / `business_user` / `annotator` on `/models`, visible to `system_admin`.
- A confirmation dialog gates extraction runs (Playground, Batch Runs) whenever the tenant's active model is the base model.
- Model versions and their originating training jobs share one human-readable run identifier: `run-{NNN}-{YYYYMMDD}`.
- Existing promotion/fallback mechanism (ADR-008) is behaviorally unchanged for API consumers other than the confirmation gate.

**Non-Goals:**
- Not changing the extraction fallback logic itself (`model_serving/services/inference_service.py`) — no code changes there; the gate lives entirely in the portal frontend, before the API call is made.
- Not adding a system-admin toggle to reveal/hide the base model — visibility is purely role-derived.
- Not migrating existing `version_number`-keyed artifact paths or MLflow registered-model names — those remain numeric internally; only the **display name** changes.
- Not backfilling `run_number` for historical training jobs/model versions created before this change (see Migration Plan).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|----------------------------|
| ADR-001-tenant-data-isolation | Per-tenant schema isolation | `run_number` sequence must be computed/scoped per-tenant schema, consistent with existing `version_number` scoping |
| ADR-002-base-model-strategy (partially superseded by ADR-008) | Single curated base model, all training jobs reference `dslim/bert-base-NER` | Run-name scheme doesn't touch base-model selection; only naming/visibility |
| ADR-003-model-serving-topology | Per-tenant model serving | No change needed; confirmation dialog is purely a portal-side gate before calling `/api/v1/extract` |
| ADR-006-training-infrastructure | Async Celery/RabbitMQ training pipeline; artifacts at `tenant-<uuid>/models/v<version>/` | Run number must be assignable at submission time (before the async job even starts), and artifact paths keep the existing `v{version_number}` internal form — only the display name changes |
| ADR-008-base-model-as-default | Base model = synthetic version 0, no DB row, shared singleton | Base model keeps a static "Base Model" label, never a `run-NNN-YYYYMMDD` name; confirmation dialog fires exactly when resolution lands on version 0 |

## Decisions

### Decision 1: Assign `run_number` at training-job submission time, reuse it at model-version creation

**Choice:** Add a `run_number INTEGER` column to `training_jobs`, assigned inside the same transaction as job creation via `SELECT COALESCE(MAX(run_number), 0) + 1 FROM training_jobs WHERE tenant_id = :tenant_id FOR UPDATE`. When `worker.py` completes training and creates the `ModelVersion` row, it copies `training_job.run_number` into a new `model_versions.run_number` column instead of independently computing `MAX(version_number)+1` for naming purposes (the numeric `version_number` column is still computed and kept for MLflow/artifact-path compatibility, per Non-Goals).

**Rationale:** The request requires Training Jobs and Model Registry to show the *same* run number for a given pipeline run, and a training job is visible (and needs a stable label) long before its model version exists. Assigning at submission is the only point where both entities can agree on one number without the frontend guessing an unassigned job's future version number.

**Alternatives considered:**
- Assign at completion only (mirrors today's `version_number` logic), backfilling the job afterward — rejected: a `pending_approval`/`queued`/`running` job would show no run number for its entire pre-completion lifetime, which is most of a training job's visible existence in the Training Jobs screen.
- Reuse `version_number` directly as the run number (skip the new column) — rejected: `version_number` is only assigned at completion and is tied to MLflow versioning semantics (must remain a plain sequential int for `STAGE_TO_STATUS` bookkeeping); overloading it as a submission-time reservation risks colliding with MLflow's own version numbering if a job is cancelled after reservation but MLflow assigns numbers independently.

### Decision 2: Run number is a per-tenant monotonic counter that is never reused, even on cancel/reject/fail

**Choice:** `run_number` comes from `MAX(run_number)+1` scoped to the tenant's schema and is permanently consumed once assigned, regardless of the job's eventual outcome.

**Rationale:** Guarantees `run-NNN-YYYYMMDD` uniquely identifies one pipeline attempt forever — critical since these names may be communicated externally (per the request's "generated by your pipeline" framing) and reused as MLflow/model-registry names. Reusing a retired number after a cancelled job would let two different artifacts collide on the same run name.

**Alternatives considered:**
- Reclaim/reuse numbers from cancelled jobs — rejected: cheap to implement but breaks the "one name, one artifact" invariant and complicates concurrent submission handling (two admins racing to reuse the same reclaimed number).

### Decision 3: Display name is computed as `run-{run_number:03d}-{created_at:%Y%m%d}`, not stored as a string column

**Choice:** Store only the integer `run_number` (plus the existing `created_at` timestamp); compute the `run-NNN-YYYYMMDD` string in the API serializer (`_row_to_response` in both `models.py` and `training_jobs.py`) and expose it as a new `run_name` field. Frontend renders `run_name` directly instead of `` `v${version_number}` `` / raw UUID.

**Rationale:** Avoids storing a derived/denormalized string that could drift from `run_number`/`created_at`; keeps the date component naturally tied to submission date (a training job's `created_at`), which is set once and immutable.

**Alternatives considered:**
- Persist `run_name` as a generated column at insert time — rejected: no benefit over computing at serialization time for two integer/timestamp columns, adds migration complexity (would need backfill logic for the date format).

### Decision 4: Base model keeps a static label with no run number; frontend gates rendering by `version_number === 0` and role

**Choice:** `_base_model_metadata()` in `models.py` continues to return no `run_number`/`run_name` (both `null`); frontend `ModelVersionCard` renders "Base Model" when `version_number === 0`, unchanged from today. `ModelRegistryPage.tsx` additionally reads the authenticated user's role (already available via the existing auth context used elsewhere, e.g. `training-jobs/page.tsx`'s `user?.role`) and skips calling `buildBaseModelEntry()` / appending it to the list unless `role === "system_admin"`.

**Rationale:** Matches ADR-008's "version 0 is synthetic, no DB row" — a run number implies a pipeline run produced it, which is false for the base model. Role gating purely in the list-assembly step (rather than a route-level `RequireAuth`) preserves the existing behavior that all authenticated roles can still view `/models` and see their *real* trained models — only the base-model card is conditionally omitted.

**Alternatives considered:**
- Route-level `RequireAuth roles={[...]}` on `/models` — rejected: would block tenant_admin/business_user/annotator from the whole page, not just the base-model card, which is broader than requested ("the default base model shouldn't be visible to them" — the page itself must remain visible).
- Hide base model server-side (omit it from the API response for non-system_admin) — rejected: proposal explicitly scopes this as a frontend change, and `/api/v1/models/active` (used for the extraction fallback confirmation, Decision 5) must still return base-model metadata to every role so the portal can detect "active model is base" regardless of who's logged in.

### Decision 5: Extraction confirmation dialog checks `GET /api/v1/models/active` client-side before submitting the run

**Choice:** Before Playground "Run extraction" or Batch Runs "New batch run" calls `/api/v1/extract` / `/api/v1/extract-batch`, the portal reads the already-fetched (or freshly-fetched) active model (`useModelVersions()`'s existing `activeModel` query). If `activeModel.version_number === 0`, render a confirmation dialog ("A fine-tuned model isn't available yet. Use the base model for this run?") before proceeding. Confirm → call the extraction endpoint as today. Cancel → no API call, no run created.

**Rationale:** Reuses the existing `/api/v1/models/active` query already wired into the Model Registry hook (`use-model-versions.ts`) — no new backend endpoint needed. Keeps the actual fallback decision (ADR-008) server-side and untouched; the dialog is purely an opt-in confirmation gate client-side, so declining simply means "don't send the request," not "the server behaves differently."

**Alternatives considered:**
- Have the extraction API itself reject with a 409/422 when resolving to base model, requiring an explicit `?allow_base=true` override — rejected: proposal says "keep" the current promotion/fallback mechanism as-is; changing the API contract for extraction risks breaking the Playground/Batch-Runs' existing straightforward POST flow and any other API consumers (e.g. the widget/embeddable extraction path) that should NOT be gated by this portal-only UX decision.

## Risks / Trade-offs

- [Race: two training jobs submitted concurrently for the same tenant could compute the same `MAX(run_number)+1` under weak isolation] → Use `SELECT ... FOR UPDATE` (or an equivalent row-lock / `SERIALIZABLE` transaction) on the tenant's `training_jobs` table when assigning `run_number`, mirroring whatever locking (if any) protects today's `version_number` assignment in `worker.py`.
- [Existing historical training jobs/model versions have no `run_number`] → See Migration Plan: nullable column, frontend falls back to short-UUID / `v{version_number}` display for rows where `run_number IS NULL`.
- [Confirmation dialog adds a client-side check that could go stale between the check and the actual extraction call if a fine-tuned model is promoted in the intervening seconds] → Acceptable: worst case a user is asked to confirm base-model usage for a run that would've actually used the just-promoted model; harmless since the extraction API resolves the model version itself at request time regardless of what the dialog assumed.
- [Two services (`training_service` for jobs/models, `model_serving` for inference) both need a consistent notion of "is this the base model"] → No new coupling introduced; `model_serving` is unchanged (Non-Goals), only `training_service`'s API responses and the portal gain the `run_name`/role-gating logic.

## Migration Plan

1. DB migration: add nullable `run_number INTEGER` to `training_jobs` and `model_versions` (per-tenant schema, applied via the existing tenant-schema migration mechanism — see `tenant-schema-migrations` capability). Nullable so existing rows are unaffected (no backfill required, per proposal's Open Questions/Non-Goals).
2. Backend: `training_jobs.py` submission handler assigns `run_number` for new jobs only; `worker.py` copies `training_job.run_number` onto the created `ModelVersion` instead of computing a naming value independently (it still computes `version_number` for MLflow/artifact-path purposes, unchanged).
3. Backend: `models.py` and `training_jobs.py` serializers add a `run_name` field, `null` when `run_number IS NULL` (legacy rows) or the row is the synthetic base model.
4. Frontend: Model Registry — role-gate the base-model card; render `run_name` when present, else fall back to `v{version_number}` (model versions) or a short UUID (training jobs) for legacy rows.
5. Frontend: Training Jobs screen — render `run_name` in job cards, detail header, and the lineage diagram's MODEL VERSION box (replacing `v{version_number}`), with the same legacy fallback.
6. Frontend: Extraction page — add the confirmation dialog component, wire it in front of both "Run extraction" and "New batch run" handlers.
7. Rollback: all changes are additive (nullable columns, new response fields, new frontend conditionals) — reverting the frontend deploy alone fully restores prior behavior even if the DB migration has already run; reverting the DB migration is a plain `DROP COLUMN` with no data-loss risk since no other column depends on `run_number`.

## Open Questions

- Exact row-locking strategy for concurrent `run_number` assignment (see Risks) — left to implementation to match whatever pattern (if any) currently guards `version_number` assignment in `worker.py`; if none exists today, this change should introduce one rather than replicate an unguarded read-modify-write.
- Whether `run_name` should also appear in MLflow's registered-model version description/tags (for traceability inside the MLflow UI itself) — out of scope for this change; MLflow-facing naming (`_registered_model_name`) is untouched.
