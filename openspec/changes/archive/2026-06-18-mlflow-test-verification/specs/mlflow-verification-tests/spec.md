## ADDED Requirements

### Requirement: MLflow server health verification

The test script SHALL verify the MLflow Tracking Server is reachable and responsive before running integration-dependent tests.

#### Scenario: Health check returns 200

- **GIVEN** the MLflow Tracking Server is running at `settings.mlflow_tracking_uri`
- **WHEN** a GET request is sent to `{tracking_uri}/health`
- **THEN** the response status SHALL be 200

### Requirement: Experiment and run lifecycle

The test script SHALL verify the full MLflow experiment and run lifecycle: creation, parameter/metric logging, tagging, and status transitions.

#### Scenario: Create experiment and run with params and tags

- **GIVEN** a unique tenant ID
- **WHEN** an MLflow experiment `tenant_{tid}` is created
- **AND** a run is created under that experiment with `log_params()` and `set_tags()`
- **THEN** the experiment SHALL exist with the correct name
- **AND** the run SHALL contain the logged params (`learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`)
- **AND** the run SHALL contain the logged tags (`base_model`, `tenant_id`, `training_job_id`, `num_labels`)

#### Scenario: Metrics logged per-step

- **GIVEN** an active MLflow run
- **WHEN** `log_metric()` is called with `eval_f1` at step 0 and step 1
- **THEN** the metric history SHALL contain both values
- **AND** the latest value SHALL be the final logged value

#### Scenario: Run failure sets FAILED status

- **GIVEN** an active MLflow run
- **WHEN** `set_terminated(status="FAILED")` is called with an `error_message` tag
- **THEN** the run status SHALL be `FAILED`
- **AND** the `error_message` tag SHALL contain the error description

### Requirement: Model registration and artifact logging

The test script SHALL verify that trained model artifacts can be logged to MLflow and registered under the tenant-specific model name.

#### Scenario: Model registered with correct naming convention

- **GIVEN** a completed MLflow run with a logged model
- **WHEN** a registered model is created with name `tenant_{tid}_ner_model`
- **AND** a model version is created from the run
- **THEN** the registered model SHALL exist in MLflow
- **AND** the version SHALL reference the correct run ID
- **AND** the version's stage SHALL default to `None`

### Requirement: Model registry proxy integration

The test script SHALL verify that the Model Registry proxy functions (`list_model_versions`, `get_active_model`, `promote_model_version`, `demote_model_version`) work correctly against a live MLflow server.

#### Scenario: List model versions returns registered models

- **GIVEN** a tenant with registered model versions in MLflow
- **WHEN** `list_model_versions(tenant_id)` is called
- **THEN** the response SHALL contain all versions
- **AND** each version SHALL include `version_number`, `status`, `mlflow_run_id`, and `mlflow_run_url`

#### Scenario: Promote transitions Staging to Production

- **GIVEN** a model version in "completed" status (MLflow Staging stage)
- **WHEN** `promote_model_version(tenant_id, version_number)` is called
- **THEN** the version's MLflow stage SHALL be `Production`
- **AND** the returned status SHALL be `promoted`
- **AND** `get_active_model(tenant_id)` SHALL return this version

#### Scenario: Promote archives previous Production version

- **GIVEN** a tenant with v1 in Production and v2 in Staging
- **WHEN** v2 is promoted
- **THEN** v2's stage SHALL be `Production`
- **AND** v1's stage SHALL be `Archived`
- **AND** `get_active_model(tenant_id)` SHALL return v2

#### Scenario: Demote returns to Staging

- **GIVEN** a model version in Production stage
- **WHEN** `demote_model_version(tenant_id, version_number)` is called
- **THEN** the version's MLflow stage SHALL be `Staging`
- **AND** the returned status SHALL be `completed`
- **AND** `get_active_model(tenant_id)` SHALL return `None`

#### Scenario: List returns empty when no registered model exists

- **GIVEN** a tenant with no registered model in MLflow
- **WHEN** `list_model_versions(tenant_id)` is called
- **THEN** the response SHALL be an empty list
- **AND** no warning SHALL be returned

### Requirement: DB cache fallback on MLflow outage

The test script SHALL verify that the Model Registry proxy falls back to the local PostgreSQL cache when MLflow is unreachable, and returns an appropriate warning indicator.

#### Scenario: Cache returns model list when MLflow unavailable

- **GIVEN** a tenant with cached model versions in the `model_versions` DB table
- **WHEN** MLflow is unreachable and `list_model_versions(tenant_id)` is called
- **THEN** the response SHALL contain the cached versions
- **AND** a warning SHALL indicate `mlflow-unavailable`

#### Scenario: Cache returns active model when MLflow unavailable

- **GIVEN** a tenant with a promoted model cached in the DB
- **WHEN** MLflow is unreachable and `get_active_model(tenant_id)` is called
- **THEN** the response SHALL contain the cached promoted model
- **AND** a warning SHALL indicate `mlflow-unavailable`

### Requirement: Tenant isolation via naming convention

The test script SHALL verify that tenant isolation works via the naming convention — each tenant's models are scoped to their own experiment and registered model name.

#### Scenario: Tenant A and Tenant B models do not overlap

- **GIVEN** two unique tenant IDs A and B
- **WHEN** a model is registered for Tenant A under `tenant_{A}_ner_model`
- **THEN** `_registered_model_name(B)` SHALL NOT equal `_registered_model_name(A)`
- **AND** `list_model_versions(A)` SHALL include Tenant A's model
- **AND** `list_model_versions(B)` SHALL NOT include Tenant A's model

### Requirement: Status-to-stage mapping consistency

The test script SHALL verify the status-to-stage mapping is correct and round-trippable.

#### Scenario: Statuses map to stages and back

- **GIVEN** the `STATUS_TO_STAGE` and `STAGE_TO_STATUS` mappings
- **WHEN** each status is mapped to a stage via `STATUS_TO_STAGE`
- **THEN** `STAGE_TO_STATUS[STATUS_TO_STAGE[status]]` SHALL equal the original status
- **AND** the mappings SHALL be: `completed`→`Staging`, `promoted`→`Production`, `archived`→`Archived`
