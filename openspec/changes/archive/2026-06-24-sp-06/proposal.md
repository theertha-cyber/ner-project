## Why

The tenant management backend APIs and system-admin console are complete, but tenant admins have no functional UI to manage their own users — the `/users` page is an unimplemented placeholder. Completing this self-service surface closes the last gap in the multi-tenant lifecycle story.

## What Changes

- Implement the `/users` portal page for tenant admins: list, create, view/edit, and deactivate users scoped to their tenant
- Add a user list to the admin console's tenant detail page (`/admin/tenants/{id}`) so system admins can inspect which users belong to each tenant
- No backend changes — all APIs (`/api/v1/users`, `/api/v1/admin/tenants/{id}`) are already implemented

## Capabilities

### New Capabilities

- `tenant-admin-users-ui`: Full CRUD user management portal for tenant admins at `/users` — list users with role filter, create user form (email/password/role), user detail drawer or inline edit for role/status changes, deactivate action

### Modified Capabilities

- `admin-console`: Tenant detail page (`/admin/tenants/{id}`) shall display the list of users belonging to the tenant, satisfying the existing spec requirement that was left unimplemented

## Impact

- **Portal frontend only**: Changes confined to `src/portal/src/app/(auth)/users/page.tsx` (rewrite from placeholder) and `src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx` (add user list section)
- **APIs consumed**: `GET/POST /api/v1/users`, `GET/PUT/DELETE /api/v1/users/{id}` (tenant-scoped, JWT-resolved) and `GET /api/v1/admin/tenants/{id}` users sub-query (system admin)
- **Auth**: Users page gated by `tenant_admin` role; nav-config already routes `tenant_admin` to `/users`
- No backend, migration, or infrastructure changes

## Open Questions

- Should the admin console tenant detail use the existing `/api/v1/admin/tenants/{id}` endpoint (which currently returns `user_count` but not the user list) or call `/api/v1/users` impersonating the tenant? Assumption: a dedicated endpoint `GET /api/v1/admin/tenants/{id}/users` is needed — or the tenant detail response is extended to include a `users` array. Needs backend decision before implementation.
- What roles can tenant admins assign? Assumption: `annotator`, `business_user`, `tenant_admin` (not `system_admin`).
