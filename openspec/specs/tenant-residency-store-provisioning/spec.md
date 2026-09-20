# tenant-residency-store-provisioning Specification

## Purpose

TBD - created by syncing change tenant-postgresql-data-plane.

## Requirements

### Requirement: Activating a data-plane connection provisions the tenant schema in the tenant store

When a `tenant_owned` tenant's `azure_postgresql_data_plane` connection becomes active and the tenant is in `awaiting_store` or `provisioning_failed`, the system SHALL set the tenant to `provisioning` and run a durable, idempotent background provisioning task that, against the tenant store: creates the `vector` extension if absent, creates schema `tenant_<id>`, applies the tenant-store schema baseline and every later tenant-store revision in order, creates or verifies the chat query role and its grants, reconciles generated entity tables from the tenant's active entity definitions, and writes a store identity marker and the applied revision to `tenant_<id>.platform_store_meta`. On success the tenant SHALL become `ready`. On failure the tenant SHALL become `provisioning_failed` with a finite safe reason class, and the tenant administrator SHALL be able to retry provisioning.

#### Scenario: Successful provisioning makes the tenant ready

- **GIVEN** a `tenant_owned` tenant in `awaiting_store` and a reachable empty tenant store
- **WHEN** the tenant administrator activates its data-plane connection
- **THEN** the tenant SHALL enter `provisioning` and then `ready`
- **AND** the tenant store SHALL contain `tenant_<id>` with every table, index, generated column, and materialized view present in the platform tenant template at the same revision
- **AND** `platform_store_meta` SHALL record the store identity and the applied revision

#### Scenario: Provisioning failure is safe and retryable

- **GIVEN** a tenant store where schema creation fails part-way
- **WHEN** provisioning runs
- **THEN** the tenant SHALL enter `provisioning_failed` with a finite safe reason class
- **AND** a retry SHALL complete provisioning without error on the objects that already exist

#### Scenario: Provisioning refuses a non-empty foreign schema

- **GIVEN** a tenant store that already contains a `tenant_<id>` schema with tables but no matching store identity marker
- **WHEN** provisioning runs
- **THEN** it SHALL stop with reason class `target_schema_not_empty`
- **AND** it SHALL NOT alter or drop any existing object

#### Scenario: No platform schema is created for a residency tenant

- **GIVEN** a `tenant_owned` tenant that has been provisioned
- **WHEN** the platform database is inspected
- **THEN** no `tenant_<id>` schema for that tenant SHALL exist on the platform database

### Requirement: Tenant-store schema is defined by a versioned baseline and ordered revisions

The system SHALL define the tenant schema for tenant stores as a checked-in baseline, parameterised by schema name, equal to the platform `tenant_template` shape at the baseline Alembic revision, followed by ordered, idempotent tenant-store revisions. Every Alembic migration that changes a tenant-scoped table SHALL ship a corresponding tenant-store revision. An automated test SHALL fail when the tenant schema produced by applying the baseline and all revisions to an empty database differs in tables, columns, types, defaults, constraints, indexes, generated columns, or materialized views from `tenant_template` after `alembic upgrade head`.

#### Scenario: Missing tenant-store revision fails the build

- **GIVEN** a new Alembic migration that adds a column to `tenant_template.documents`
- **AND** no corresponding tenant-store revision
- **WHEN** the tenant-store parity test runs
- **THEN** the test SHALL fail naming the differing table and column

#### Scenario: Re-applying a revision is a no-op

- **GIVEN** a tenant store already at revision N
- **WHEN** revision N is applied again
- **THEN** no error SHALL occur and the schema shape SHALL be unchanged

### Requirement: Pending tenant-store revisions are applied per store on deploy

The deploy migration step SHALL, after `alembic upgrade head` on the platform database, apply pending tenant-store revisions to every `tenant_owned` tenant whose status is `ready` or `migration_required` and update the recorded revision. The platform SHALL declare a minimum supported tenant-store revision. A tenant whose store is below it, or whose migration fails, SHALL become `migration_required` with a safe reason class and SHALL fail closed for content routes until a later run succeeds. A failure for one store SHALL NOT prevent other stores from being migrated or the platform from starting.

#### Scenario: Deploy upgrades a residency store

- **GIVEN** a `ready` residency tenant at revision N and a deploy containing revision N+1
- **WHEN** the deploy migration step runs
- **THEN** the store SHALL be at revision N+1 and the tenant SHALL remain `ready`

#### Scenario: Unreachable store during deploy is isolated

- **GIVEN** two residency tenants, one with an unreachable store, and a deploy whose minimum supported revision is N+1
- **WHEN** the deploy migration step runs
- **THEN** the reachable store SHALL be upgraded
- **AND** the unreachable tenant SHALL become `migration_required`
- **AND** platform services SHALL start normally

### Requirement: Replacement connections must point at the same store

The system SHALL permit replacing an active data-plane connection only when the replacement's connection test reads the store identity marker in `tenant_<id>.platform_store_meta` and it equals the identity recorded at provisioning. A replacement that reaches a different or unmarked store SHALL fail its test with reason class `store_identity_mismatch` and SHALL NOT be activatable.

#### Scenario: Credential rotation keeps the tenant ready

- **GIVEN** a `ready` residency tenant and a replacement draft with a new secret reference pointing at the same store
- **WHEN** the replacement is tested and activated
- **THEN** the tenant SHALL remain `ready` without re-provisioning
- **AND** the resolver SHALL use the replacement connection

#### Scenario: Pointing at a different server is rejected

- **GIVEN** a `ready` residency tenant and a replacement draft pointing at a different server
- **WHEN** the replacement is tested
- **THEN** the test outcome SHALL be failed with reason class `store_identity_mismatch`
