## Why

The synthetic base model (`dslim/bert-base-NER`, version 0, ADR-008) is a fallback safety net, but the Model Registry screen currently shows it to every role as a peer entry alongside real fine-tuned models — tenant admins have no way to tell "our trained model" apart from "the platform default" at a glance, and can be confused into thinking it's a trained artifact. Separately, extraction runs silently fall back to the base model with no user signal, so a tenant admin may not realize their results came from an untuned generic model. Finally, model versions are named `v1`, `v2`, ... with no date context and no link to the training job that produced them, and Training Jobs are identified only by raw UUID — making it hard to correlate a run across the two screens or communicate about a specific run externally.

## What Changes

- Hide the base model (version 0) card from the Model Registry screen (`/models`) for `tenant_admin`, `business_user`, and `annotator` roles. `system_admin` continues to see it. **Frontend-only** — the backend already marks it via `version_number: 0` / `X-Model-Source: base`; no API contract change.
- Keep the existing model-promotion fallback mechanism for extraction unchanged (promoted model wins; else base model serves inference) — **BUT** gate it behind a client-side confirmation: when a `business_user` triggers an extraction run (Playground "Run extraction" or Batch Runs "New batch run") and the tenant's active model resolves to version 0 (no promoted fine-tuned model), show a confirmation dialog: "A fine-tuned model isn't available yet. Use the base model for this run?" Confirming proceeds with the existing base-model fallback; declining cancels the run (no API call is sent).
- Replace the `v{N}` model naming scheme with a chronological run-based scheme: `run-{sequentialNumber:03d}-{YYYYMMDD}` (e.g. `run-001-20260729`). The sequential number is assigned once per training job at submission time (not at completion), so it is stable and known immediately.
- Training Jobs screen (`/training-jobs`) displays the same run number (`run-001-20260729`) for each job — synchronized with the model version name the job eventually produces, replacing (or supplementing, for jobs that fail/haven't completed) the raw-UUID-only display.
- **BREAKING**: `ModelVersion`/`TrainingJob` API responses gain a `run_name` (or equivalently `run_number` + `created_at`-derived date) field; existing `v{N}` display strings in the frontend are removed. The base model (version 0) keeps a static, non-run label ("Base Model") since it is not produced by a run.

## Capabilities

### New Capabilities

(none — this extends existing capabilities)

### Modified Capabilities

- `model-registry-screen`: base model card visibility becomes role-gated (hidden for tenant_admin/business_user/annotator, visible for system_admin); model version cards display the `run-NNN-YYYYMMDD` name instead of `vN`.
- `model-registry`: model versions carry a run number assigned at the owning training job's submission time (not completion); API responses expose the run-based name.
- `training-jobs`: training job creation assigns a per-tenant sequential run number at submission time; this number is later reused as the resulting model version's run number.
- `training-jobs-screen`: job cards/detail panel display the `run-NNN-YYYYMMDD` run name instead of (or alongside a shortened form of) the raw UUID; the lineage diagram's "MODEL VERSION" box uses the new run name instead of `v{version_number}`.
- `portal-extraction-page`: Playground "Run extraction" and Batch Runs "New batch run" actions check the tenant's active model version before submitting; if it resolves to the base model (version 0), a confirmation dialog is shown before proceeding, and declining cancels the run without calling the extraction API.

## Impact

- **Frontend**: `src/portal/src/components/model-registry/ModelRegistryPage.tsx`, `ModelVersionCard.tsx`, `src/portal/src/hooks/use-model-versions.ts`, `src/portal/src/components/training-jobs/*` (job-card, detail panel, lineage), `src/portal/src/components/extraction/*` (Playground run button, Batch Runs new-run button — new confirmation dialog component), `src/portal/src/types/model-registry.ts`, `src/portal/src/types/training-jobs.ts` (or equivalent).
- **Backend**: `src/training_service/api/v1/training_jobs.py` (assign run number on submit), `src/training_service/api/v1/models.py` (surface run name / run number on model version responses, base model metadata keeps static label), `src/training_service/worker.py` (reuse job's run number as the model version's run number instead of independently computing `MAX(version_number)+1`), `src/training_service/domain/training_job.py` and `domain/model_version.py` (new `run_number` column), a DB migration to add `run_number` to `training_jobs` and reuse/derive it on `model_versions`.
- **Docs**: ADR-008 language around "version 0" is unaffected (base model still synthetic); a note may be added clarifying the base model has no run number.

## Open Questions

- Should `run_number` be tenant-scoped (resets/continues per tenant, matching existing per-tenant `version_number` sequencing) or global across the whole platform? Assumption: **tenant-scoped**, consistent with today's per-tenant `version_number`.
- For a training job that is cancelled, rejected, or fails before producing a model version, does its reserved run number get reused by the next job, or permanently retired? Assumption: **retired** (monotonic per-tenant counter, never reused) to avoid two different artifacts ever sharing a run name.
- Does `system_admin` get an explicit toggle to view the base model, or is visibility purely role-derived with no UI control? Assumption: **purely role-derived** (no toggle) per the request's wording ("shouldn't be visible to them... visible... to the system admin").
