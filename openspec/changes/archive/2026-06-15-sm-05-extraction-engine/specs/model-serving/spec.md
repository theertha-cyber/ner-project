## ADDED Requirements

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

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token class logits and predicted labels.

#### Scenario: Inference returns predictions

- **GIVEN** a loaded model for the tenant
- **WHEN** POST to `/internal/v1/tenants/{tid}/infer` with `{"tokens": ["John", "works", "at", "Acme", "Corp", "in", "New", "York"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence

#### Scenario: Inference for tenant with no loaded model

- **GIVEN** no model is loaded for the tenant
- **WHEN** POST to `/internal/v1/tenants/{tid}/infer`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL indicate no model is available

### Requirement: Model warmup on promotion

The system SHALL pre-load a model into the cache when it is promoted via the model registry (consuming the `ModelPromoted` event). Warmup SHALL complete before the promotion API returns success to ensure zero cold-start latency for the first extraction request.

#### Scenario: Warmup on promotion

- **GIVEN** a model version v2 is being promoted
- **WHEN** the promotion completes
- **THEN** the model SHALL be loaded into the serving cache
- **AND** the first extraction request after promotion SHALL use the cached model

### Requirement: Version pinning

The system SHALL resolve the tenant's active model version from the model registry on each request (or cache with configurable TTL, default 60 seconds). The system SHALL use the resolved version for inference.

#### Scenario: Version pinning uses active model

- **GIVEN** a tenant with promoted model v2
- **WHEN** an inference request arrives
- **THEN** the system SHALL resolve and use model version v2

#### Scenario: Model rollback switches version

- **GIVEN** a tenant with promoted model v2 that is rolled back to v1
- **WHEN** an inference request arrives after the version TTL has expired
- **THEN** the system SHALL resolve and use model version v1
