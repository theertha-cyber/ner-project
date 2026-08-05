## MODIFIED Requirements

### Requirement: Entity Type Definition

The system SHALL allow a Tenant Admin to define entity types within their tenant scope. Each entity type SHALL have: `name`, `description`, `examples` (JSON array of example strings), `validation_rule` (optional regex or type constraint), `target_table` (optional target DB table name for extraction), `value_kind` (optional semantic value kind, one of `text`, `number`, `duration`, `money`, `date`, `boolean`, defaulting to `text`), `value_unit` (optional canonical unit for the declared kind, e.g. `years`, `days`, `INR`), `required_flag` (boolean), and `is_active` (boolean). Entity types SHALL be versioned — each update increments the version number. The system SHALL reject a `value_kind` outside the supported set.

#### Scenario: Tenant Admin creates an entity type

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "customer_name", "description": "Full name of a customer", "examples": ["John Smith", "Acme Corp"], "validation_rule": null, "required_flag": true}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain an `entity_type` object with `name: "customer_name"`, `version: 1`, `is_active: true`
- **AND** `value_kind` SHALL default to `text`

#### Scenario: Tenant Admin updates an entity type

- **GIVEN** entity type "customer_name" exists with `version: 1`
- **WHEN** the Tenant Admin PUTs to `/api/v1/tenants/acme-corp/entity-types/customer_name` with `{"description": "Updated description"}`
- **THEN** the response SHALL have status 200
- **AND** `version` SHALL be `2`
- **AND** `description` SHALL be `"Updated description"`

#### Scenario: Tenant Admin declares a structured value kind

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "YEARS_OF_EXP", "value_kind": "duration", "value_unit": "years"}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `value_kind: "duration"` and `value_unit: "years"`

#### Scenario: Unsupported value kind is rejected

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST an entity type with `{"name": "office_location", "value_kind": "geo"}`
- **THEN** the response SHALL have status 422
- **AND** no entity type SHALL be created

#### Scenario: Existing entity types keep working

- **GIVEN** entity types created before `value_kind` existed
- **WHEN** they are read through the entity types API
- **THEN** each SHALL report `value_kind: "text"` and `value_unit: null`
- **AND** extraction for those types SHALL behave exactly as before
