## ADDED Requirements

### Requirement: Extraction Service Endpoints Auto-Resolve Tenant ID from JWT

The extraction service SHALL resolve tenant_id exclusively from the JWT token (via `request.state.tenant_id` set by `TenantContextMiddleware`). The URL path SHALL NOT include `{tid}` as a path parameter. The `tid` function parameter and the `tid != tenant_id` validation check SHALL be removed from all endpoint handlers.

The following endpoint paths SHALL change:

| Old Path | New Path |
|----------|----------|
| `POST /api/v1/tenants/{tid}/extract` | `POST /api/v1/extract` |
| `POST /api/v1/tenants/{tid}/extract-batch` | `POST /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` | `GET /api/v1/extract-batch/{run_id}` |
| `GET /api/v1/tenants/{tid}/entities` | `GET /api/v1/entities` |
| `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` | `PATCH /api/v1/entities/{entity_id}` |

#### Scenario: Single extraction returns entities without tid in URL

- **GIVEN** a valid JWT with `tenant_id` for a tenant that has a promoted model
- **WHEN** a POST request is sent to `/api/v1/extract` with `{"text": "Acme Corp"}`
- **THEN** the response SHALL have status 200 with a list of extracted entities
- **AND** the `model_version` SHALL be present in the response

#### Scenario: Batch extraction accepts request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: tenant_admin`
- **WHEN** a POST request is sent to `/api/v1/extract-batch?documentIds=uuid1,uuid2`
- **THEN** the response SHALL have status 200 with a `run_id` and `status: "queued"`

#### Scenario: Batch status returns run details without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a GET request is sent to `/api/v1/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200 with the batch run status and `model_version`

#### Scenario: Entity list returns entities without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a GET request is sent to `/api/v1/entities?reviewStatus=unreviewed`
- **THEN** the response SHALL have status 200 with a paginated list of extracted entities

#### Scenario: Entity patch updates review without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a PATCH request is sent to `/api/v1/entities/{entity_id}` with `{"review_status": "confirmed"}`
- **THEN** the response SHALL have status 200 with the updated entity

#### Scenario: Extraction returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/api/v1/extract` with `{"text": "test"}`
- **THEN** the response SHALL have status 403

---

### Requirement: Model Serving Endpoints Auto-Resolve Tenant ID from JWT

The model serving service SHALL resolve tenant_id exclusively from the JWT token (via `request.state.tenant_id` set by `TenantContextMiddleware`). The URL path SHALL NOT include `{tid}` as a path parameter. The `tid` function parameter and the `tid != tenant_id` validation check SHALL be removed from all endpoint handlers.

The following endpoint paths SHALL change:

| Old Path | New Path |
|----------|----------|
| `POST /internal/v1/tenants/{tid}/infer` | `POST /internal/v1/infer` |
| `POST /internal/v1/tenants/{tid}/warmup` | `POST /internal/v1/warmup` |

#### Scenario: Inference returns predictions without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a POST request is sent to `/internal/v1/infer` with `{"tokens": ["Acme", "Corp"]}`
- **THEN** the response SHALL have status 200 with token-level predictions and `model_version`

#### Scenario: Warmup loads model without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a POST request is sent to `/internal/v1/warmup` with `{"version_number": 3}`
- **THEN** the response SHALL have status 200 with `{"status": "ok", "version_number": 3}`

#### Scenario: Warmup version 0 succeeds without tid in URL

- **GIVEN** a valid JWT with `tenant_id`
- **WHEN** a POST request is sent to `/internal/v1/warmup` with `{"version_number": 0}`
- **THEN** the response SHALL have status 200 with `{"status": "ok", "version_number": 0}`

#### Scenario: Inference returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/internal/v1/infer` with `{"tokens": ["test"]}`
- **THEN** the response SHALL have status 403

---

### Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure

The gateway extraction proxy SHALL use URL paths without `{tid}`. The proxy SHALL forward the JWT `Authorization` header (already present from the inbound request) transparently to the extraction service.

The following proxy endpoint paths SHALL change:

| Old Path | New Path |
|----------|----------|
| `POST /api/v1/tenants/{tid}/extract` | `POST /api/v1/extract` |
| `POST /api/v1/tenants/{tid}/extract-batch` | `POST /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` | `GET /api/v1/extract-batch/{run_id}` |
| `GET /api/v1/tenants/{tid}/entities` | `GET /api/v1/entities` |
| `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` | `PATCH /api/v1/entities/{entity_id}` |

#### Scenario: Proxy forwards single extraction request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: business_user`
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "Acme Corp"}`
- **THEN** the response SHALL have status 200 with extracted entities
- **AND** the proxy SHALL have forwarded the request to the extraction service at `/api/v1/extract`

#### Scenario: Proxy returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "test"}`
- **THEN** the response SHALL have status 403

---

### Requirement: Callers Construct URLs Without {tid}

All internal callers that construct URLs to the extraction service or model serving service SHALL omit `{tid}` from the URL path. The tenant_id SHALL continue to be sent via the JWT token in the `Authorization` header.

Affected callers:
- `extraction_engine.py`: constructs inference URL → SHALL NOT include tenant_id in path; SHALL forward JWT from the incoming request
- `worker.py`: constructs inference URL for batch extraction → SHALL NOT include tenant_id in path (JWT already forwarded)
- `models.py` (`_warmup_model`): constructs warmup URL → SHALL NOT include tenant_id in path (JWT already forwarded)

#### Scenario: Extraction engine forwards request without tid in URL

- **GIVEN** the synchronous extract endpoint receives a request with a valid JWT
- **WHEN** `extraction_engine.infer()` is called
- **THEN** the HTTP POST to model serving SHALL use URL `/internal/v1/infer` (without `{tid}`)
- **AND** the request SHALL include the `Authorization` header from the incoming request

#### Scenario: Worker constructs inference URL without tid in path

- **GIVEN** a batch extraction run is processing documents
- **WHEN** the worker sends an inference request to model serving
- **THEN** the URL SHALL be `/internal/v1/infer` (without `{tid}`)
- **AND** the request SHALL include a valid JWT with the tenant_id

#### Scenario: Training service constructs warmup URL without tid in path

- **GIVEN** a model is being promoted
- **WHEN** `_warmup_model()` sends a warmup request to model serving
- **THEN** the URL SHALL be `/internal/v1/warmup` (without `{tid}`)
- **AND** the request SHALL include a valid JWT with the tenant_id
