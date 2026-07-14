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

The model-serving layer SHALL expose an internal inference endpoint consumed by the extraction service. The endpoint SHALL accept tokenized input and return per-token class logits and predicted labels. When the tenant has no promoted fine-tuned model, the endpoint SHALL fall back to the base `dslim/bert-base-NER` model (version 0) and return CoNLL-2003 label predictions. For fine-tuned models, the endpoint SHALL resolve the tenant's custom `label_list` from the model registry and use it to map ONNX output indices to label strings instead of using the base model's CoNLL labels.

#### Scenario: Inference returns predictions from fine-tuned model with custom labels

- **GIVEN** a loaded fine-tuned model for the tenant with `label_list`: `["O", "B-company", "I-company", "B-contact_details"]`
- **WHEN** POST to `/internal/v1/infer` with `{"tokens": ["Acme", "Corp"]}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `predictions` array with per-token label and confidence
- **AND** labels SHALL use the tenant's custom entity types (e.g., "B-company"), NOT CoNLL labels
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

### Requirement: Model loader uses API-provided artifact path

The model loader SHALL accept the `artifact_path` from the model registry API response and use it to download artifacts from blob storage. The loader SHALL NOT construct its own path independently.

#### Scenario: Loader downloads from API-provided path

- **GIVEN** the active model API returns `artifact_path`: `tenants/abc-123/models/v5/`
- **WHEN** the model loader downloads artifacts
- **THEN** the loader SHALL list and download objects under the prefix `tenants/abc-123/models/v5/`
- **AND** the loader SHALL NOT use a different path format

#### Scenario: Loader handles missing artifacts gracefully

- **GIVEN** the API-provided artifact path exists but contains no ONNX file
- **WHEN** the model loader attempts to load the model
- **THEN** the loader SHALL return a failure status
- **AND** the inference service SHALL fall back to the base model

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

### Requirement: Model Registry URL is configurable and targets the correct in-network port

The model-serving layer SHALL resolve the Model Registry (`training_service`) base URL from a `training_service_url` setting, not a hardcoded literal. The setting SHALL default to the correct bare-metal host-mapped port for local development, and SHALL be overridable via environment variable for Docker Compose to target the service's internal container port.

#### Scenario: Registry URL is read from settings, not hardcoded

- **GIVEN** `_resolve_active_version()` and `_resolve_label_list()` need to query the active model
- **WHEN** either function builds the Model Registry request URL
- **THEN** the URL SHALL be built from `settings.training_service_url`
- **AND** no literal `http://training_service:8003` or similar hardcoded host:port string SHALL appear in `inference_service.py`

#### Scenario: Registry URL defaults to the correct port for bare-metal dev

- **GIVEN** the `NER_TRAINING_SERVICE_URL` environment variable is not set
- **WHEN** model-serving resolves the active model version
- **THEN** the request SHALL be sent to `http://localhost:8003/api/v1/models/active`

#### Scenario: Registry URL is overridden to the Docker-internal port

- **GIVEN** `NER_TRAINING_SERVICE_URL` is set to `http://training_service:8000`
- **WHEN** model-serving resolves the active model version inside the Docker Compose network
- **THEN** the request SHALL be sent to `http://training_service:8000/api/v1/models/active`
- **AND** the request SHALL successfully connect (not fail with a connection error)

#### Scenario: A misconfigured or unreachable registry URL still falls back to the base model

- **GIVEN** `training_service_url` points at an address with nothing listening
- **WHEN** model-serving attempts to resolve the active model version
- **THEN** the request SHALL fail with a connection error
- **AND** the system SHALL fall back to treating the tenant as version 0 (base model), consistent with the "Version resolution with base fallback" requirement
- **AND** this fallback SHALL NOT be the outcome of every request once the URL is correctly configured (regression guard for the bug where the hardcoded port made this the permanent, not exceptional, path)

### Requirement: ONNX inference inputs match the loaded session's declared inputs

`_infer_with_onnx()` SHALL only include an input (e.g. `token_type_ids`) in the dict passed to `session.run()` when the loaded ONNX session actually declares that input name. It SHALL NOT assume a fixed input signature based on what the tokenizer produces.

#### Scenario: Inference succeeds against a 2-input ONNX export

- **GIVEN** a loaded ONNX session whose declared inputs are `["input_ids", "attention_mask"]` (no `token_type_ids`), matching the current training worker's export convention
- **WHEN** `_infer_with_onnx()` runs inference and the tokenizer output includes `token_type_ids`
- **THEN** `token_type_ids` SHALL NOT be included in the dict passed to `session.run()`
- **AND** the call SHALL succeed and return predictions, not fall back to the base model due to an ONNX `InvalidArgument` error

#### Scenario: Inference succeeds against a 3-input ONNX export

- **GIVEN** a loaded ONNX session whose declared inputs include `token_type_ids`
- **WHEN** `_infer_with_onnx()` runs inference and the tokenizer output includes `token_type_ids`
- **THEN** `token_type_ids` SHALL be included in the dict passed to `session.run()`
- **AND** the call SHALL succeed and return predictions

#### Scenario: A promoted model is actually used for extraction, not silently replaced by the base model

- **GIVEN** a tenant with a promoted, ONNX-loadable model version
- **WHEN** an extraction request is made for that tenant
- **THEN** the response SHALL have `model_version` equal to the promoted version number, not `"0"`
- **AND** the response SHALL NOT contain the `x-model-source: base` header
- **AND** this SHALL hold regardless of whether the exported ONNX graph includes a `token_type_ids` input (regression guard for the bug where an ONNX input mismatch caused every fine-tuned model to silently fall back to the base model)
