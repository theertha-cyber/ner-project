## MODIFIED Requirements

### Requirement: Single-Command Local Stack Startup

The system SHALL provide a `docker-compose.yml` that starts every backend service — `gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction` — along with all infrastructure dependencies (`postgres-test`, `redis`, `minio`, `mlflow`) and the local observability stack (`otel-collector`, `grafana`) via a single `docker compose up` command.

#### Scenario: All services start with docker compose up

- **GIVEN** a valid `.env` file exists with all required secrets
- **WHEN** `docker compose up` is run from the project root
- **THEN** all eight application services, four infrastructure services and two observability services SHALL start without error
- **AND** the gateway health endpoint at `http://localhost:8000/health` SHALL return `{"status": "ok"}`

#### Scenario: Individual service health endpoints respond

- **GIVEN** `docker compose up` has completed and all services are running
- **WHEN** each service health endpoint is called: `localhost:8000/health` (gateway), `localhost:8001/health` (document_service), `localhost:8002/health` (extraction_service), `localhost:8003/health` (training_service), `localhost:8004/health` (model_serving), `localhost:8005/health` (annotation_service)
- **THEN** every endpoint SHALL return HTTP 200 with `{"status": "ok"}`

#### Scenario: Observability stack is reachable

- **GIVEN** `docker compose up` has completed
- **WHEN** the Grafana root URL is requested
- **THEN** it SHALL return HTTP 200
- **AND** the OTLP endpoint exposed by `otel-collector` SHALL accept an export from a running service without error

#### Scenario: Stack starts when the observability services are unavailable

- **GIVEN** the `otel-collector` container is stopped
- **WHEN** a request is made to any running application service
- **THEN** the request SHALL be served normally
- **AND** the service SHALL NOT fail its health check because telemetry export is failing
