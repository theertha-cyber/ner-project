## Why

The user-auth spec mandates that a Tenant Admin can create, read, update, and deactivate users within their own tenant scope. The current implementation blocks Tenant Admin from all user CRUD — the endpoints sit under `/api/v1/admin/...` and require `system_admin`. This is a spec-vs-implementation gap that blocks tenant-level user management.

## What Changes

- Add a new tenant-scoped route module `users.py` at prefix `/api/v1/tenants/{slug}/users` with full CRUD
- Add a `require_tenant_admin` dependency that admits only the `tenant_admin` role
- Wire the new router into the app
- **Remove** user CRUD endpoints from `admin.py` — system_admin no longer manages tenant users
- Update the existing `user-auth` delta spec scenarios to reference the correct route paths
- Rewrite `test_scenario_10` to test tenant-scoped user creation (own-tenant → 201, cross-tenant → 403)

## Capabilities

### New Capabilities

- `tenant-user-mgmt`: Tenant-scoped user CRUD endpoints at `/api/v1/tenants/{slug}/users`, gated by `resolve_tenant` + `require_tenant_admin`

### Modified Capabilities

- `user-auth`: The "Tenant-Scoped User Management" requirement scenarios need their route paths corrected from `/api/v1/admin/tenants/{tid}/users` to `/api/v1/tenants/{slug}/users` to match the new tenant-scoped router

## Impact

| Area | Impact |
|---|---|---|
| `src/gateway/dependencies.py` | New `require_tenant_admin` dependency function |
| `src/gateway/api/v1/users.py` | New router module (mirrors `entity_types.py` structure) |
| `src/gateway/main.py` | Add `users.router` to `include_router` |
| `src/gateway/api/v1/admin.py` | Remove 5 user CRUD endpoints (lines 63–116) |
| `openspec/changes/sm-01-identity-tenant-entity-config/specs/user-auth/spec.md` | Delta: update route paths in 2 scenarios |
| `tests/` | All test files updated to remove admin user route dependencies |
| `README.md` | Replace admin user endpoints with tenant-scoped user endpoints |

## Open Questions

- Should `tenant_admin` users be able to create other `tenant_admin` users within their tenant? (Assuming yes for now — the role enum includes `tenant_admin` as a valid role for user creation)
