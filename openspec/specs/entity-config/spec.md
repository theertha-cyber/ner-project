# Entity Configuration

## Purpose

Tenant-scoped entity type management. Allows Tenant Admins to define, version, and manage the entity types used for NER annotation and extraction.

---
## Requirements
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

#### Scenario: An entity type predating the view layer defaults to multi

- **GIVEN** an entity type row created before the view-layer metadata existed
- **WHEN** the `037` migration is applied
- **THEN** its `cardinality` SHALL be `multi`
- **AND** its `sql_identifier` SHALL be a valid identifier derived from its `name`

#### Scenario: Cardinality is constrained to the two known values

- **GIVEN** the `public.entity_definitions` table after migration `037`
- **WHEN** a row is written with `cardinality = 'many'`
- **THEN** the write SHALL be rejected by a CHECK constraint

#### Scenario: Two tenants may share an sql_identifier

- **GIVEN** tenant A has an entity type with `sql_identifier = 'e_skill'`
- **WHEN** tenant B creates an entity type that also slugs to `e_skill`
- **THEN** the write SHALL succeed
- **AND** a second row for tenant A with `sql_identifier = 'e_skill'` SHALL be rejected by the partial unique index on `(tenant_id, sql_identifier)`

### Requirement: Base Label Mapping

The system SHALL allow each entity type to define a `base_label_mapping` field: a JSON object mapping base model CoNLL class names (PER, ORG, LOC, MISC) to this entity type. If an entity type has no mapping, it will not receive pre-labels during annotation. The system SHALL validate that all keys in the mapping are one of PER, ORG, LOC, or MISC.

#### Scenario: Entity type with valid label mapping

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "vendor_name", "base_label_mapping": {"ORG": ["vendor_name"]}}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `base_label_mapping: {"ORG": ["vendor_name"]}`

#### Scenario: Entity type with invalid base model label

- **GIVEN** an authenticated Tenant Admin
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "custom_type", "base_label_mapping": {"INVALID_LABEL": ["custom_type"]}}`
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate `INVALID_LABEL` is not a valid base model label

### Requirement: Entity Type Listing and Query

The system SHALL allow listing all active entity types for a tenant with optional filters by `is_active` status. The system SHALL return entity type details by ID or name. The system SHALL allow soft-deleting an entity type by setting `is_active: false`.

#### Scenario: Tenant Admin lists entity types

- **GIVEN** tenant "acme-corp" has 5 entity types (3 active, 2 inactive)
- **WHEN** the Tenant Admin GETs `/api/v1/tenants/acme-corp/entity-types`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an array of 5 entity type objects
- **AND** each object SHALL include `is_active` field

#### Scenario: Tenant Admin filters active entity types only

- **GIVEN** tenant "acme-corp" has 5 entity types (3 active, 2 inactive)
- **WHEN** the Tenant Admin GETs `/api/v1/tenants/acme-corp/entity-types?is_active=true`
- **THEN** the response SHALL contain exactly 3 entity type objects
- **AND** all returned objects SHALL have `is_active: true`

