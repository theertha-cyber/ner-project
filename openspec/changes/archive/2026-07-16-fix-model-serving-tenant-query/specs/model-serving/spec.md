## MODIFIED Requirements

### Requirement: Model Registry URL is configurable and targets the correct in-network port

**Modification:** The existing requirement is expanded to add that inter-service calls as `system_admin` MUST include the `tenant_id` query parameter.

The model-serving layer SHALL resolve the Model Registry (`training_service`) base URL from a `training_service_url` setting, not a hardcoded literal. The setting SHALL default to the correct bare-metal host-mapped port for local development, and SHALL be overridable via environment variable for Docker Compose to target the service's internal container port. When calling the Model Registry's `/api/v1/models/active` endpoint as a `system_admin` caller, the request SHALL include `tenant_id` as a query parameter.

#### Scenario: Registry URL is read from settings, not hardcoded

- **GIVEN** `_resolve_active_version()` and `_resolve_label_list()` need to query the active model
- **WHEN** either function builds the Model Registry request URL
- **THEN** the URL SHALL be built from `settings.training_service_url`
- **AND** no literal `http://training_service:8003` or similar hardcoded host:port string SHALL appear in `inference_service.py`

#### Scenario: Registry URL defaults to the correct port for bare-metal dev

- **GIVEN** the `NER_TRAINING_SERVICE_URL` environment variable is not set
- **WHEN** model-serving resolves the active model version
- **THEN** the request SHALL be sent to `http://localhost:8003/api/v1/models/active`

#### Scenario: Registry URL is overridden to the Docker-internal port

- **GIVEN** `NER_TRAINING_SERVICE_URL` is set to `http://training_service:8000`
- **WHEN** model-serving resolves the active model version inside the Docker Compose network
- **THEN** the request SHALL be sent to `http://training_service:8000/api/v1/models/active`
- **AND** the request SHALL successfully connect (not fail with a connection error)

#### Scenario: A misconfigured or unreachable registry URL still falls back to the base model

- **GIVEN** `training_service_url` points at an address with nothing listening
- **WHEN** model-serving attempts to resolve the active model version
- **THEN** the request SHALL fail with a connection error
- **AND** the system SHALL fall back to treating the tenant as version 0 (base model), consistent with the "Version resolution with base fallback" requirement
- **AND** this fallback SHALL NOT be the outcome of every request once the URL is correctly configured (regression guard for the bug where the hardcoded port made this the permanent, not exceptional, path)

#### MODIFIED: System admin inter-service call includes tenant_id query parameter

- **GIVEN** `_resolve_active_version()` calls `GET /api/v1/models/active` with a `system_admin` JWT
- **WHEN** the request is built
- **THEN** the request SHALL include `tenant_id` as a query parameter with the tenant's ID
- **AND** the endpoint SHALL return 200 with the promoted model's metadata (not 400)

#### MODIFIED: Label list resolution includes tenant_id query parameter

- **GIVEN** `_resolve_label_list()` calls `GET /api/v1/models/active` with a `system_admin` JWT
- **WHEN** the request is built
- **THEN** the request SHALL include `tenant_id` as a query parameter with the tenant's ID
- **AND** the endpoint SHALL return 200 with the model's metrics including `label_list` (not 400)
