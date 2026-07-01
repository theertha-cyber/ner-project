## Why

The entity types backend API was implemented with routes at `/api/v1/entity-types` and UUID-based identifiers, but the frontend (built per sp-09 spec) calls `/api/v1/tenants/{slug}/entity-types` with name-based identifiers. This causes every entity type API call to return 404, so entities created directly in the database never appear in the UI.

## What Changes

- **BREAKING** Change backend route prefix from `/api/v1/entity-types` to `/api/v1/tenants/{tenant_slug}/entity-types`
- Change route parameters from `{entity_id}` (UUID) to `{name}` (string) on GET, PUT, and DELETE endpoints
- Add `PATCH /api/v1/tenants/{tenant_slug}/entity-types/{name}` endpoint for toggling `is_active`
- Fix `EntityService._row_to_dict` to call `json.loads()` on `examples` and `base_label_mapping` columns (currently returned as raw JSON strings)
- Fix `create_entity_type` and `update_entity_type` response shape — currently returns `{"entity_type": {...}}` but frontend expects the flat entity object

## Capabilities

### New Capabilities

- `entity-types-backend`: Backend API routes and service layer aligned to the spec: correct URL prefix, name-based identifiers, PATCH toggle endpoint, and correct JSON serialization on read

### Modified Capabilities

<!-- No existing spec-level requirements are changing — this is a bug fix bringing backend implementation into conformance with the already-approved sp-09-entity-types spec -->

## Impact

- `src/gateway/api/v1/entity_types.py` — router prefix and all route handler signatures
- `src/gateway/services/entity_service.py` — `_row_to_dict`, `_get_by_id` response shape, new toggle method
- Existing direct calls to `/api/v1/entity-types/*` (e.g. via Postman or scripts) will break — this is intentional alignment

## Open Questions

- Should the old `/api/v1/entity-types` prefix be kept temporarily with a deprecation warning, or removed immediately? (Recommend: remove immediately — no production traffic has relied on it)
- The `resolve_tenant_from_jwt` dependency currently resolves tenant ID from the JWT. With `/tenants/{slug}/` in the URL, does the middleware already validate slug-vs-JWT consistency? (Confirmed: `TenantContextMiddleware` extracts slug from URL into `request.state.tenant_slug` but doesn't cross-validate against the JWT tenant — the dependency chain should verify this)
