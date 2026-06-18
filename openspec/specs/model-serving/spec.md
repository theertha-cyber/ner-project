# Model Serving

## Purpose

Internal inference layer that loads ONNX models into an in-memory LRU cache and exposes a per-tenant inference endpoint (with tenant ID resolved from JWT) consumed by the extraction service.

---

## Requirements

### Requirement: Model cache

The system SHALL maintain an in-memory cache of loaded ONNX models keyed by model version ID. Models SHALL be loaded on first request for a tenant. The cache SHALL support LRU eviction when memory exceeds a configurable threshold (default 2 GB). Models SHALL be evicted after a configurable inactivity TTL (default 30 minutes).

#### Scenario: Load model on first request

- **GIVEN** a tenant with a promoted model version v2 that is not yet loaded
- **WHEN** an inference request arrives for that tenant
- **THEN** the model SHALL be loaded from blob storage into the cache
- **AND** the inference request SHALL proceed

#### Scenario: Cache hit on subsequent request

- **GIVEN** a tenant's model is already loaded in the cache
- **WHEN** an inference request arrives for that tenant
- **THEN** the cached model SHALL be used
- **AND** no new model loading SHALL occur

#### Scenario: LRU eviction on memory pressure

- **GIVEN** the cache has reached its memory threshold
- **WHEN** a new model needs to be loaded
- **THEN** the least recently used model SHALL be evicted
- **AND** the new model SHALL be loaded

### Requirement: Internal inference endpoint

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token class logits and predicted labels. When the tenant has no promoted fine-tuned model, the endpoint SHALL fall back to the base `dslim/bert-base-NER` model (version 0) and return CoNLL-2003 label predictions.

#### Scenario: Inference returns predictions from fine-tuned model

- **GIVEN** a loaded fine-tuned model for the tenant
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["John", "works", "at", "Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence
- **AND** the response SHALL contain `model_version` set to the promoted version number

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

### Requirement: Model warmup on promotion

The system SHALL pre-load a fine-tuned model into the cache when it is promoted via the model registry. Warmup SHALL NOT affect the base model singleton — the base model remains available before, during, and after any promotion.

| Old Path | New Path |
|----------|----------|
| `POST /internal/v1/tenants/{tid}/warmup` | `POST /internal/v1/warmup` |

#### Scenario: Warmup on promotion does not affect base model

- **GIVEN** the base model is loaded and in use (version 0)
- **WHEN** a new model version is promoted and warmed up
- **THEN** the base model SHALL remain loaded
- **AND** subsequent requests for that tenant SHALL use the promoted model
- **AND** other tenants without promoted models SHALL continue using the base model

#### Scenario: Warmup loads model without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a POST request is sent to `/internal/v1/warmup` with `{"version_number": 3}`
- **THEN** the response SHALL have status 200 with `{"status": "ok", "version_number": 3}`

#### Scenario: Warmup version 0 succeeds without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a POST request is sent to `/internal/v1/warmup` with `{"version_number": 0}`
- **THEN** the response SHALL have status 200 with `{"status": "ok", "version_number": 0}`

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

#### Scenario: Model rollback switches version

- **GIVEN** a tenant with promoted model v2 that is rolled back to v1
- **WHEN** an inference request arrives after the version TTL has expired
- **THEN** the system SHALL resolve and use model version v1
