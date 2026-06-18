## MODIFIED Requirements

### Requirement: Get active model version

The system SHALL expose an endpoint to query the tenant's currently promoted model version. This endpoint SHALL query the MLflow Model Registry for the Production stage version and fall back to the local cache if the MLflow server is unavailable. If no promoted model version exists for the tenant, the endpoint SHALL return synthetic base model metadata (version 0, CoNLL label list, empty metrics).

#### Scenario: Get active model from MLflow when one is promoted

- **GIVEN** a tenant with model v2 in "promoted" status (MLflow Production stage)
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the promoted model's version number, artifact path, metrics, and MLflow run URL

#### Scenario: Get active model when none is promoted — returns base model

- **GIVEN** a tenant with no promoted model (no Production stage version)
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `version_number`: 0
- **AND** the response SHALL contain `artifact_path`: "base"
- **AND** the response SHALL contain `label_list` with CoNLL-2003 classes
- **AND** the response SHALL contain `metrics`: {}
- **AND** the response SHALL contain a header `X-Model-Source: base` to indicate fallback

#### Scenario: Get active model when MLflow is unavailable with no cached promoted model

- **GIVEN** a tenant with no promoted model cached locally
- **WHEN** the MLflow Tracking Server is unreachable
- **THEN** the proxy SHALL return the base model metadata
- **AND** the response SHALL have status 200
- **AND** the response SHALL include a warning header
