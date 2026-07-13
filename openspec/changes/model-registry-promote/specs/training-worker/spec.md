# Training Worker — Delta

**Base spec**: `openspec/specs/training-worker/spec.md`

## Changes

### 1. `model_versions` row must reflect actual job outcome

#### Current spec (Requirement: Save model artifacts, Scenario: Artifacts are stored after training)

> "the `model_versions` table SHALL have a new row with `version_number`, `status`: `"completed"`, and `artifact_path`"

This is changed to reflect the corrected lifecycle — the row is created with `status='training'` before the job fully completes, and updated to `'completed'` only after `_update_job_progress` succeeds.

#### Updated scenario

- **GIVEN** a completed training run
- **WHEN** the worker saves the model and tokenizer
- **THEN** `model.safetensors`, `config.json`, `tokenizer.json`, `vocab.txt`, `training_args.json`, and `metrics.json` SHALL exist at the artifact path
- **AND** the `model_versions` table SHALL have a new row with `version_number`, `status`: `"training"`, and `artifact_path`
- **AND** after job progress is persisted, `model_versions.status` SHALL be `"completed"`

### 2. New scenario: Failed job sets model_versions to failed

- **GIVEN** a training run where artifacts were saved and a `model_versions` row was created with `status='training'`
- **WHEN** `_update_job_progress` or `mlflow.end_run` fails
- **THEN** the worker exception handler SHALL update `model_versions.status` to `"failed"`
- **AND** `training_jobs.status` SHALL be `"failed"`
- **AND** the MLflow run status SHALL be `FAILED`

### 3. `_update_job_progress` must accept dict-type metrics

#### Current spec (Requirement: Update job progress during training)

The `_update_job_progress` function accepts `**fields` but crashes when a dict value is passed because psycopg2 cannot adapt Python dicts directly.

#### Updated requirement

`_update_job_progress` SHALL JSON-serialize any Python dict values in `**fields` before passing them to the SQL UPDATE statement. This prevents `psycopg2.ProgrammingError: can't adapt type 'dict'` when `metrics` or similar nested fields are passed.
