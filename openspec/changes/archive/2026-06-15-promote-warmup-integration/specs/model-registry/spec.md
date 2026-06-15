## MODIFIED Requirements

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
