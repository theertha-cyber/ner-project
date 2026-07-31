## ADDED Requirements

### Requirement: The `document_entities` table exists on the template and every tenant schema

The migration introducing normalized entity storage SHALL create the `document_entities` table in `tenant_template` and in every tenant schema that exists at migration time, regardless of that tenant's `status`. The table SHALL have columns `id` (UUID primary key), `document_id` (UUID), `entity_type` (TEXT), `entity_value` (TEXT), `normalized_value` (TEXT), `confidence` (DOUBLE PRECISION), `page_number` (INTEGER), `char_start` (INTEGER), `char_end` (INTEGER), and `created_at` (TIMESTAMPTZ). The migration SHALL create indexes on `document_id`, on `entity_type`, and on `normalized_value`. The migration SHALL be re-runnable without error and SHALL NOT alter `extracted_entities` in any schema.

#### Scenario: Template and existing tenant schemas both receive the table

- **GIVEN** an existing tenant with an already-provisioned schema `tenant_<id>`
- **WHEN** the migration is applied (`alembic upgrade head`)
- **THEN** `tenant_template.document_entities` SHALL exist with the specified columns
- **AND** `tenant_<id>.document_entities` SHALL also exist with the specified columns and indexes

#### Scenario: Inactive tenant schemas are not skipped

- **GIVEN** a tenant with `status: "inactive"` and an already-provisioned schema
- **WHEN** the migration is applied
- **THEN** that tenant's schema SHALL also contain `document_entities`

#### Scenario: Raw entity table is untouched

- **GIVEN** a tenant schema with populated `extracted_entities` rows
- **WHEN** the migration is applied
- **THEN** `extracted_entities` SHALL retain its columns and all of its rows

#### Scenario: Re-running the migration DDL is a no-op

- **GIVEN** a tenant schema that already contains `document_entities`
- **WHEN** the migration's per-tenant-schema DDL is executed against that schema again
- **THEN** no error SHALL occur
- **AND** the schema's shape SHALL be unchanged

#### Scenario: Downgrade removes only the new table

- **GIVEN** the migration has been applied
- **WHEN** the migration is downgraded
- **THEN** `document_entities` SHALL be dropped from the template and every tenant schema
- **AND** `extracted_entities` SHALL be unaffected
