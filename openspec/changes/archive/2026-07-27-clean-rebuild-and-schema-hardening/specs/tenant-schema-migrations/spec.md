## ADDED Requirements

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
