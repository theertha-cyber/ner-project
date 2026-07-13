## MODIFIED Requirements

### Requirement: Save model artifacts

The worker SHALL persist model artifacts (config.json, model.safetensors, tokenizer files, training_args.json, and model.onnx) to blob storage after training completes. The artifact path SHALL follow `tenants/{tid}/models/v{version}/` convention.

#### Scenario: Artifacts are stored after training

- **GIVEN** a completed training run
- **WHEN** the worker saves the model and tokenizer
- **THEN** `model.safetensors`, `config.json`, `tokenizer.json`, `vocab.txt`, `training_args.json`, `metrics.json`, and `model.onnx` SHALL exist at the artifact path
- **AND** the `model_versions` table SHALL have a new row with `version_number`, `status`: "completed", and `artifact_path`

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
