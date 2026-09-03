## MODIFIED Requirements

### Requirement: Tokenize dataset

The worker SHALL tokenize the dataset using the `dslim/bert-base-NER` tokeniser, aligning BIO tags to subword tokens via the `label_all_tokens=True` strategy from HuggingFace's token classification utilities.

The worker's default `max_seq_length` SHALL be large enough that a record produced by the annotation export's window budget expands to subword tokens without truncation. `max_seq_length` SHALL remain a caller-supplied hyperparameter settable through the existing approval-time hyperparameter path, and SHALL NOT be hardcoded.

The worker SHALL detect when a record's subword expansion exceeds `max_seq_length` and SHALL record that occurrence, rather than silently discarding the overflow. Truncation SHALL be an observable event, not an invisible default.

#### Scenario: Tokens are aligned to subwords

- **GIVEN** a dataset with tokens `["John", "smith"]` and tags `["B-PER", "I-PER"]`
- **WHEN** the worker tokenises with `max_seq_length=128`
- **THEN** each token SHALL be mapped to its subword tokens
- **AND** the label for the first subword SHALL be the original tag, and subsequent subwords SHALL receive -100 (ignored in loss computation)

#### Scenario: A window-sized record is not truncated at the default sequence length

- **GIVEN** a dataset record containing the maximum number of source tokens permitted by the export window budget
- **WHEN** the worker tokenises it using the default `max_seq_length`
- **THEN** no token of that record SHALL be truncated
- **AND** every source token SHALL have at least one corresponding subword label

#### Scenario: max_seq_length remains overridable per job

- **GIVEN** a training job whose approved hyperparameters set `max_seq_length` to a value other than the default
- **WHEN** the worker tokenises the dataset
- **THEN** the worker SHALL use the supplied value, not the default

#### Scenario: Truncation is recorded when it occurs

- **GIVEN** a dataset containing a record whose subword expansion exceeds the configured `max_seq_length`
- **WHEN** the worker tokenises the dataset
- **THEN** the worker SHALL record that truncation occurred, including how many records were affected
- **AND** the job SHALL NOT fail solely because truncation occurred

### Requirement: Load annotated dataset

The worker SHALL load the tenant's annotated data by calling the annotation service's `GET /api/v1/annotation-export` endpoint, filtering for entity types in the tenant's configuration, and constructing a HuggingFace `Dataset` from the JSONL response. The worker SHALL resolve the annotation service's base URL from the `ANNOTATION_SERVICE_URL` environment variable, defaulting to `http://annotation_service:8000` (the annotation service's actual configured internal port) when the variable is unset.

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
