## Why

Extraction service and model serving endpoints require `{tid}` as a URL path parameter (e.g., `/api/v1/tenants/{tid}/extract`), but the tenant ID is already available from the JWT via middleware (`request.state.tenant_id`). This redundancy forces callers to manually pass tenant_id in the URL, adds boilerplate `tid != tenant_id` validation in every handler, and deviates from the pattern used by document, annotation, and other services that auto-resolve tenant_id from JWT.

## What Changes

- **Extraction Service API** — remove `{tid}` from URL prefix. Endpoints change:
  - `POST /api/v1/tenants/{tid}/extract` → `POST /api/v1/extract` (**BREAKING**)
  - `POST /api/v1/tenants/{tid}/extract-batch` → `POST /api/v1/extract-batch` (**BREAKING**)
  - `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` → `GET /api/v1/extract-batch/{run_id}` (**BREAKING**)
  - `GET /api/v1/tenants/{tid}/entities` → `GET /api/v1/entities` (**BREAKING**)
  - `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` → `PATCH /api/v1/entities/{entity_id}` (**BREAKING**)
  - Remove `tid` parameter from all handler function signatures
  - Remove `tid != tenant_id` validation (redundant — both come from JWT now)
- **Model Serving API** — remove `{tid}` from internal URL prefix:
  - `POST /internal/v1/tenants/{tid}/infer` → `POST /internal/v1/infer` (**BREAKING**)
  - `POST /internal/v1/tenants/{tid}/warmup` → `POST /internal/v1/warmup` (**BREAKING**)
  - Remove `tid` parameter from handler signatures
  - Remove `tid != tenant_id` validation
- **Gateway extraction proxy** — remove `{tid}` from proxy prefix:
  - `POST /api/v1/tenants/{tid}/extract` → `POST /api/v1/extract` (**BREAKING**)
  - `POST /api/v1/tenants/{tid}/extract-batch` → `POST /api/v1/extract-batch` (**BREAKING**)
  - `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` → `GET /api/v1/extract-batch/{run_id}` (**BREAKING**)
  - `GET /api/v1/tenants/{tid}/entities` → `GET /api/v1/entities` (**BREAKING**)
  - `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` → `PATCH /api/v1/entities/{entity_id}` (**BREAKING**)
  - Remove `tid` parameter from all proxy functions; downstream URL construction no longer includes tenant_id in path
- **Callers** — update code that constructs the old URLs:
  - `extraction_engine.py`: no longer puts `tenant_id` in the inference URL (but still passes it via JWT token)
  - `worker.py`: no longer puts `tenant_id` in the inference URL (but still passes it via JWT token)
  - `models.py` (`_warmup_model`): no longer puts `tenant_id` in the warmup URL (but still passes it via JWT token)
- **README.md** — update all documented endpoint paths

## Capabilities

### New Capabilities

- `auto-resolve-tenant-id`: Remove `{tid}` from URL paths in extraction service, model serving service, and gateway proxy. Tenant ID is resolved exclusively from the JWT token set by the `TenantContextMiddleware` on `request.state.tenant_id`. All callers that construct URLs to these services are updated to omit `{tid}` from the path.

### Modified Capabilities

- None. No existing spec requirements are being modified — this is purely a routing and parameter refactor.

## Impact

- **Breaking API change**: All extraction endpoints on the gateway change their URL structure (external consumers must update). Internal model-serving endpoints also change (only affects internal service-to-service calls).
- **Services affected**: `extraction_service`, `model_serving`, `gateway` (extraction proxy), `training_service` (warmup caller)
- **Files changed**: ~8 files across 4 packages
- **Tests**: Endpoint URL changes require test updates. Extraction service mock-based tests need updated URL paths.
- **No DB changes**: Tenant ID continues to flow through middleware → `request.state`.
- **No config changes**: `settings.model_serving_url` remains unchanged.

## Open Questions

- None. The scope is well-understood and the pattern matches existing services (document, annotation).
