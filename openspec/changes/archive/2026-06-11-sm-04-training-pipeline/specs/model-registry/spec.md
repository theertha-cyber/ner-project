## ADDED Requirements

### Requirement: List model versions

The system SHALL list all model versions for a tenant, ordered by version number descending, with status (training/completed/promoted/archived), creation date, and training job reference.

#### Scenario: List model versions

- **GIVEN** a tenant with 3 model versions (v1 archived, v2 promoted, v3 training)
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain all 3 versions
- **AND** each version SHALL contain `version_number`, `status`, `training_job_id`, `created_at`, and `metrics`

#### Scenario: List models as annotator

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator GETs `/api/v1/models`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL be the same as a Tenant Admin would see (read-only access)

### Requirement: Promote model version

The system SHALL allow a Tenant Admin to promote a model version with "completed" status to "promoted" (production). The previously promoted version (if any) SHALL be automatically demoted to "archived". Only one model version per tenant SHALL be in "promoted" status at any time.

#### Scenario: Promote a completed model

- **GIVEN** a tenant with model v1 in "completed" status and no currently promoted version
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{version_id}/promote`
- **THEN** the response SHALL have status 200
- **AND** the model version's status SHALL be "promoted"

#### Scenario: Promote replaces previously promoted version

- **GIVEN** a tenant with model v1 in "promoted" status and model v2 in "completed" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/promote`
- **THEN** v2's status SHALL be "promoted"
- **AND** v1's status SHALL be "archived"

#### Scenario: Promote a non-completed model returns 422

- **GIVEN** a tenant with model v1 in "training" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v1_id}/promote`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate only completed models can be promoted

#### Scenario: Promote as annotator returns 403

- **GIVEN** a completed model version
- **WHEN** an annotator user POSTs to promote it
- **THEN** the response SHALL have status 403

### Requirement: Demote model version

The system SHALL allow a Tenant Admin to demote the currently promoted model version back to "completed" status, leaving no promoted version for the tenant.

#### Scenario: Demote the active model

- **GIVEN** a tenant with model v2 in "promoted" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/demote`
- **THEN** the response SHALL have status 200
- **AND** the model's status SHALL be "completed"
- **AND** the tenant SHALL have no promoted model

#### Scenario: Demote a non-promoted model returns 422

- **GIVEN** a tenant with model v1 in "completed" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v1_id}/demote`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate only promoted models can be demoted

### Requirement: Get active model version

The system SHALL expose an endpoint to query the tenant's currently promoted model version. This endpoint SHALL be used by SM-05 to determine which model to load for extraction.

#### Scenario: Get active model when one is promoted

- **GIVEN** a tenant with model v2 in "promoted" status
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the promoted model's version number, artifact path, and metrics

#### Scenario: Get active model when none is promoted

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin GETs `/api/v1/models/active`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL indicate no active model exists
