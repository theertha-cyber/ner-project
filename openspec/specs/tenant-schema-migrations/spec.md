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

Provisioning a new `platform` data-plane tenant SHALL create the tenant's schema and every table present in `tenant_template` as a single atomic unit. If any table fails to be created, the whole provisioning SHALL be rolled back so that no tenant row, schema, or partially-populated schema survives. A `platform` tenant SHALL NOT exist in `public.tenants` with a schema that is missing tables present in `tenant_template`. A `tenant_owned` data-plane tenant SHALL NOT have its schema cloned on the platform database; its schema is provisioned into its own store under `tenant-residency-store-provisioning`.

#### Scenario: A failed table clone rolls back the whole tenant

- **GIVEN** tenant provisioning is in progress for a `platform` tenant
- **WHEN** creation of one tenant-scoped table fails
- **THEN** no row for that tenant SHALL remain in `public.tenants`
- **AND** no schema for that tenant SHALL remain in the database
- **AND** no user row for that tenant SHALL remain in `public.tenant_users`

#### Scenario: A provisioned tenant has the full template table set

- **GIVEN** `tenant_template` contains N tables
- **WHEN** a new `platform` tenant is provisioned successfully
- **THEN** that tenant's schema SHALL contain all N tables
- **AND** listing documents for that tenant SHALL return an empty list rather than an error

#### Scenario: A tenant-owned tenant is not cloned on the platform

- **GIVEN** `tenant_template` contains N tables
- **WHEN** a new `tenant_owned` tenant is created
- **THEN** no `tenant_<id>` schema SHALL be created on the platform database

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

### Requirement: Tenant-scoped migration DDL is authored once and delegated to

A tenant-scoped Alembic migration (one that adds or alters a table/column that exists in `tenant_template` and per-tenant `tenant_%` schemas) SHALL NOT define its DDL inline. It SHALL instead import a `src/shared/tenant_store/revisions/NNNN_<name>.py` module and call that module's `statements(schema)` (and, if the migration supports downgrade, a corresponding reverse statement source) inside its own per-schema loop. The same revision module SHALL be the one `src/shared/tenant_store/migrate.py` applies to `tenant_owned` (e.g. Azure-hosted) tenant stores, so a single authored DDL definition reaches both platform-hosted and tenant-owned tenant schemas.

#### Scenario: A tenant-scoped migration delegates its upgrade DDL

- **GIVEN** a new Alembic migration that adds a column to a tenant-scoped table
- **WHEN** the migration's `upgrade()` is inspected
- **THEN** it SHALL contain a call to a `src/shared/tenant_store/revisions` module's `statements(schema)` function for that DDL
- **AND** it SHALL NOT contain the column-adding DDL written out as a literal SQL string

#### Scenario: The same revision reaches a tenant-owned Azure store

- **GIVEN** a tenant in `mode: tenant_owned` whose data plane is `ready`
- **AND** a tenant-scoped migration that delegates to revision module `NNNN`
- **WHEN** `alembic upgrade head` is run against the platform database and `src/shared/tenant_store/migrate.py` is subsequently run
- **THEN** the platform's `tenant_template` and every platform-hosted `tenant_%` schema SHALL reflect revision `NNNN`'s DDL
- **AND** the tenant-owned tenant's remote schema SHALL also reflect revision `NNNN`'s DDL, without requiring any DDL beyond what revision `NNNN` defines

#### Scenario: A migration with inline tenant-scoped DDL and no matching revision fails the check

- **GIVEN** a new Alembic migration whose `upgrade()` executes DDL against `tenant_template` or a `tenant_%`-pattern schema directly, with no import from `src/shared/tenant_store/revisions`
- **WHEN** the tenant-store delegation check runs
- **THEN** the check SHALL fail
- **AND** the failure SHALL name the offending migration file

#### Scenario: A migration exempted from delegation is not flagged

- **GIVEN** a migration that touches only platform-only (non-tenant-scoped) tables, or a tenant-scoped migration carrying an explicit exemption comment with a stated reason
- **WHEN** the tenant-store delegation check runs
- **THEN** the check SHALL NOT fail for that migration

#### Scenario: Re-applying a delegated migration is a no-op

- **GIVEN** a tenant schema already in the shape a delegated migration's revision module produces
- **WHEN** that revision module's `statements(schema)` is executed against the schema again, whether via the Alembic migration's loop or via `migrate.py`
- **THEN** no error SHALL occur
- **AND** the schema's shape SHALL be unchanged

### Requirement: Tenant-scoped migrations also reach residency stores

A migration that changes a tenant-scoped table SHALL continue to propagate to every tenant schema on the platform database, and SHALL additionally be delivered to `tenant_owned` tenant stores as a tenant-store revision applied per store by the deploy migration step. Per-tenant-schema loops over `pg_namespace` on the platform database SHALL NOT be relied upon to reach residency tenants.

#### Scenario: A column added by migration reaches both planes

- **GIVEN** a `platform` tenant and a `ready` `tenant_owned` tenant
- **AND** a migration adds column `foo` to `tenant_template.some_table` with its tenant-store revision
- **WHEN** the deploy migration step runs
- **THEN** `tenant_<platform id>.some_table` on the platform database SHALL have column `foo`
- **AND** `tenant_<owned id>.some_table` in the tenant store SHALL have column `foo`
