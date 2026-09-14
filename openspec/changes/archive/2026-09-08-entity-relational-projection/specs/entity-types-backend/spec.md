## ADDED Requirements

### Requirement: Creating an entity type assigns its sql_identifier

`EntityService.create_entity_type` SHALL assign `sql_identifier` at insert time by calling `to_sql_identifier(name, taken)` with `taken` loaded as the set of `sql_identifier` values already used by that tenant. The value SHALL be written in the same statement as the rest of the row. It SHALL NOT be assigned lazily at read time, and it SHALL NOT be changed by any later update.

Without this, every entity type created after migration `037` carries a NULL `sql_identifier` and is therefore skipped by the reconciler and the projection — the entity type appears correctly in the UI and in `document_entities` while being silently absent from the entire relational query surface.

#### Scenario: A newly created entity type gets an identifier

- **GIVEN** a tenant admin creating an entity type named `Vendor Name`
- **WHEN** the create succeeds
- **THEN** the persisted row SHALL have a non-NULL `sql_identifier` matching `^e_[a-z0-9][a-z0-9_]*$`

#### Scenario: The identifier is unique within the tenant

- **GIVEN** a tenant that already has an entity type whose `sql_identifier` is `e_vendor_name`
- **WHEN** the tenant admin creates a second entity type whose name slugs to the same value
- **THEN** the second row SHALL receive a different `sql_identifier`
- **AND** the partial unique index on `(tenant_id, sql_identifier)` SHALL NOT be violated

#### Scenario: Renaming is impossible and the identifier survives every update

- **GIVEN** an entity type with `sql_identifier = 'e_vendor_name'`
- **WHEN** it is updated, toggled, or soft-deleted
- **THEN** its `sql_identifier` SHALL be unchanged

#### Scenario: A newly created entity type is projected on the next run

- **GIVEN** a tenant admin creates an active `multi` entity type
- **WHEN** the next batch extraction run reconciles and processes a document containing that entity
- **THEN** the entity type's generated table SHALL exist
- **AND** it SHALL contain the document's routed rows

### Requirement: Create and update accept cardinality

The create endpoint SHALL accept an optional `cardinality` field with the values `single` or `multi`, defaulting to `multi` when omitted. The update endpoint SHALL accept `cardinality` as a modifiable field. Both SHALL reject any other value with HTTP 422 and a message naming the two permitted values, before the write reaches the database — the `037` CHECK constraint is a backstop, not the validation path.

`multi` remains the default because a genuinely multi-valued entity rendered as a child table is always correct, whereas marking a multi-valued entity `single` silently discards every value except the selected one from the query surface.

#### Scenario: Create with cardinality single persists single

- **GIVEN** a tenant admin
- **WHEN** they POST an entity type with `"cardinality": "single"`
- **THEN** the response SHALL have status 201
- **AND** the persisted row SHALL have `cardinality = 'single'`

#### Scenario: Create without cardinality defaults to multi

- **GIVEN** a tenant admin
- **WHEN** they POST an entity type with no `cardinality` field
- **THEN** the persisted row SHALL have `cardinality = 'multi'`

#### Scenario: Update changes cardinality

- **GIVEN** an entity type with `cardinality = 'multi'`
- **WHEN** the tenant admin PUTs `{"cardinality": "single"}`
- **THEN** the response SHALL have status 200
- **AND** the returned entity SHALL have `cardinality: "single"`
- **AND** `version` SHALL be incremented

#### Scenario: An invalid cardinality is rejected with 422

- **GIVEN** a tenant admin
- **WHEN** they POST or PUT with `"cardinality": "many"`
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL name `single` and `multi`
- **AND** no row SHALL be written or modified

### Requirement: Entity type responses expose view-layer metadata

Every entity type read path — list, get by name, and the flat objects returned by create and update — SHALL include `cardinality` and `sql_identifier` in the response body. `sql_identifier` SHALL be presented as read-only metadata; the API SHALL ignore it if a client sends it in a create or update payload.

Without this, the UI cannot display an entity type's persisted cardinality when the admin opens the edit form, and would silently reset the field to its default on every save.

#### Scenario: The list response carries both fields

- **GIVEN** a tenant with two entity types
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types`
- **THEN** each entry SHALL include `cardinality` and `sql_identifier`

#### Scenario: Get by name carries both fields

- **GIVEN** an entity type `vendor_name`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types/vendor_name`
- **THEN** the body SHALL include `cardinality` and `sql_identifier`

#### Scenario: Create and update responses carry both fields

- **GIVEN** a valid create or update payload
- **WHEN** the request succeeds
- **THEN** the flat entity object SHALL include `cardinality` and `sql_identifier`

#### Scenario: A client-supplied sql_identifier is ignored

- **GIVEN** a tenant admin
- **WHEN** they POST or PUT with `"sql_identifier": "e_injected"`
- **THEN** the persisted `sql_identifier` SHALL be the system-assigned value
- **AND** the request SHALL NOT fail on account of the extra field

### Requirement: Definition write paths reconcile the tenant's generated schema

`create_entity_type`, `update_entity_type`, `toggle_entity_type`, and `soft_delete_entity_type` SHALL each reconcile the tenant's generated relational schema after their write, in that call's own transaction. Reconciliation SHALL NOT drop a table or column in any of the four paths, in either direction of `is_active`.

#### Scenario: Creating an entity type creates its relation

- **GIVEN** a tenant schema with `document_entities`
- **WHEN** a tenant admin creates an active `multi` entity type
- **THEN** its generated child table SHALL exist when the request returns

#### Scenario: Changing cardinality reconciles the new representation

- **GIVEN** an active entity type with `cardinality = 'multi'` whose child table exists
- **WHEN** the tenant admin updates it to `cardinality = 'single'`
- **THEN** the `subject` table SHALL gain that entity type's column
- **AND** the child table SHALL still exist with its rows intact

#### Scenario: Deactivation reconciles without dropping

- **GIVEN** an active entity type whose generated table holds rows
- **WHEN** the tenant admin deactivates it
- **THEN** the table and its rows SHALL be unchanged
- **AND** no `DROP` statement SHALL be executed

### Requirement: Entity type payloads are validated by a typed schema

The create, update, and toggle endpoints SHALL validate their request bodies against declared Pydantic models rather than accepting an untyped `dict`. An unknown or malformed field SHALL produce HTTP 422 rather than a database error surfaced as HTTP 500. The toggle endpoint SHALL return 422 when `is_active` is absent rather than raising `KeyError`.

#### Scenario: A malformed create payload returns 422

- **GIVEN** a tenant admin
- **WHEN** they POST a body missing the required `name` field
- **THEN** the response SHALL have status 422
- **AND** the response SHALL NOT be a 500

#### Scenario: A toggle without is_active returns 422

- **GIVEN** a tenant admin
- **WHEN** they PATCH an entity type with an empty body
- **THEN** the response SHALL have status 422
