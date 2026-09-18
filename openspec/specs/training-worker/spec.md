# Training Worker

## Purpose

Celery worker that executes the HuggingFace fine-tuning pipeline: loads annotated datasets, tokenizes, trains `dslim/bert-base-NER`, saves artifacts to blob storage, and reports progress.

---

## Requirements

### Requirement: Celery worker initialisation

The system SHALL run a Celery worker process that consumes training jobs from a `training.jobs` queue. The worker SHALL be configured to connect to a Redis broker. The worker SHALL deserialise training job parameters and execute the HuggingFace training pipeline.

#### Scenario: Worker starts and connects to broker

- **GIVEN** a running Redis instance
- **WHEN** the Celery worker process starts
- **THEN** the worker SHALL connect to the Redis broker
- **AND** the worker SHALL register the `train_tenant_model` task

#### Scenario: Worker consumes a job from the queue

- **GIVEN** a submitted training job in "queued" status
- **WHEN** the Celery worker picks up the job
- **THEN** the training job's status SHALL be updated to "running"
- **AND** `started_at` SHALL be recorded

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

### Requirement: Fine-tune the model

The worker SHALL load `dslim/bert-base-NER`, configure the HuggingFace `Trainer` with the tenant's hyperparameters (learning_rate, num_epochs, batch_size, max_seq_length), train on the tokenised dataset, and evaluate on a 10% validation split.

#### Scenario: Training runs to completion

- **GIVEN** a tokenised dataset with at least 100 examples
- **WHEN** the `Trainer.train()` method executes
- **THEN** training SHALL run for the specified `num_epochs`
- **AND** the model SHALL be checkpointed after each epoch
- **AND** the final model SHALL be saved to blob storage at `tenants/{tid}/models/v{version}/`

#### Scenario: Training produces evaluation metrics

- **GIVEN** a trained model
- **WHEN** the `Trainer.evaluate()` method runs
- **THEN** the evaluation result SHALL contain `eval_loss`, `eval_precision`, `eval_recall`, and `eval_f1`
- **AND** these metrics SHALL be persisted to the `training_jobs` record

### Requirement: Save model artifacts

The worker SHALL persist model artifacts (config.json, model.safetensors, tokenizer files, training_args.json, and model.onnx) to blob storage after training completes. The artifact path SHALL follow `tenants/{tid}/models/v{version}/` convention. The worker SHALL include the trained model's `label_list` (the ordered list of BIO labels used during training, e.g., `["O", "B-company", "B-contact_details", ...]`) in the `model_versions.metrics` JSONB column under the key `label_list`.

#### Scenario: Artifacts are stored after training

- **GIVEN** a completed training run
- **WHEN** the worker saves the model and tokenizer
- **THEN** `model.safetensors`, `config.json`, `tokenizer.json`, `vocab.txt`, `training_args.json`, `metrics.json`, and `model.onnx` SHALL exist at the artifact path
- **AND** the `model_versions` table SHALL have a new row with `version_number`, `status`: `"training"`, and `artifact_path`
- **AND** after job progress is persisted, `model_versions.status` SHALL be `"completed"`

#### Scenario: label_list is persisted in model version metrics

- **GIVEN** a completed training run with entity types ["company", "contact_details", "programming_language"]
- **WHEN** the worker writes the model_versions row
- **THEN** `metrics.label_list` SHALL contain `["O", "B-company", "I-company", "B-contact_details", "I-contact_details", "B-programming_language", "I-programming_language"]`
- **AND** the label_list SHALL include all BIO tags extracted from the annotated dataset

#### Scenario: Artifact path uses version number not UUID

- **GIVEN** a training run that produces version_number 5 for tenant `abc-123`
- **WHEN** the worker saves artifacts to blob storage
- **THEN** the artifact path SHALL be `tenants/abc-123/models/v5/`
- **AND** the path SHALL NOT contain a UUID subdirectory

### Requirement: Handle training failure

The worker SHALL catch exceptions during training, update the job status to "failed" with the error message, and not persist partial model artifacts.

#### Scenario: Worker catches training exception

- **GIVEN** a training run that encounters an error (e.g., OOM, dataset schema mismatch)
- **WHEN** the worker catches the exception
- **THEN** the job status SHALL be updated to "failed"
- **AND** `error_message` SHALL contain the exception details
- **AND** no partial model artifacts SHALL be persisted to the model registry

#### Scenario: Failed job sets model_versions to failed

- **GIVEN** a training run where artifacts were saved and a `model_versions` row was created with `status='training'`
- **WHEN** `_update_job_progress` or `mlflow.end_run` fails
- **THEN** the worker's exception handler SHALL update `model_versions.status` to `"failed"`
- **AND** `training_jobs.status` SHALL be `"failed"`
- **AND** the MLflow run status SHALL be `FAILED`

### Requirement: Update job progress during training

The worker SHALL periodically report training progress (current epoch, current loss) to the Celery result backend and persist it to the `training_jobs` table so the status endpoint can return live progress. `_update_job_progress` SHALL JSON-serialize any Python dict values in its `**fields` before passing them to the SQL UPDATE statement, to prevent `psycopg2.ProgrammingError: can't adapt type 'dict'` when `metrics` or similar nested fields are passed.

#### Scenario: Progress is reported during training

- **GIVEN** a training job in "running" status with 3 epochs
- **WHEN** the worker completes epoch 1
- **THEN** `GET /api/v1/training-jobs/{job_id}` SHALL return `current_epoch`: 1 and the loss value for that epoch
- **AND** `current_epoch` SHALL update as each epoch completes

### Requirement: Log training run to MLflow Tracking

The Training Worker SHALL initialize an MLflow run at the start of each training job. The worker SHALL log hyperparameters, per-epoch evaluation metrics, and the trained model artifacts to the MLflow server. The worker SHALL use MLflow client version 2.x (compatible with the MLflow server v2.20.0).

#### Scenario: MLflow run starts when training begins

- **GIVEN** a Celery training task executing for a tenant
- **WHEN** the task begins fine-tuning
- **THEN** a new MLflow run SHALL be created under experiment `tenant_{tid}`
- **AND** the training hyperparameters SHALL be logged via `mlflow.log_params()`
- **AND** the base model name and hash SHALL be logged as tags
- **AND** the dataset version and entity config version SHALL be logged as tags

#### Scenario: Per-epoch metrics are logged to MLflow

- **GIVEN** an active MLflow run during training
- **WHEN** each epoch completes
- **THEN** the metrics `train_loss`, `eval_loss`, `eval_precision`, `eval_recall`, and `eval_f1` SHALL be logged via `mlflow.log_metrics()`
- **AND** per-entity-type precision, recall, and F1 SHALL be logged as nested metrics (e.g., `invoice_number_f1`)

#### Scenario: Model artifacts are logged on completion

- **GIVEN** a completed training run
- **WHEN** the model is saved and converted to ONNX
- **THEN** the model artifacts SHALL be logged via `mlflow.transformers.log_model()`
- **AND** the registered model name SHALL be `tenant_{tid}_ner_model`
- **AND** the MLflow run ID SHALL be persisted to the `training_jobs` record as `mlflow_run_id`
- **AND** the MLflow client version SHALL be 2.x, matching the MLflow server version

#### Scenario: Training failure logs error to MLflow

- **GIVEN** a training run that encounters a failure
- **WHEN** the worker catches the exception
- **THEN** the MLflow run status SHALL be set to `FAILED`
- **AND** the error message SHALL be logged as a tag `error_message`
