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

### Requirement: Per-tenant-schema DDL tolerates tenant schemas missing a table

A migration's per-tenant-schema loop SHALL NOT abort because one tenant schema lacks a table the statement references. Every statement inside such a loop — including `UPDATE`, `INSERT`, and index creation, not only `ALTER TABLE` — SHALL be guarded so that a missing table causes that statement to be skipped for that schema while the loop continues to the remaining schemas. A migration SHALL NOT leave the chain partially applied because a single tenant schema was incomplete.

#### Scenario: A tenant schema missing annotation_tasks does not abort migration 022

- **GIVEN** tenant schemas `tenant_a` (complete) and `tenant_b` (has `documents` but no `annotation_tasks`)
- **WHEN** migration `022_document_purpose_scoping` is applied
- **THEN** the migration SHALL complete successfully
- **AND** `tenant_a.documents` SHALL have the `purpose` column with training rows backfilled
- **AND** `tenant_b.documents` SHALL have the `purpose` column
- **AND** the backfill statement SHALL have been skipped for `tenant_b` without raising

#### Scenario: A tenant schema missing the target table entirely is skipped

- **GIVEN** a tenant schema containing none of the tables a migration's per-tenant loop references
- **WHEN** that migration is applied
- **THEN** the migration SHALL complete successfully
- **AND** `alembic_version` SHALL advance to that migration's revision

#### Scenario: Re-running a guarded loop is a no-op

- **GIVEN** tenant schemas already in the shape a guarded per-tenant loop produces
- **WHEN** the loop's DDL is executed again
- **THEN** no error SHALL occur
- **AND** no schema or data SHALL change

### Requirement: Existing tenant schemas are reconciled to the current template shape

The migration chain SHALL include a reconciliation migration that brings every existing `tenant_<id>` schema up to the current `tenant_template` shape, creating any tenant-scoped table present in `tenant_template` but absent from the tenant schema, and adding any column present in a `tenant_template` table but absent from the tenant's copy. Reconciliation SHALL cover columns that earlier migrations added to `tenant_template` alone without a per-tenant loop — specifically migration `003`'s `content_type`, `file_size`, `blob_path`, and `updated_at` on `documents`, and its `span_index`, `char_start`, `char_end`, `page_number`, and `created_at` on `document_text_spans`. Reconciliation SHALL be idempotent and SHALL NOT drop or alter columns that exist only in the tenant schema.

#### Scenario: A tenant schema provisioned before migration 003 gains its columns

- **GIVEN** a tenant schema whose `documents` table lacks `content_type`, `file_size`, and `blob_path`
- **WHEN** the reconciliation migration is applied
- **THEN** that tenant's `documents` table SHALL have all three columns
- **AND** document upload against that tenant SHALL succeed

#### Scenario: A tenant schema missing a whole table gains it from the template

- **GIVEN** `tenant_template` contains a `documents` table
- **AND** a tenant schema that does not contain a `documents` table
- **WHEN** the reconciliation migration is applied
- **THEN** that tenant schema SHALL contain a `documents` table with the template's columns, defaults, constraints, and indexes

#### Scenario: Reconciliation preserves tenant-only columns

- **GIVEN** a tenant schema whose table carries a column not present in `tenant_template`
- **WHEN** the reconciliation migration is applied
- **THEN** that column SHALL still exist and its data SHALL be unchanged

#### Scenario: Reconciliation is idempotent

- **GIVEN** a database on which the reconciliation migration has already been applied
- **WHEN** the same reconciliation DDL is executed again
- **THEN** no error SHALL occur
- **AND** no schema or data SHALL change

### Requirement: Tenant provisioning clones the template atomically

Provisioning a new tenant SHALL create the tenant's schema and every table present in `tenant_template` as a single atomic unit. If any table fails to be created, the whole provisioning SHALL be rolled back so that no tenant row, schema, or partially-populated schema survives. A tenant SHALL NOT exist in `public.tenants` with a schema that is missing tables present in `tenant_template`.

#### Scenario: A failed table clone rolls back the whole tenant

- **GIVEN** tenant provisioning is in progress
- **WHEN** creation of one tenant-scoped table fails
- **THEN** no row for that tenant SHALL remain in `public.tenants`
- **AND** no schema for that tenant SHALL remain in the database
- **AND** no user row for that tenant SHALL remain in `public.tenant_users`

#### Scenario: A provisioned tenant has the full template table set

- **GIVEN** `tenant_template` contains N tables
- **WHEN** a new tenant is provisioned successfully
- **THEN** that tenant's schema SHALL contain all N tables
- **AND** listing documents for that tenant SHALL return an empty list rather than an error
