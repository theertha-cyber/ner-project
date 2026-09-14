## MODIFIED Requirements

### Requirement: Single-Command Local Stack Startup

The system SHALL provide a `docker-compose.yml` that starts every backend service — `gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`, `chat_api`, `analytics_service`, `celery_worker`, `celery_worker_extraction` — plus the `portal` frontend service, along with all infrastructure dependencies (`postgres-test`, `redis`, `minio`, `mlflow`) via a single `docker compose up` command.

#### Scenario: All services start with docker compose up

- **GIVEN** a valid `.env` file exists with all required secrets
- **WHEN** `docker compose up` is run from the project root
- **THEN** all application services (including `portal`) and infrastructure services SHALL start without error
- **AND** the gateway health endpoint at `http://localhost:8000/health` SHALL return `{"status": "ok"}`

#### Scenario: Individual service health endpoints respond

- **GIVEN** `docker compose up` has completed and all services are running
- **WHEN** each service health endpoint is called: `localhost:8000/health` (gateway), `localhost:8001/health` (document_service), `localhost:8002/health` (extraction_service), `localhost:8003/health` (training_service), `localhost:8004/health` (model_serving), `localhost:8005/health` (annotation_service)
- **THEN** every endpoint SHALL return HTTP 200 with `{"status": "ok"}`

#### Scenario: Portal serves the app via docker compose

- **GIVEN** `docker compose up` has completed
- **WHEN** a request is made to `http://localhost:3000`
- **THEN** the portal SHALL respond with HTTP 200 and render the app shell

### Requirement: Shared Root Dockerfile

The system SHALL provide a single multi-stage `Dockerfile` at the project root — a `builder` stage that installs all Python dependencies declared in `pyproject.toml` via Poetry, and a minimal runtime stage that copies only the installed dependencies and application source, exposing port `8000`. Each backend service in `docker-compose.yml` SHALL reference this root `Dockerfile` via `build.context: .` and `build.dockerfile: Dockerfile`, overriding `CMD` to launch its specific FastAPI application. No service SHALL reference `src/training_service/Dockerfile`, which SHALL NOT exist in the repository.

#### Scenario: All services built from shared Dockerfile

- **GIVEN** the root `Dockerfile` exists at the project root
- **WHEN** `docker compose build` is run
- **THEN** every application service image SHALL be built from the root `Dockerfile`
- **AND** no service SHALL reference `src/training_service/Dockerfile`
- **AND** `src/training_service/Dockerfile` SHALL NOT exist in the repository

#### Scenario: Service CMD overrides route to correct app module

- **GIVEN** the `gateway` compose service is defined with `command: uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000`
- **WHEN** the gateway container starts
- **THEN** the gateway SHALL bind to port `8000` internally and respond on host port `8000`

#### Scenario: Final image excludes build-only tooling

- **GIVEN** the root `Dockerfile`'s multi-stage build
- **WHEN** the final runtime stage image is inspected
- **THEN** Poetry and its installer SHALL NOT be present in the final image layer
- **AND** the application SHALL still start and serve requests using the dependencies installed in the `builder` stage

### Requirement: Stable Inter-Service Communication via Docker DNS

All inter-service HTTP calls within the compose network SHALL use Docker service names as hostnames (e.g., `http://document_service:8000`, `http://model_serving:8000`, `http://chat_api:8000`) rather than `localhost` or `host.docker.internal`. No service SHALL use `extra_hosts: host.docker.internal` or a `host.docker.internal` URL for calls to sibling services. Every application service that calls another application service SHALL have the corresponding `NER_*_URL` environment variable set in `docker-compose.yml` — a missing variable, even with a correct URL builder in code, falls back to the bare-metal `localhost` default and fails to connect from inside the container.

#### Scenario: Extraction worker reaches document_service via service name

- **GIVEN** the `celery_worker_extraction` service has `NER_DOCUMENT_SERVICE_URL=http://document_service:8000`
- **WHEN** the extraction worker performs an HTTP call to the document service
- **THEN** the call SHALL resolve to the `document_service` container without error
- **AND** the `extra_hosts` block with `host.docker.internal` SHALL not be present in `celery_worker_extraction`

#### Scenario: Extraction worker reaches model_serving via service name

- **GIVEN** the `celery_worker_extraction` service has `NER_MODEL_SERVING_URL=http://model_serving:8000`
- **WHEN** the extraction worker calls the model serving inference endpoint
- **THEN** the call SHALL resolve to the `model_serving` container without error

#### Scenario: Training service reaches model_serving for warmup via service name

- **GIVEN** the `training_service` compose block has `NER_MODEL_SERVING_URL=http://model_serving:8000`
- **WHEN** `training_service` promotes a model version and calls the model-serving warmup endpoint
- **THEN** the call SHALL resolve to the `model_serving` container without error
- **AND** the warmup call SHALL NOT fail with a connection error caused by falling back to the bare-metal `http://localhost:8004` default

#### Scenario: Model serving reaches training_service via service name at the correct internal port

- **GIVEN** the `model_serving` compose block has `NER_TRAINING_SERVICE_URL=http://training_service:8000`
- **WHEN** `model_serving` resolves a tenant's active model version or label list
- **THEN** the call SHALL resolve to the `training_service` container at its internal port `8000`, not the host-mapped port `8003`
- **AND** the call SHALL NOT fail with a connection error caused by targeting the wrong port

#### Scenario: Gateway reaches chat_api via service name

- **GIVEN** the `gateway` compose service has `NER_CHAT_API_URL=http://chat_api:8000`
- **WHEN** the gateway proxies a request to the chat API
- **THEN** the call SHALL resolve to the `chat_api` container without error
- **AND** the `gateway` service definition SHALL NOT reference `host.docker.internal`

## ADDED Requirements

### Requirement: Docker Build Context Hygiene

Every Docker build context in the repository SHALL be constrained by a `.dockerignore` file that excludes version control metadata (`.git`), secrets (`.env` and variants), dependency caches (`node_modules`, `__pycache__`, `.pytest_cache`, virtualenvs), and non-build data artifacts (e.g. `*.jsonl`, `*.pptx`) from the build context sent to the Docker daemon.

#### Scenario: Root build context excludes VCS and secrets

- **GIVEN** the root `.dockerignore` file
- **WHEN** `docker compose build` sends the build context for any backend service
- **THEN** `.git`, `.env`, `node_modules`, `**/__pycache__`, and `.pytest_cache` SHALL NOT be included in the context

#### Scenario: Portal build context excludes node_modules and build output

- **GIVEN** `src/portal/.dockerignore`
- **WHEN** `docker compose build portal` sends the build context
- **THEN** `node_modules` and `.next` (except what the Dockerfile explicitly stages) SHALL NOT be included in the context
