## MODIFIED Requirements

### Requirement: List model versions

The system SHALL list all model versions for a tenant, ordered by version number descending, with status (training/completed/promoted/archived), creation date, training job reference, MLflow run URL, and a `run_name` field. `run_name` SHALL be computed as `run-{run_number:03d}-{created_at:%Y%m%d}` when the underlying training job has a `run_number` assigned, and SHALL be `null` for model versions created before run-number tracking existed (legacy rows).

#### Scenario: List model versions with MLflow links

- **GIVEN** a tenant with 3 model versions (v1 archived, v2 promoted, v3 training) and MLflow tracking enabled
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain all 3 versions
- **AND** each version SHALL contain `version_number`, `status`, `training_job_id`, `created_at`, `metrics`, `mlflow_run_id`, `mlflow_run_url`, and `run_name`

#### Scenario: List models as annotator

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator GETs `/api/v1/models`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL be the same as a Tenant Admin would see (read-only access)

#### Scenario: List models when MLflow server is unavailable

- **GIVEN** a tenant with model versions stored in the local DB cache
- **WHEN** the MLflow Tracking Server is unreachable
- **THEN** the Model Registry proxy SHALL return model list from the local cache
- **AND** the response SHALL have status 200
- **AND** the response SHALL include a warning header `X-Info: mlflow-unavailable`

#### Scenario: List all versions when multiple exist in same MLflow stage

- **GIVEN** a tenant with 3 registered model versions, all in MLflow stage `None`
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL contain all 3 versions
- **AND** each version SHALL include `version_number`, `status`, `training_job_id`, `created_at`, `metrics`, `mlflow_run_id`, `mlflow_run_url`, and `run_name`

#### Scenario: Model version created via a run-numbered training job exposes a run name

- **GIVEN** a training job with `run_number: 3` submitted on 2026-07-29 that completes and produces model version `v3`
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL contain that version with `run_name: "run-003-20260729"`

#### Scenario: Legacy model version with no run_number exposes a null run name

- **GIVEN** a model version created before run-number tracking existed, with no associated `run_number`
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL contain that version with `run_name: null`

## ADDED Requirements

### Requirement: Base model omits run name

The base model (version 0) metadata returned by the Model Registry SHALL always include `run_name: null`, since it is a synthetic singleton not produced by any training job run.

#### Scenario: Active model endpoint returns null run name for the base model

- **GIVEN** a tenant with no promoted fine-tuned model
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `version_number: 0` and `run_name: null`
