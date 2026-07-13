## ADDED Requirements

### Requirement: MLflow client-server version compatibility

The test script SHALL verify that the MLflow client version installed in the training worker is compatible with the MLflow server version.

#### Scenario: MLflow client version matches server version range

- **GIVEN** the MLflow server is running version 2.20.0
- **WHEN** the client creates a registered model and logs a model via `mlflow.transformers.log_model()`
- **THEN** the call SHALL succeed without a 404 error
- **AND** the registered model SHALL be visible via `MlflowClient.get_registered_model()`

### Requirement: ONNX artifact completeness

The test script SHALL verify that training produces a valid ONNX file in the artifact output.

#### Scenario: ONNX file exists in exported artifacts

- **GIVEN** a completed (or mocked) training run
- **WHEN** the model artifacts are exported to a temp directory
- **THEN** a file matching `*.onnx` SHALL exist in the artifact directory
- **AND** the ONNX file SHALL be loadable by `onnxruntime.InferenceSession`

### Requirement: Retry guard prevents duplicate execution

The test script SHALL verify that the training worker aborts when a job already has a terminal status.

#### Scenario: Worker skips completed job

- **GIVEN** a training job with `status = "completed"` in the database
- **WHEN** `fine_tune_model` is invoked with that job ID
- **THEN** the worker SHALL log a skip warning
- **AND** the job status SHALL remain `completed`
- **AND** no training operations SHALL be executed
