## ADDED Requirements

### Requirement: Extraction worker deployment

The system SHALL deploy a Celery worker process that consumes tasks from the `extraction` queue. The worker SHALL run the `extraction_service` Celery app and SHALL be configured alongside the existing training worker in `docker-compose.yml`.

#### Scenario: Worker connects and processes an extraction task

- **GIVEN** Redis is running and the `extraction` queue exists
- **WHEN** the extraction worker starts with `celery -A src.extraction_service.celery_app worker -Q extraction --pool=solo`
- **THEN** the worker SHALL connect to Redis and log a `ready` message
- **AND** the worker SHALL be subscribed to the `extraction` queue

#### Scenario: Batch extraction task is consumed

- **GIVEN** the extraction worker is running and connected
- **WHEN** a `run_batch_extraction` task is sent to the `extraction` queue
- **THEN** the worker SHALL receive the task and begin processing
- **AND** the extraction run SHALL transition from "queued" to "running" to "completed"
