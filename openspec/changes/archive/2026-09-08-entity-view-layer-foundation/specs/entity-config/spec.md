## MODIFIED Requirements

### Requirement: Entity Type Definition

The system SHALL allow a Tenant Admin to define entity types within their tenant scope. Each entity type SHALL have: `name`, `description`, `examples` (JSON array of example strings), `validation_rule` (optional regex or type constraint), `target_table` (optional target DB table name for extraction), `required_flag` (boolean), `is_active` (boolean), `cardinality` (`single` or `multi`, defaulting to `multi`), and `sql_identifier` (the system-assigned, immutable Postgres identifier for that entity type's generated view). Entity types SHALL be versioned — each update increments the version number.

`cardinality` determines how the entity renders in the tenant's generated view layer: `single` becomes a pivoted column on the tenant's `subject` view, `multi` becomes its own child view. The default SHALL be `multi`, because rendering a genuinely multi-valued entity as a child view is always correct, whereas marking a multi-valued entity `single` silently collapses its values through the pivot's aggregate.

`sql_identifier` SHALL be assigned once when the entity type is created and SHALL NOT change thereafter, so renaming an entity type's display name neither renames nor orphans its view. It SHALL be unique per tenant; two tenants MAY hold the same `sql_identifier` because their views live in separate schemas.

#### Scenario: Tenant Admin creates an entity type

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "customer_name", "description": "Full name of a customer", "examples": ["John Smith", "Acme Corp"], "validation_rule": null, "required_flag": true}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain an `entity_type` object with `name: "customer_name"`, `version: 1`, `is_active: true`

#### Scenario: Tenant Admin updates an entity type

- **GIVEN** entity type "customer_name" exists with `version: 1`
- **WHEN** the Tenant Admin PUTs to `/api/v1/tenants/acme-corp/entity-types/customer_name` with `{"description": "Updated description"}`
- **THEN** the response SHALL have status 200
- **AND** `version` SHALL be `2`
- **AND** `description` SHALL be `"Updated description"`

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
