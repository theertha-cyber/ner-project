## ADDED Requirements

### Requirement: Postgres Data Persistence Across Compose Cycles

The `postgres-test` service SHALL mount a named Docker volume (`postgres-data`) at `/var/lib/postgresql/data` so that all database schemas, tables, and rows survive `docker compose down` / `docker compose up` cycles. The named volume SHALL be declared in the top-level `volumes` block of `docker-compose.yml` alongside `minio-data`.

#### Scenario: Database contents survive docker compose down and up

- **GIVEN** `docker compose up` has run, migrations have been applied, and at least one tenant row exists in the database
- **WHEN** `docker compose down` is run followed by `docker compose up`
- **THEN** all previously created schemas, tables, and rows SHALL still be present and queryable
- **AND** no manual migration or seed step SHALL be required

#### Scenario: Named volume is declared alongside minio-data

- **GIVEN** the `docker-compose.yml` file
- **WHEN** the top-level `volumes` block is inspected
- **THEN** both `minio-data` and `postgres-data` SHALL be declared as named volumes

#### Scenario: Explicit volume removal resets the database

- **GIVEN** the compose stack is stopped
- **WHEN** `docker compose down -v` is run
- **THEN** the `postgres-data` named volume SHALL be removed
- **AND** subsequent `docker compose up` SHALL start with a fresh empty database

---

### Requirement: Automated Database Initialization on Compose Up

The compose stack SHALL include a `db-init` one-shot service that automatically runs `alembic upgrade head` and `python -m src.gateway.seed` on every `docker compose up`, before any application service starts. The `db-init` service SHALL use `restart: "no"` and the shared root `Dockerfile` image with an overridden `command`. All application services that depend on the database schema — `gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction` — SHALL declare `depends_on: db-init: condition: service_completed_successfully`.

#### Scenario: Migrations are applied automatically on compose up

- **GIVEN** a valid `.env` file exists and `postgres-test` is healthy
- **WHEN** `docker compose up` is run from the project root
- **THEN** the `db-init` service SHALL run `alembic upgrade head` and exit with code 0 before any application service starts
- **AND** all Alembic migration versions SHALL be applied to `ner_dev`

#### Scenario: Seed admin is created automatically on compose up

- **GIVEN** `db-init` has run `alembic upgrade head` successfully
- **WHEN** `python -m src.gateway.seed` runs within `db-init`
- **THEN** the system tenant (`id = 'system'`) SHALL exist in `public.tenants`
- **AND** the system admin user (`admin@nerplatform.io`, role `system_admin`) SHALL exist in `public.tenant_users`

#### Scenario: Init is idempotent on subsequent compose up cycles

- **GIVEN** `docker compose up` has already run once and the database is fully initialised
- **WHEN** `docker compose down` and `docker compose up` are run again (without `-v`)
- **THEN** `db-init` SHALL complete successfully with exit code 0
- **AND** no duplicate tenants or admin users SHALL be created
- **AND** Alembic SHALL report that no new migrations need to be applied

#### Scenario: Application services wait for db-init to complete

- **GIVEN** `docker compose up` is run
- **WHEN** `db-init` is still running or has not yet exited
- **THEN** `gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, and `celery_worker_extraction` SHALL NOT start
- **AND** each of those services SHALL start only after `db-init` exits with code 0

#### Scenario: Stack startup fails fast if db-init fails

- **GIVEN** `db-init` exits with a non-zero exit code (e.g., due to a bad migration)
- **WHEN** `docker compose up` is running
- **THEN** all application services that depend on `db-init` SHALL not start
- **AND** the compose output SHALL display the `db-init` service logs indicating the failure
