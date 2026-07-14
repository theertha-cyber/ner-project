## MODIFIED Requirements

### Requirement: Model warmup on promotion

When a model version is promoted via the model registry, the system SHALL pre-load the model into the model-serving inference cache before the promote API responds. The warmup SHALL be synchronous — the promote endpoint SHALL wait for model-serving to confirm the model is loaded, with a client-side timeout of 90 seconds to accommodate cold loads (S3 artifact download plus ONNX Runtime session initialization) that take longer than usual immediately after a training job completes, while the host is still under load from that job. If the warmup fails (including on timeout), the promote SHALL still succeed (graceful degradation) and the model SHALL be loaded on the first extraction request. Model-serving SHALL continue loading the model in the background even if the promote request's warmup call times out, so that a subsequent warmup or extraction request finds the model already cached rather than re-triggering a full cold load.

#### Scenario: Warmup is triggered on promotion

- **GIVEN** a tenant with model v2 in "completed" status (MLflow Staging)
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{v2_id}/promote`
- **THEN** the model registry SHALL transition the version to MLflow Production
- **AND** the model registry SHALL call the model-serving warmup endpoint
- **AND** the model-serving SHALL load the model into the inference cache
- **AND** the promote API SHALL return status 200 only after warmup completes or the 90-second timeout elapses

#### Scenario: Warmup failure does not fail promote

- **GIVEN** the model-serving service is unavailable
- **WHEN** a Tenant Admin POSTs to `/api/v1/models/{version_id}/promote`
- **THEN** the promote SHALL succeed (MLflow stage transition + DB cache update)
- **AND** the error SHALL be logged
- **AND** the response SHALL have status 200

#### Scenario: A slow cold load that exceeds the client timeout still completes in the background

- **GIVEN** a tenant promotes a model version immediately after its training job finishes, while the host is still under load
- **WHEN** the warmup call to model-serving exceeds the 90-second client-side timeout and `_warmup_model()` logs a failure
- **THEN** model-serving SHALL continue loading the model to completion regardless of the client having given up
- **AND** a subsequent warmup call or extraction request for that tenant SHALL find the model already cached and SHALL NOT repeat the full cold load
- **AND** the promote response itself SHALL still be 200 (regression guard for the bug where a merely slow load was indistinguishable from a permanently broken one from the promote caller's perspective)

#### Scenario: First extraction after warmup uses cached model

- **GIVEN** a model has been warmed up via the promote endpoint
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract`
- **THEN** the extraction SHALL use the cached model
- **AND** the extraction response latency SHALL be consistent with a cache hit (no multi-second model loading delay)
