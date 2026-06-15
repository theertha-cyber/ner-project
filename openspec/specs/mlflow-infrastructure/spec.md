# MLflow Infrastructure

## Purpose

Deploys and configures the MLflow Tracking Server for experiment tracking and model registry with tenant-isolated experiments and registered models.

---

## Requirements

### Requirement: MLflow Tracking Server deployment

The system SHALL deploy a standalone MLflow Tracking Server as part of the platform infrastructure. The server SHALL use PostgreSQL as the backend store and S3/MinIO as the artifact store.

#### Scenario: MLflow server starts and connects to backend stores

- **GIVEN** a PostgreSQL instance and an S3/MinIO bucket configured for MLflow
- **WHEN** the MLflow Tracking Server process starts
- **THEN** the server SHALL connect to the PostgreSQL backend store
- **AND** the server SHALL connect to the S3/MinIO artifact store
- **AND** the server SHALL expose the MLflow UI at the configured endpoint

#### Scenario: MLflow server health check

- **GIVEN** a running MLflow Tracking Server
- **WHEN** a health check request is sent to the configured endpoint
- **THEN** the server SHALL respond with 200 OK
- **AND** the response SHALL indicate backend store connectivity

### Requirement: Tenant isolation via naming convention

The Model Registry proxy SHALL enforce tenant isolation by using an MLflow naming convention. Each tenant SHALL have a dedicated experiment and registered model. The proxy SHALL reject cross-tenant access at the application layer.

#### Scenario: Tenant A creates a training run

- **GIVEN** an authenticated Tenant Admin from tenant A
- **WHEN** a training job completes and the Training Worker logs to MLflow
- **THEN** the run SHALL be logged under experiment `tenant_{tenant_a_id}`
- **AND** the registered model SHALL be named `tenant_{tenant_a_id}_ner_model`

#### Scenario: Tenant B cannot access Tenant A's models

- **GIVEN** a Tenant Admin from tenant B
- **WHEN** the admin lists models via the Model Registry proxy
- **THEN** the proxy SHALL scope the query to registered model `tenant_{tenant_b_id}_ner_model`
- **AND** Tenant A's models SHALL NOT be visible in the response

### Requirement: Docker Compose MLflow service

The docker-compose.yml SHALL include an MLflow Tracking Server service for local development.

#### Scenario: MLflow service available in dev environment

- **GIVEN** the docker-compose.yml file
- **WHEN** `docker compose up -d` is executed
- **THEN** the MLflow service SHALL start
- **AND** it SHALL use the PostgreSQL service as backend store
- **AND** it SHALL use the MinIO service as artifact store
- **AND** the UI SHALL be accessible at `http://localhost:5000`

### Requirement: MLflow environment configuration

The system SHALL expose the MLflow Tracking URI via environment variable `MLFLOW_TRACKING_URI` across all services that need it.

#### Scenario: Training Worker reads MLflow URI from environment

- **GIVEN** the MLflow Tracking Server is running at a known URI
- **WHEN** the Training Worker initializes an MLflow run
- **THEN** the worker SHALL read `MLFLOW_TRACKING_URI` from the environment
- **AND** SHALL connect to the specified server

### Requirement: K8s deployment manifests

The system SHALL provide Kubernetes deployment manifests for the MLflow Tracking Server for production environments.

#### Scenario: MLflow server deploys to K8s

- **GIVEN** a Kubernetes cluster with PostgreSQL and S3 access
- **WHEN** the MLflow deployment manifest is applied
- **THEN** a pod SHALL be created running the MLflow Tracking Server
- **AND** a Service SHALL expose it on port 5000
- **AND** a health probe SHALL be configured
