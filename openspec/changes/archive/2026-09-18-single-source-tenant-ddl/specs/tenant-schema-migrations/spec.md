## ADDED Requirements

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
