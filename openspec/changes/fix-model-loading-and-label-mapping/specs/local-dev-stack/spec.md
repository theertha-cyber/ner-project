## MODIFIED Requirements

### Requirement: Stable Inter-Service Communication via Docker DNS

All inter-service HTTP calls within the compose network SHALL use Docker service names as hostnames (e.g., `http://document_service:8000`, `http://model_serving:8000`) rather than `localhost` or `host.docker.internal`. No service SHALL use `extra_hosts: host.docker.internal` for calls to sibling services. Every application service that calls another application service SHALL have the corresponding `NER_*_URL` environment variable set in `docker-compose.yml` — a missing variable, even with a correct URL builder in code, falls back to the bare-metal `localhost` default and fails to connect from inside the container.

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
