## MODIFIED Requirements

### Requirement: Get active model version

The system SHALL expose an endpoint to query the tenant's currently promoted model version. This endpoint SHALL query the MLflow Model Registry for the Production stage version and fall back to the local cache if the MLflow server is unavailable. SM-05 uses this endpoint to determine which model to load for extraction. The response SHALL include the `label_list` from the model version's `metrics` JSONB column, enabling the inference service to map ONNX output indices to the tenant's custom entity labels.

#### Scenario: Get active model from MLflow when one is promoted

- **GIVEN** a tenant with model v2 in "promoted" status (MLflow Production stage) and `metrics.label_list`: `["O", "B-company", "I-company"]`
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the promoted model's version number, artifact path, metrics, and MLflow run URL
- **AND** the response SHALL contain `label_list` with the tenant's custom entity labels

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
