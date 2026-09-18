## MODIFIED Requirements

### Requirement: Load annotated dataset

The worker SHALL load the tenant's annotated data by calling the annotation service's `GET /api/v1/annotation-export` endpoint, filtering for entity types in the tenant's configuration, and constructing a HuggingFace `Dataset` from the JSONL response. The worker SHALL resolve the annotation service's base URL from the `ANNOTATION_SERVICE_URL` environment variable, defaulting to `http://annotation_service:8000` (the annotation service's actual configured internal port) when the variable is unset.

The worker SHALL read the job's stored `source_scope` and pass it through to the export call as the `source` query parameter, so the dataset the worker trains on matches the same workflow the submission's entity-count gate was scoped to. A job with no `source_scope` SHALL call the export endpoint with no `source` parameter, combining every source as before this field existed.

The worker SHALL fail the job with a clear error when the loaded dataset cannot form a train/evaluation split containing at least one evaluation row. This guard SHALL be mechanical only; the worker SHALL NOT apply any additional judgement about whether the dataset is large enough to train a good model, which is governed separately by the per-entity-type dataset readiness threshold.

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

#### Scenario: Dataset too small to form an evaluation split

- **GIVEN** a tenant whose export yields a dataset so small that the configured split produces zero evaluation rows
- **WHEN** the worker prepares the train/evaluation split
- **THEN** the worker SHALL fail the job with a clear error naming the row count
- **AND** the job status SHALL be "failed"
- **AND** the worker SHALL NOT train on the dataset or report an evaluation metric

#### Scenario: Dataset large enough to split proceeds

- **GIVEN** a tenant whose export yields a dataset that produces at least one evaluation row under the configured split
- **WHEN** the worker prepares the train/evaluation split
- **THEN** the worker SHALL proceed to training
- **AND** the worker SHALL NOT apply any additional minimum-size judgement of its own

#### Scenario: Annotation service URL defaults to the correct internal port

- **GIVEN** the `ANNOTATION_SERVICE_URL` environment variable is not set
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the request SHALL be sent to `http://annotation_service:8000/api/v1/annotation-export`

#### Scenario: Annotation service URL is overridable via environment variable

- **GIVEN** the `ANNOTATION_SERVICE_URL` environment variable is set to `http://custom-host:9999`
- **WHEN** the worker calls the annotation export endpoint
- **THEN** the request SHALL be sent to `http://custom-host:9999/api/v1/annotation-export`

#### Scenario: The job's source_scope is forwarded to the export call

- **GIVEN** a training job whose stored `source_scope` is `"automated"`
- **WHEN** the worker loads the annotated dataset for that job
- **THEN** the export request SHALL include `source=automated` as a query parameter

#### Scenario: A job with no source_scope combines every source

- **GIVEN** a training job whose stored `source_scope` is `NULL`
- **WHEN** the worker loads the annotated dataset for that job
- **THEN** the export request SHALL include no `source` query parameter
