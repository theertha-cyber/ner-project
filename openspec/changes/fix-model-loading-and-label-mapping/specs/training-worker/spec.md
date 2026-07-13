## MODIFIED Requirements

### Requirement: Save model artifacts

The worker SHALL persist model artifacts (config.json, model.safetensors, tokenizer files, training_args.json, and model.onnx) to blob storage after training completes. The artifact path SHALL follow `tenants/{tid}/models/v{version}/` convention. The worker SHALL include the trained model's `label_list` (the ordered list of BIO labels used during training, e.g., `["O", "B-company", "B-contact_details", ...]`) in the `model_versions.metrics` JSONB column under the key `label_list`.

#### Scenario: Artifacts are stored after training

- **GIVEN** a completed training run
- **WHEN** the worker saves the model and tokenizer
- **THEN** `model.safetensors`, `config.json`, `tokenizer.json`, `vocab.txt`, `training_args.json`, `metrics.json`, and `model.onnx` SHALL exist at the artifact path
- **AND** the `model_versions` table SHALL have a new row with `version_number`, `status`: "completed", and `artifact_path`

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
