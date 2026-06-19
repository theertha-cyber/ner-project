# Local Development Stack

## Purpose

Defines how the platform's backend services are containerised and orchestrated for local development using Docker Compose, enabling single-command startup of all services and their infrastructure dependencies.

---

## Requirements

### Requirement: Single-Command Local Stack Startup

The system SHALL provide a `docker-compose.yml` that starts every backend service — `gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction` — along with all infrastructure dependencies (`postgres-test`, `redis`, `minio`, `mlflow`) via a single `docker compose up` command.

#### Scenario: All services start with docker compose up

- **GIVEN** a valid `.env` file exists with all required secrets
- **WHEN** `docker compose up` is run from the project root
- **THEN** all eight application services and four infrastructure services SHALL start without error
- **AND** the gateway health endpoint at `http://localhost:8000/health` SHALL return `{"status": "ok"}`

#### Scenario: Individual service health endpoints respond

- **GIVEN** `docker compose up` has completed and all services are running
- **WHEN** each service health endpoint is called: `localhost:8000/health` (gateway), `localhost:8001/health` (document_service), `localhost:8002/health` (extraction_service), `localhost:8003/health` (training_service), `localhost:8004/health` (model_serving), `localhost:8005/health` (annotation_service)
- **THEN** every endpoint SHALL return HTTP 200 with `{"status": "ok"}`

### Requirement: Shared Root Dockerfile

The system SHALL provide a single `Dockerfile` at the project root that installs all Python dependencies declared in `pyproject.toml` and exposes port `8000`. Each service in `docker-compose.yml` SHALL reference this root `Dockerfile` via `build.context: .` and `build.dockerfile: Dockerfile`, overriding `CMD` to launch its specific FastAPI application.

#### Scenario: All services built from shared Dockerfile

- **GIVEN** the root `Dockerfile` exists at the project root
- **WHEN** `docker compose build` is run
- **THEN** every application service image SHALL be built from the root `Dockerfile`
- **AND** no service SHALL reference `src/training_service/Dockerfile`

#### Scenario: Service CMD overrides route to correct app module

- **GIVEN** the `gateway` compose service is defined with `command: uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000`
- **WHEN** the gateway container starts
- **THEN** the gateway SHALL bind to port `8000` internally and respond on host port `8000`

### Requirement: Stable Inter-Service Communication via Docker DNS

All inter-service HTTP calls within the compose network SHALL use Docker service names as hostnames (e.g., `http://document_service:8000`, `http://model_serving:8000`) rather than `localhost` or `host.docker.internal`. No service SHALL use `extra_hosts: host.docker.internal` for calls to sibling services.

#### Scenario: Extraction worker reaches document_service via service name

- **GIVEN** the `celery_worker_extraction` service has `NER_DOCUMENT_SERVICE_URL=http://document_service:8000`
- **WHEN** the extraction worker performs an HTTP call to the document service
- **THEN** the call SHALL resolve to the `document_service` container without error
- **AND** the `extra_hosts` block with `host.docker.internal` SHALL not be present in `celery_worker_extraction`

#### Scenario: Extraction worker reaches model_serving via service name

- **GIVEN** the `celery_worker_extraction` service has `NER_MODEL_SERVING_URL=http://model_serving:8000`
- **WHEN** the extraction worker calls the model serving inference endpoint
- **THEN** the call SHALL resolve to the `model_serving` container without error

### Requirement: Application Service Port Mapping

Each application service SHALL map a unique host port to internal container port `8000` following the convention: gateway → `8000`, document_service → `8001`, extraction_service → `8002`, training_service → `8003`, model_serving → `8004`, annotation_service → `8005`.

#### Scenario: Services are reachable on distinct host ports

- **GIVEN** `docker compose up` is running
- **WHEN** a developer calls `curl http://localhost:<port>/health` for each assigned port
- **THEN** each SHALL return HTTP 200 from the corresponding service
- **AND** no two services SHALL share the same host port

### Requirement: Service Startup Dependencies

Application services that require database or message broker access SHALL declare `depends_on` conditions in `docker-compose.yml` so that infrastructure services are healthy before the application container starts.

#### Scenario: Gateway waits for postgres to be healthy

- **GIVEN** `docker compose up` is run
- **WHEN** the `gateway` service container starts
- **THEN** it SHALL not begin before `postgres-test` passes its `pg_isready` healthcheck

#### Scenario: Celery workers wait for postgres and redis

- **GIVEN** `docker compose up` is run
- **WHEN** `celery_worker` and `celery_worker_extraction` containers start
- **THEN** both SHALL wait for `postgres-test` (healthy) and `redis` (healthy) before starting

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
