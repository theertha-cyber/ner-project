## Purpose

Defines how the extraction worker resolves network addresses for dependent services (document service, model serving). Covers environment-variable-driven URL configuration with defaults for local development and overrides for Docker container contexts.

## Requirements

### Requirement: Worker host service connectivity

The extraction worker SHALL be configurable to reach the document service and model serving layer via environment-variable-driven URLs, with defaults that work for local development and overrides for the Docker container context.

#### Scenario: Worker processes a batch document from Docker

- **GIVEN** the extraction worker is running in the Docker container
- **AND** `NER_DOCUMENT_SERVICE_URL` is set to `http://host.docker.internal:8001`
- **AND** `NER_MODEL_SERVING_URL` is set to `http://host.docker.internal:8004`
- **WHEN** a batch extraction task processes a document
- **THEN** the worker successfully fetches document text from the document service
- **AND** the worker successfully sends inference requests to the model serving layer
- **AND** the extraction run completes with `processed_count=1` and `failed_count=0`
