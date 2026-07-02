## ADDED Requirements

### Requirement: List extraction runs

The system SHALL expose an endpoint to list a tenant's batch extraction runs, most recently started first. The endpoint SHALL return up to 50 runs. Each run in the list SHALL include the same fields as the single-run status endpoint (`status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `completed_at`, `started_at`, `model_version`) plus `run_id`. The endpoint SHALL scope results to the requesting tenant's schema.

#### Scenario: List batch extraction runs for a tenant

- **GIVEN** a tenant with three extraction runs: one "completed", one "queued", one "failed"
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a `runs` array with all three runs
- **AND** each run SHALL include `run_id`, `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `started_at`, `completed_at`, and `model_version`

#### Scenario: Runs are ordered most-recent-first

- **GIVEN** a tenant with runs started at three different times
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the `runs` array SHALL be ordered by `started_at` descending

#### Scenario: List is scoped to the requesting tenant

- **GIVEN** tenant A has extraction runs and tenant B has none
- **WHEN** tenant B's Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the `runs` array SHALL be empty

#### Scenario: List returns empty array when no runs exist

- **GIVEN** a tenant with no extraction runs
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the `runs` array SHALL be empty

#### Scenario: List entities as non-admin business user

- **GIVEN** an authenticated `business_user`
- **WHEN** the user GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200

## MODIFIED Requirements

### Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure

The gateway extraction proxy SHALL use URL paths without `{tid}`. The proxy SHALL forward the JWT `Authorization` header (already present from the inbound request) transparently to the extraction service.

The following proxy endpoint paths SHALL change:

| Old Path | New Path |
|----------|----------|
| `POST /api/v1/tenants/{tid}/extract` | `POST /api/v1/extract` |
| `POST /api/v1/tenants/{tid}/extract-batch` | `POST /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` | `GET /api/v1/extract-batch/{run_id}` |
| `GET /api/v1/tenants/{tid}/extract-batch` (list) | `GET /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/entities` | `GET /api/v1/entities` |
| `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` | `PATCH /api/v1/entities/{entity_id}` |

#### Scenario: Proxy forwards single extraction request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: business_user`
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "Acme Corp"}`
- **THEN** the response SHALL have status 200 with extracted entities
- **AND** the proxy SHALL have forwarded the request to the extraction service at `/api/v1/extract`

#### Scenario: Proxy forwards batch run list request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: business_user`
- **WHEN** a GET request is sent to external gateway `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200 with a `runs` array
- **AND** the proxy SHALL have forwarded the request to the extraction service at `/api/v1/extract-batch`

#### Scenario: Proxy returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "test"}`
- **THEN** the response SHALL have status 403