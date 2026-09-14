## MODIFIED Requirements

### Requirement: Internal inference endpoint

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token predicted labels together with a **calibrated confidence in the closed interval `[0, 1]`**, obtained by applying a softmax over the label axis and taking the probability of the predicted label. The raw maximum logit SHALL NOT be returned as `confidence`. The ONNX path and the base-model fallback path SHALL emit confidences on the same scale, so a threshold means the same thing on both. When the tenant has no promoted fine-tuned model, the endpoint SHALL fall back to the base `dslim/bert-base-NER` model (version 0) and return CoNLL-2003 label predictions. For fine-tuned models, the endpoint SHALL resolve the tenant's custom `label_list` from the model registry and use it to map ONNX output indices to label strings instead of using the base model's CoNLL labels.

#### Scenario: Inference returns predictions from fine-tuned model with custom labels

- **GIVEN** a loaded fine-tuned model for the tenant with `label_list`: `["O", "B-company", "I-company", "B-contact_details"]`
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence
- **AND** labels SHALL use the tenant's custom entity types (e.g., "B-company"), NOT CoNLL labels
- **AND** the response SHALL contain `model_version` set to the promoted version number

#### Scenario: Confidence is a calibrated probability on the fine-tuned path

- **GIVEN** a loaded fine-tuned model for the tenant
- **WHEN** POST to `/internal/v1/infer` with any token sequence
- **THEN** every prediction's `confidence` SHALL satisfy `0.0 <= confidence <= 1.0`
- **AND** the value SHALL be the softmax probability of the predicted label, not the raw maximum logit

#### Scenario: Confidence is a calibrated probability on the base-model path

- **GIVEN** a tenant with no promoted model
- **WHEN** POST to `/internal/v1/infer` with any token sequence
- **THEN** every prediction's `confidence` SHALL satisfy `0.0 <= confidence <= 1.0`
- **AND** the scale SHALL be the same as the fine-tuned path's

#### Scenario: Overlap resolution still breaks ties by confidence

- **GIVEN** sliding-window inference where two windows label the same word at equal distance from a window edge
- **WHEN** the winner is selected
- **THEN** the selection SHALL compare calibrated probabilities
- **AND** the surviving prediction SHALL be the one with the higher probability

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
