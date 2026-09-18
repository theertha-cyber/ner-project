## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Tenant-scoped migrations also reach residency stores

A migration that changes a tenant-scoped table SHALL continue to propagate to every tenant schema on the platform database, and SHALL additionally be delivered to `tenant_owned` tenant stores as a tenant-store revision applied per store by the deploy migration step. Per-tenant-schema loops over `pg_namespace` on the platform database SHALL NOT be relied upon to reach residency tenants.

#### Scenario: A column added by migration reaches both planes

- **GIVEN** a `platform` tenant and a `ready` `tenant_owned` tenant
- **AND** a migration adds column `foo` to `tenant_template.some_table` with its tenant-store revision
- **WHEN** the deploy migration step runs
- **THEN** `tenant_<platform id>.some_table` on the platform database SHALL have column `foo`
- **AND** `tenant_<owned id>.some_table` in the tenant store SHALL have column `foo`
