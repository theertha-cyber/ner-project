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

The worker SHALL load the tenant's annotated data by calling the annotation service's `GET /api/v1/annotation-export` endpoint, filtering for entity types in the tenant's configuration, and constructing a HuggingFace `Dataset` from the JSONL response.

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

### Requirement: Tokenize dataset

The worker SHALL tokenize the dataset using the `dslim/bert-base-NER` tokeniser, aligning BIO tags to subword tokens via the `label_all_tokens=True` strategy from HuggingFace's token classification utilities.

#### Scenario: Tokens are aligned to subwords

- **GIVEN** a dataset with tokens `["John", "smith"]` and tags `["B-PER", "I-PER"]`
- **WHEN** the worker tokenises with `max_seq_length=128`
- **THEN** each token SHALL be mapped to its subword tokens
- **AND** the label for the first subword SHALL be the original tag, and subsequent subwords SHALL receive -100 (ignored in loss computation)

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

The worker SHALL persist model artifacts (config.json, model.safetensors, tokenizer files, training_args.json) to blob storage after training completes. The artifact path SHALL follow `tenants/{tid}/models/v{version}/` convention.

#### Scenario: Artifacts are stored after training

- **GIVEN** a completed training run
- **WHEN** the worker saves the model and tokenizer
- **THEN** `model.safetensors`, `config.json`, `tokenizer.json`, `vocab.txt`, `training_args.json`, and `metrics.json` SHALL exist at the artifact path
- **AND** the `model_versions` table SHALL have a new row with `version_number`, `status`: "completed", and `artifact_path`

### Requirement: Handle training failure

The worker SHALL catch exceptions during training, update the job status to "failed" with the error message, and not persist partial model artifacts.

#### Scenario: Worker catches training exception

- **GIVEN** a training run that encounters an error (e.g., OOM, dataset schema mismatch)
- **WHEN** the worker catches the exception
- **THEN** the job status SHALL be updated to "failed"
- **AND** `error_message` SHALL contain the exception details
- **AND** no partial model artifacts SHALL be persisted to the model registry

### Requirement: Update job progress during training

The worker SHALL periodically report training progress (current epoch, current loss) to the Celery result backend and persist it to the `training_jobs` table so the status endpoint can return live progress.

#### Scenario: Progress is reported during training

- **GIVEN** a training job in "running" status with 3 epochs
- **WHEN** the worker completes epoch 1
- **THEN** `GET /api/v1/training-jobs/{job_id}` SHALL return `current_epoch`: 1 and the loss value for that epoch
- **AND** `current_epoch` SHALL update as each epoch completes

### Requirement: Log training run to MLflow Tracking

The Training Worker SHALL initialize an MLflow run at the start of each training job. The worker SHALL log hyperparameters, per-epoch evaluation metrics, and the trained model artifacts to the MLflow server.

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
- **WHEN** the model is saved
- **THEN** the model artifacts SHALL be logged via `mlflow.transformers.log_model()`
- **AND** the registered model name SHALL be `tenant_{tid}_ner_model`
- **AND** the MLflow run ID SHALL be persisted to the `training_jobs` record as `mlflow_run_id`

#### Scenario: Training failure logs error to MLflow

- **GIVEN** a training run that encounters a failure
- **WHEN** the worker catches the exception
- **THEN** the MLflow run status SHALL be set to `FAILED`
- **AND** the error message SHALL be logged as a tag `error_message`
