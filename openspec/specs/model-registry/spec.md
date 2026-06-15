# Model Registry

## Purpose

Manages the lifecycle of trained model versions per tenant: listing, promoting, demoting, and querying the active model for extraction.

---

## Requirements

### Requirement: List model versions

The system SHALL list all model versions for a tenant, ordered by version number descending, with status (training/completed/promoted/archived), creation date, training job reference, and MLflow run URL.

#### Scenario: List model versions with MLflow links

- **GIVEN** a tenant with 3 model versions (v1 archived, v2 promoted, v3 training) and MLflow tracking enabled
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain all 3 versions
- **AND** each version SHALL contain `version_number`, `status`, `training_job_id`, `created_at`, `metrics`, `mlflow_run_id`, and `mlflow_run_url`

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

### Requirement: Promote model version

The system SHALL allow a Tenant Admin to promote a model version with "completed" status (MLflow Staging stage) to "promoted" (MLflow Production stage). The previously promoted version SHALL be transitioned to MLflow Archived stage. Only one model version per tenant SHALL be in Production stage at any time. After promoting, the system SHALL trigger model-serving cache warmup for the newly promoted version. If warmup fails, the promotion SHALL still succeed (graceful degradation).

#### Scenario: Promote a completed model via MLflow with warmup

- **GIVEN** a tenant with model v1 in "completed" status (MLflow Staging) and no currently promoted version
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{version_id}/promote`
- **THEN** the Model Registry proxy SHALL transition the version to MLflow Production stage
- **AND** the proxy SHALL call the model-serving warmup endpoint
- **AND** the proxy SHALL wait for model-serving to confirm the model is loaded
- **AND** the response SHALL have status 200
- **AND** the model version's status SHALL be "promoted"
- **AND** the proxy SHALL update the local cache

#### Scenario: Promote replaces previously promoted version via MLflow

- **GIVEN** a tenant with model v1 in "promoted" status (MLflow Production) and model v2 in "completed" status (MLflow Staging)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/promote`
- **THEN** v2's status SHALL be "promoted" (MLflow Production)
- **AND** v1's status SHALL be "archived" (MLflow Archived)
- **AND** both transitions SHALL be persisted in the MLflow Model Registry
- **AND** the proxy SHALL call the model-serving warmup endpoint

#### Scenario: Promote a non-completed model returns 422

- **GIVEN** a tenant with model v1 in "training" status (no MLflow registered model version yet)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v1_id}/promote`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate only completed models can be promoted

#### Scenario: Promote as annotator returns 403

- **GIVEN** a completed model version
- **WHEN** an annotator user POSTs to promote it
- **THEN** the response SHALL have status 403

#### Scenario: Warmup failure does not fail promote

- **GIVEN** the model-serving service is unavailable
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{version_id}/promote`
- **THEN** the MLflow stage transition SHALL succeed
- **AND** the local cache SHALL be updated
- **AND** the warmup error SHALL be logged
- **AND** the response SHALL have status 200

### Requirement: Demote model version

The system SHALL allow a Tenant Admin to demote the currently promoted model version (MLflow Production) back to "completed" status (MLflow Staging), leaving no promoted version for the tenant.

#### Scenario: Demote the active model via MLflow

- **GIVEN** a tenant with model v2 in "promoted" status (MLflow Production)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/demote`
- **THEN** the Model Registry proxy SHALL transition the version to MLflow Staging stage
- **AND** the response SHALL have status 200
- **AND** the model's status SHALL be "completed"
- **AND** the tenant SHALL have no promoted model

#### Scenario: Demote a non-promoted model returns 422

- **GIVEN** a tenant with model v1 in "completed" status (MLflow Staging)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v1_id}/demote`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate only promoted models can be demoted

### Requirement: Get active model version

The system SHALL expose an endpoint to query the tenant's currently promoted model version. This endpoint SHALL query the MLflow Model Registry for the Production stage version and fall back to the local cache if the MLflow server is unavailable. SM-05 uses this endpoint to determine which model to load for extraction.

#### Scenario: Get active model from MLflow when one is promoted

- **GIVEN** a tenant with model v2 in "promoted" status (MLflow Production stage)
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the promoted model's version number, artifact path, metrics, and MLflow run URL

#### Scenario: Get active model when MLflow is unavailable

- **GIVEN** a tenant with a promoted model cached locally
- **WHEN** the MLflow Tracking Server is unreachable
- **THEN** the proxy SHALL return the active model from the local cache
- **AND** the response SHALL have status 200
- **AND** the response SHALL include a warning header

#### Scenario: Get active model when none is promoted

- **GIVEN** a tenant with no promoted model (no Production stage version)
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL indicate no active model exists
