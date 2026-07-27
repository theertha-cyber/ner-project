## ADDED Requirements

### Requirement: Documented clean-rebuild procedure for the local stack

The project SHALL document a single, ordered procedure that rebuilds the local development environment from a clean state: rebuild Docker images, remove the `postgres-data` volume, apply the full Alembic migration chain to an empty database, and seed. The procedure SHALL state explicitly that it destroys all local database contents, and SHALL be the documented remedy for a drifted local database.

#### Scenario: Operator follows the documented procedure on a drifted database

- **GIVEN** a local `ner_dev` database whose schema does not match the Alembic migration chain
- **WHEN** an operator follows the documented clean-rebuild procedure to completion
- **THEN** the `postgres-data` volume SHALL have been removed and recreated
- **AND** `alembic_version` SHALL equal the head revision of the migration chain
- **AND** every schema object declared by the migration chain SHALL exist with the shape the chain declares

#### Scenario: The procedure declares its destructive effect before any step runs

- **GIVEN** the documented procedure
- **WHEN** it is read
- **THEN** it SHALL state, before the first command, that all local tenants, users, documents, annotations, model versions, and training runs are permanently destroyed

#### Scenario: Images are rebuilt before migrations run

- **GIVEN** a working tree containing migration revisions newer than those baked into the current container images
- **WHEN** the clean-rebuild procedure is followed
- **THEN** `docker compose build` SHALL run before the stack is started
- **AND** the migration chain applied by `db-init` SHALL include every revision present in the working tree's `alembic/versions/` directory

### Requirement: Post-migration schema verification

The system SHALL provide a verification step, runnable as part of `db-init` after `alembic upgrade head`, that compares the live database's schema against what the migration chain declares and reports any drift. Verification SHALL check that `public` tables have the columns the chain declares, that `tenant_template` contains every tenant-scoped table the chain declares, and that every provisioned `tenant_<id>` schema matches `tenant_template`'s table set. Drift SHALL cause the verification step to exit non-zero.

#### Scenario: A clean rebuild passes verification

- **GIVEN** a database freshly built by applying the full migration chain to an empty database
- **WHEN** the verification step runs
- **THEN** it SHALL report no drift
- **AND** it SHALL exit with code 0

#### Scenario: A missing public column is detected

- **GIVEN** a database whose `public.entity_definitions` table is missing the `validation_rule` column that the migration chain declares
- **WHEN** the verification step runs
- **THEN** it SHALL report `public.entity_definitions` as drifted, naming the missing column
- **AND** it SHALL exit non-zero

#### Scenario: A missing tenant_template table is detected

- **GIVEN** a database whose `tenant_template` schema is missing the `documents` table
- **WHEN** the verification step runs
- **THEN** it SHALL report `tenant_template.documents` as missing
- **AND** it SHALL exit non-zero

#### Scenario: A tenant schema that lags the template is detected

- **GIVEN** a provisioned tenant schema `tenant_<id>` that is missing a table present in `tenant_template`
- **WHEN** the verification step runs
- **THEN** it SHALL report that tenant schema and the missing table
- **AND** it SHALL exit non-zero

### Requirement: Drift blocks stack startup

When schema verification detects drift during `db-init`, the `db-init` service SHALL exit non-zero so that application services declaring `depends_on: db-init: condition: service_completed_successfully` do not start. A drifted database SHALL NOT be able to bring up a running stack that fails later at request time.

#### Scenario: Application services do not start on a drifted database

- **GIVEN** a database with schema drift that verification detects
- **WHEN** `docker compose up` is run
- **THEN** `db-init` SHALL exit non-zero
- **AND** `gateway`, `document_service`, `extraction_service`, `annotation_service`, and `training_service` SHALL NOT start
- **AND** the `db-init` logs SHALL name the drifted objects

#### Scenario: A clean database starts the stack normally

- **GIVEN** a database that passes schema verification
- **WHEN** `docker compose up` is run
- **THEN** `db-init` SHALL exit with code 0
- **AND** all application services SHALL start as they do today
