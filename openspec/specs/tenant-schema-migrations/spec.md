# Tenant Schema Migrations

## Purpose

Ensure that Alembic migrations affecting tenant-scoped tables are propagated to all existing tenant schemas at migration time, preventing schema drift between `tenant_template` and provisioned tenant schemas.

---

## Requirements

### Requirement: Tenant-scoped migrations propagate to existing tenant schemas

When an Alembic migration changes the shape of a tenant-scoped table (adds a table, column, or index) in the `tenant_template` schema, the system SHALL apply the equivalent DDL to every tenant schema that already exists at migration time, regardless of that tenant's `status`, in the same migration run. A tenant's schema SHALL NOT permanently retain an outdated shape after a migration that changes the corresponding tenant-scoped table has been applied.

#### Scenario: A new column is added to a tenant-scoped table

- **GIVEN** an existing tenant with an already-provisioned schema `tenant_<id>`
- **AND** a new migration adds column `foo` to `tenant_template.some_table`
- **WHEN** the migration is applied (`alembic upgrade head`)
- **THEN** `tenant_template.some_table` SHALL have column `foo`
- **AND** `tenant_<id>.some_table` SHALL also have column `foo`

#### Scenario: An inactive tenant's schema is still updated

- **GIVEN** a tenant with `status: "inactive"` and an already-provisioned schema
- **AND** a migration changes a tenant-scoped table's shape
- **WHEN** the migration is applied
- **THEN** the inactive tenant's schema SHALL receive the same DDL as active tenants' schemas
- **AND** reactivating that tenant afterward SHALL NOT surface a schema mismatch caused by having been skipped during the migration

#### Scenario: Re-running the migration DDL is a no-op

- **GIVEN** a tenant schema that already has the shape a migration's DDL would produce
- **WHEN** the same migration's per-tenant-schema DDL is executed against that schema again
- **THEN** no error SHALL occur
- **AND** the schema's shape SHALL be unchanged

### Requirement: The `training_jobs.error_message` column is backfilled onto the template and every existing tenant schema

Migration `005_training_service_tables`'s `CREATE TABLE IF NOT EXISTS tenant_template.training_jobs` silently no-opped because the table already existed (created with a different shape by migration `002_tenant_template_schema`), so the `error_message` column it defined was never actually applied to `tenant_template` or any tenant schema, unlike the rest of 005's columns which were later patched in by migrations `006`, `012`, and `013`. The system SHALL provide a remediation migration that adds the `error_message` column to `tenant_template.training_jobs` and to every existing tenant schema's `training_jobs` table.

#### Scenario: `tenant_template` and existing tenants gain the missing column

- **GIVEN** `tenant_template.training_jobs` and every existing tenant's `training_jobs` table lack an `error_message` column
- **WHEN** the remediation migration is applied
- **THEN** `tenant_template.training_jobs` SHALL have an `error_message` column
- **AND** every existing tenant schema's `training_jobs` table SHALL also have an `error_message` column
- **AND** existing rows in every affected table SHALL be preserved, with `error_message` as `NULL` for pre-existing rows

#### Scenario: A schema that already has the column is unaffected

- **GIVEN** a tenant schema (or `tenant_template`) whose `training_jobs` table already has an `error_message` column
- **WHEN** the remediation migration is applied
- **THEN** the migration SHALL complete without error
- **AND** the tenant's data and schema SHALL be unchanged
