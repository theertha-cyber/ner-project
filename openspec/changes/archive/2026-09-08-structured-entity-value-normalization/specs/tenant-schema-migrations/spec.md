## ADDED Requirements

### Requirement: Semantic value columns are added to the template and every existing tenant schema

The system SHALL add the nullable columns `value_kind`, `value_number`, `value_number_high`, `value_unit`, `value_date`, and `value_date_high` to `document_entities` in `tenant_template` and in every existing `tenant_%` schema, together with a partial index on `(entity_type, value_number)` where `value_number` is not NULL and a partial index on `(entity_type, value_date)` where `value_date` is not NULL. The migration SHALL be idempotent, SHALL tolerate a tenant schema in which `document_entities` does not exist, and SHALL NOT alter any existing column's type, nullability, or data.

#### Scenario: Template and existing tenant schemas both gain the columns

- **GIVEN** a database with `tenant_template` and two provisioned tenant schemas, each holding a `document_entities` table
- **WHEN** the migration runs
- **THEN** all three schemas' `document_entities` tables SHALL contain the six semantic value columns
- **AND** each SHALL carry both partial indexes

#### Scenario: Existing rows are preserved

- **GIVEN** a tenant schema whose `document_entities` table holds rows
- **WHEN** the migration runs
- **THEN** the row count SHALL be unchanged
- **AND** every existing row's `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, and `char_end` SHALL be unchanged
- **AND** every new column SHALL be NULL for those rows

#### Scenario: Tenant schema missing the table is skipped

- **GIVEN** a `tenant_%` schema with no `document_entities` table
- **WHEN** the migration runs
- **THEN** the migration SHALL complete successfully
- **AND** the remaining tenant schemas SHALL still be migrated

#### Scenario: Re-running the migration is a no-op

- **GIVEN** the migration has already been applied
- **WHEN** it runs again
- **THEN** it SHALL complete successfully without error
- **AND** the schema SHALL be unchanged

#### Scenario: Newly provisioned tenants inherit the columns

- **GIVEN** the migration has been applied to `tenant_template`
- **WHEN** a new tenant is provisioned by cloning the template
- **THEN** the new tenant's `document_entities` table SHALL contain the six semantic value columns and both partial indexes

### Requirement: Entity definition value kind columns are added to the public schema

The system SHALL add the nullable columns `value_kind` and `value_unit` to `public.entity_definitions`. A NULL `value_kind` SHALL be interpreted as `text`. The migration SHALL NOT backfill values and SHALL NOT alter any existing column.

#### Scenario: Columns are added without touching existing definitions

- **GIVEN** `public.entity_definitions` holds existing rows
- **WHEN** the migration runs
- **THEN** the table SHALL contain `value_kind` and `value_unit`
- **AND** every existing row SHALL have NULL in both
- **AND** no other column SHALL be altered

#### Scenario: Downgrade removes the columns

- **GIVEN** the migration has been applied
- **WHEN** the migration is downgraded
- **THEN** `value_kind` and `value_unit` SHALL be removed
- **AND** the remaining columns and rows SHALL be unchanged
