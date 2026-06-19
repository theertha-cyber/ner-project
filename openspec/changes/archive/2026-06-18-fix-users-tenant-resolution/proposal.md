## Why

The tenant user management endpoints require a `{tenant_id}` URL path parameter that is actually a tenant slug, but a logged-in tenant admin's JWT already contains their tenant identity. This redundancy causes Swagger UI to fail (sending the literal placeholder `{tenant_id}` string), creates a confusing naming mismatch (`tenant_id` in the route vs. slug-based lookup in code), and is inconsistent with how other tenant-scoped endpoints (e.g., `entity_types`) already resolve tenant from the JWT alone.

## What Changes

- **BREAKING** Remove `{tenant_id}` from the users router URL prefix — new base path becomes `/api/v1/users`
- Switch users router from `resolve_tenant` (requires slug in URL + JWT cross-check) to `resolve_tenant_from_jwt` (derives tenant entirely from JWT)
- Update `specs/tenant-user-mgmt/spec.md` to reflect the new URL pattern and dependency resolution strategy
- No change to business logic, role enforcement, or response shapes

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `tenant-user-mgmt`: URL changes from `/api/v1/tenants/{slug}/users` to `/api/v1/users`; tenant resolution changes from `resolve_tenant` (URL slug) to `resolve_tenant_from_jwt` (JWT claim). Role enforcement (`require_tenant_admin`) and cross-tenant isolation remain identical — the JWT tenant claim already ensures a tenant admin can only operate within their own tenant.

## Impact

- **`src/gateway/api/v1/users.py`** — router prefix and dependency change
- **`openspec/specs/tenant-user-mgmt/spec.md`** — spec scenarios updated to use new URL
- **API consumers** — any client calling `/api/v1/tenants/{slug}/users` must update to `/api/v1/users`
- No database changes, no auth logic changes, no other services affected

## Open Questions

- Should the old `/api/v1/tenants/{slug}/users` path be kept as a deprecated alias temporarily, or cut immediately? (Current assumption: cut immediately — this is an internal project with no external consumers.)
