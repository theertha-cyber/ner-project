# ONNX Conversion

## Purpose

Converts the fine-tuned PyTorch NER model to ONNX format as part of the training pipeline, so the model-serving layer (which loads `*.onnx` files) can serve tenant-trained models instead of silently falling back to the base model.

## Requirements

### Requirement: Convert trained model to ONNX format

The training worker SHALL convert the fine-tuned PyTorch model to ONNX format after training completes, before persisting artifacts to blob storage. The conversion SHALL call `torch.onnx.export()` directly on the trained model (`trainer.model`) after `trainer.save_model()`, with explicit `input_names=["input_ids", "attention_mask"]`, `output_names=["logits"]`, and `dynamic_axes` covering the batch and sequence dimensions for `input_ids`, `attention_mask`, and `logits`. The export SHALL produce an ONNX file compatible with `onnxruntime.InferenceSession`.

#### Scenario: ONNX file is produced after training

- **GIVEN** a completed HuggingFace `Trainer.train()` run
- **WHEN** the worker calls `torch.onnx.export()` on `trainer.model` with dummy tokenized inputs (`input_ids`, `attention_mask`) and dynamic axes for the batch/sequence dimensions
- **THEN** a `model.onnx` file SHALL be written to the model output directory
- **AND** the ONNX model SHALL accept tokenized BERT inputs (`input_ids`, `attention_mask`) of variable batch size and sequence length
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
