## MODIFIED Requirements

### Requirement: Internal inference endpoint

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token class logits and predicted labels. When the tenant has no promoted fine-tuned model, the endpoint SHALL fall back to the base `dslim/bert-base-NER` model (version 0) and return CoNLL-2003 label predictions.

#### Scenario: Inference returns predictions from fine-tuned model

- **GIVEN** a loaded fine-tuned model for the tenant
- **WHEN** POST to `/internal/v1/tenants/{tid}/infer` with `{"tokens": ["John", "works", "at", "Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence
- **AND** the response SHALL contain `model_version` set to the promoted version number

#### Scenario: Inference falls back to base model when no tenant model exists

- **GIVEN** a tenant with no promoted model version
- **WHEN** POST to `/internal/v1/tenants/{tid}/infer` with `{"tokens": ["John", "works", "at", "Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with CoNLL labels (PER, ORG, LOC, MISC)
- **AND** the response SHALL contain `model_version`: "0"

#### Scenario: Inference falls back to base model when tenant model fails to load

- **GIVEN** a tenant with a promoted model version that fails to load (corrupt artifacts, storage unavailable)
- **WHEN** POST to `/internal/v1/tenants/{tid}/infer`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL use the base model
- **AND** the response SHALL contain a warning header indicating model load failure

### Requirement: Version resolution with base fallback

The system SHALL resolve the tenant's active model version from the model registry on each request (or cache with configurable TTL, default 60 seconds). If no promoted model version exists, the system SHALL treat version 0 (base model) as the active version. The base model SHALL be loaded as a shared singleton, not per-tenant.

#### Scenario: Version resolution returns promoted model when one exists

- **GIVEN** a tenant with promoted model v2
- **WHEN** an inference request arrives
- **THEN** the system SHALL resolve and use model version v2

#### Scenario: Version resolution returns version 0 when no model is promoted

- **GIVEN** a tenant with no promoted model version
- **WHEN** an inference request arrives
- **THEN** the system SHALL resolve to version 0
- **AND** the system SHALL use the base model pipeline for inference

#### Scenario: Base model is shared across tenants

- **GIVEN** tenants A and B both have no promoted model
- **WHEN** inference requests arrive for both tenants
- **THEN** both requests SHALL use the same base model pipeline instance
- **AND** the base model SHALL be loaded only once

### Requirement: Model warmup on promotion

The system SHALL pre-load a fine-tuned model into the cache when it is promoted via the model registry. Warmup SHALL NOT affect the base model singleton — the base model remains available before, during, and after any promotion.

#### Scenario: Warmup on promotion does not affect base model

- **GIVEN** the base model is loaded and in use (version 0)
- **WHEN** a new model version is promoted and warmed up
- **THEN** the base model SHALL remain loaded
- **AND** subsequent requests for that tenant SHALL use the promoted model
- **AND** other tenants without promoted models SHALL continue using the base model
