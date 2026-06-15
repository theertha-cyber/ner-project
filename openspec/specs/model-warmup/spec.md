# Model Warmup

## Purpose

TBD — Brand new capability for pre-loading models into the model-serving inference cache upon promotion.

---

## Requirements

### Requirement: Model warmup on promotion

When a model version is promoted via the model registry, the system SHALL pre-load the model into the model-serving inference cache before the promote API responds. The warmup SHALL be synchronous — the promote endpoint SHALL wait for model-serving to confirm the model is loaded. If the warmup fails, the promote SHALL still succeed (graceful degradation) and the model SHALL be loaded on the first extraction request.

#### Scenario: Warmup is triggered on promotion

- **GIVEN** a tenant with model v2 in "completed" status (MLflow Staging)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/promote`
- **THEN** the model registry SHALL transition the version to MLflow Production
- **AND** the model registry SHALL call the model-serving warmup endpoint
- **AND** the model-serving SHALL load the model into the inference cache
- **AND** the promote API SHALL return status 200 only after warmup completes

#### Scenario: Warmup failure does not fail promote

- **GIVEN** the model-serving service is unavailable
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{version_id}/promote`
- **THEN** the promote SHALL succeed (MLflow stage transition + DB cache update)
- **AND** the error SHALL be logged
- **AND** the response SHALL have status 200

#### Scenario: First extraction after warmup uses cached model

- **GIVEN** a model has been warmed up via the promote endpoint
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract`
- **THEN** the extraction SHALL use the cached model
- **AND** the extraction response latency SHALL be consistent with a cache hit (no multi-second model loading delay)

### Requirement: Warmup endpoint in model-serving

The model-serving service SHALL expose an internal warmup endpoint that accepts a tenant ID and optional version number and loads the corresponding model into the inference cache. The endpoint SHALL return 200 when the model is loaded and ready for inference.

#### Scenario: Warmup endpoint loads the active model

- **GIVEN** a tenant with a promoted model version v2 that is not currently cached
- **WHEN** a POST is sent to `/internal/v1/tenants/{tid}/warmup` without a version number
- **THEN** the model-serving SHALL resolve the active model version
- **AND** the model-serving SHALL load it into the cache
- **AND** the response SHALL have status 200

#### Scenario: Warmup endpoint loads a specific version

- **GIVEN** a tenant with model version v2 that is not currently cached
- **WHEN** a POST is sent to `/internal/v1/tenants/{tid}/warmup` with `{"version_number": 2}`
- **THEN** the model-serving SHALL load version v2 into the cache
- **AND** the response SHALL have status 200

#### Scenario: Warmup endpoint for non-existent version returns 404

- **GIVEN** a tenant without model version v99
- **WHEN** a POST is sent to `/internal/v1/tenants/{tid}/warmup` with `{"version_number": 99}`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL indicate the version was not found

### Requirement: Standalone warmup API (optional convenience)

The training service SHALL expose a warmup-only endpoint `POST /api/v1/models/{version_id}/warmup` that triggers model-serving warmup without changing the model's promotion status. This allows CI/CD pipelines and operators to pre-warm the cache independently.

#### Scenario: Warmup-only endpoint pre-loads a model

- **GIVEN** a tenant with a completed model version v2
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/warmup`
- **THEN** the model-serving SHALL load the model into the cache
- **AND** the model's status SHALL remain unchanged
