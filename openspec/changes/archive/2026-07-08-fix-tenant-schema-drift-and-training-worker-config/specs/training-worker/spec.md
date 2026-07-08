## MODIFIED Requirements

### Requirement: Load annotated dataset

The worker SHALL load the tenant's annotated data by calling the annotation service's `GET /api/v1/annotation-export` endpoint, filtering for entity types in the tenant's configuration, and constructing a HuggingFace `Dataset` from the JSONL response. The worker SHALL resolve the annotation service's base URL from the `ANNOTATION_SERVICE_URL` environment variable, defaulting to `http://annotation_service:8000` (the annotation service's actual configured internal port) when the variable is unset.

#### Scenario: Dataset loads successfully

- **GIVEN** a tenant with annotated documents and a running annotation service
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the worker SHALL receive JSONL data with `tokens` and `tags` arrays
- **AND** the worker SHALL construct a `datasets.Dataset` from the response

#### Scenario: Export returns no data

- **GIVEN** a tenant with no annotated documents
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the worker SHALL fail the job with a clear error message
- **AND** the job status SHALL be "failed"

#### Scenario: Annotation service URL defaults to the correct internal port

- **GIVEN** the `ANNOTATION_SERVICE_URL` environment variable is not set
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the request SHALL be sent to `http://annotation_service:8000/api/v1/annotation-export`

#### Scenario: Annotation service URL is overridable via environment variable

- **GIVEN** the `ANNOTATION_SERVICE_URL` environment variable is set to `http://custom-host:9999`
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the request SHALL be sent to `http://custom-host:9999/api/v1/annotation-export`
