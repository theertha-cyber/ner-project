## MODIFIED Requirements

### Requirement: Internal inference endpoint

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token class logits and predicted labels. Predictions SHALL be returned as an ordered sequence following source token order, with one entry per predicted token; predictions SHALL NOT be deduplicated or reordered by token text, since downstream BIO reconstruction depends on order and on repeated occurrences. This applies to both the fine-tuned ONNX path and the base-model fallback path. When the tenant has no promoted fine-tuned model, the endpoint SHALL fall back to the base `dslim/bert-base-NER` model (version 0) and return CoNLL-2003 label predictions. For fine-tuned models, the endpoint SHALL resolve the tenant's custom `label_list` from the model registry and use it to map ONNX output indices to label strings instead of using the base model's CoNLL labels.

#### Scenario: Inference returns predictions from fine-tuned model with custom labels

- **GIVEN** a loaded fine-tuned model for the tenant with `label_list`: `["O", "B-company", "I-company", "B-contact_details"]`
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence
- **AND** labels SHALL use the tenant's custom entity types (e.g., "B-company"), NOT CoNLL labels
- **AND** the response SHALL contain `model_version` set to the promoted version number

#### Scenario: Base-model predictions preserve token order and repeats

- **GIVEN** a tenant with no promoted model
- **WHEN** POST to `/internal/v1/infer` with tokens whose text contains the same entity word twice
- **THEN** the `predictions` array SHALL contain one entry per predicted token in source order
- **AND** the repeated word SHALL appear once per occurrence, not collapsed into a single entry

#### Scenario: Inference falls back to base model when no tenant model exists

- **GIVEN** a tenant with no promoted model version
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["John", "works", "at", "Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with CoNLL labels (PER, ORG, LOC, MISC)
- **AND** the response SHALL contain `model_version`: "0"

#### Scenario: Inference falls back to base model when tenant model fails to load

- **GIVEN** a tenant with a promoted model version that fails to load (corrupt artifacts, storage unavailable)
- **WHEN** POST to `/internal/v1/infer`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL use the base model
- **AND** the response SHALL contain a warning header indicating model load failure

#### Scenario: Inference returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["test"]}`
- **THEN** the response SHALL have status 403
