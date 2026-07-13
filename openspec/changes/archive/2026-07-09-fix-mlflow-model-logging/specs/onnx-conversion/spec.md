## ADDED Requirements

### Requirement: Convert trained model to ONNX format

The training worker SHALL convert the fine-tuned PyTorch model to ONNX format after training completes, before persisting artifacts to blob storage. The conversion SHALL use the `optimum` library and SHALL produce an ONNX file compatible with `onnxruntime.InferenceSession`.

#### Scenario: ONNX file is produced after training

- **GIVEN** a completed HuggingFace `Trainer.train()` run
- **WHEN** the worker calls `optimum.onnx.export_onnx()` with the model and tokenizer
- **THEN** a `.onnx` file SHALL be written to the model output directory
- **AND** the ONNX model SHALL accept tokenized BERT inputs (`input_ids`, `attention_mask`)
- **AND** the ONNX model SHALL produce the same output logits shape as the PyTorch model

#### Scenario: ONNX file is uploaded to blob storage

- **GIVEN** an ONNX file exists in the model directory
- **WHEN** the worker uploads artifacts to MinIO via `_save_artifacts()`
- **THEN** a `.onnx` file SHALL exist at the artifact path `tenants/{tid}/models/v{version}/`
- **AND** the PyTorch format files SHALL also be present (backward compatibility)

#### Scenario: ONNX file is loadable by model-serving layer

- **GIVEN** an ONNX file at the expected MinIO path
- **WHEN** the model-serving layer downloads and loads it via `onnxruntime.InferenceSession()`
- **THEN** the model SHALL load without errors
- **AND** an inference call SHALL return valid predictions
