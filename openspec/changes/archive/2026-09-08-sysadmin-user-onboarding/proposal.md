## Why

Only Tenant Admins can onboard users today (`POST /api/v1/users`, gated by `require_tenant_admin` + `resolve_tenant_from_jwt` in [users.py](src/gateway/api/v1/users.py:22)), so a System Admin who needs to seed a tenant's first Business User, recover from a locked-out Tenant Admin, or bulk-onboard users across tenants has no path except impersonating a Tenant Admin. The System Admin already manages tenants end-to-end (create, quota, deactivate) via `/api/v1/admin/*`, but user creation is the one onboarding capability it lacks — the admin console can only *list* a tenant's users (`GET /api/v1/admin/tenants/{tenant_id}/users`, [admin.py:87](src/gateway/api/v1/admin.py:87)), not create them.

System Admin is explicitly granted the ability to create `tenant_admin` users, not just `business_user`/`annotator`, for three concrete reasons:
- **First-admin provisioning**: `TenantService.create_tenant` already creates the first `tenant_admin` inline during tenant creation ([tenant_service.py:62-74](src/gateway/services/tenant_service.py:62)); this change gives System Admin the same capability outside that one-shot flow, e.g. to add a second Tenant Admin for a tenant.
- **Admin-account recovery**: if a tenant's only Tenant Admin account is lost, locked out, or leaves the organization, System Admin needs a way to re-establish tenant-level administration without direct database access.
- **Platform-level tenant lifecycle management**: System Admin already owns the full tenant lifecycle (create, quota, deactivate); the ability to staff a tenant's administration is a natural extension of that existing responsibility, not a new authority.

## What Changes

- Add a new System Admin endpoint `POST /api/v1/admin/tenants/{tenant_id}/users` that creates a user (`tenant_admin`, `business_user`, or `annotator`) in the tenant identified by the path parameter, gated by the existing `require_system_admin` dependency ([dependencies.py:17](src/gateway/dependencies.py:17)) — unchanged, no new or combined authorization dependency introduced. `tenant_id` is explicit in the path — never inferred from the actor's JWT.
- Reuse `UserService.create_user(tenant_id, payload, ...)` ([user_service.py:12](src/gateway/services/user_service.py:12)) as the shared creation logic for both the Tenant Admin and System Admin paths — no duplicated business logic, quota checks, or password validation. Two small additions land inside this shared service (not per-route) so both callers get them identically:
  - **Tenant-active validation**: the service currently checks a target tenant exists (via its quota row) but does not check `status`, relying entirely on `resolve_tenant_from_jwt`'s pre-check ([dependencies.py:76](src/gateway/dependencies.py:76)) for the Tenant Admin path. Since the System Admin path resolves `tenant_id` from the URL instead of a JWT, it has no equivalent pre-check today. Rather than duplicate an inactive-tenant check per route, `UserService.create_user` itself is extended to reject creation against an inactive tenant (`TenantInactiveError`, 403) — giving both callers the same guarantee from one place, including the edge case where a tenant is deactivated between a System Admin opening the create-user form and submitting it.
  - **Audit logging**: `UserService.create_user` records a `user.create` event via the existing `AuditService` ([audit_service.py](src/gateway/services/audit_service.py)) — the same pattern `TenantService.create_tenant`/`deactivate_tenant` already use — capturing `actor` (creator's email), `role` (creator's role: `tenant_admin` or `system_admin`), `target` (new user's email), and `tenant_id`. This is currently not captured at all for user creation by either role; see the Impact section.
- Leave `POST /api/v1/users` (Tenant Admin self-service, tenant scoped via JWT, `require_tenant_admin`) unchanged in route signature, request/response shape, and authorization. It gains the tenant-active and audit-logging behavior above only because it flows through the same shared service — not through any route-level change.
- Add a "Create User" action to the existing System Admin tenant detail page ([admin/tenants/[id]/page.tsx](src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx)), matching the exact button/panel terminology the Tenant Admin `Users` page already uses ("Create User" button, "New User" panel heading — [users/page.tsx:125](src/portal/src/app/(auth)/users/page.tsx:125), [users/page.tsx:131](src/portal/src/app/(auth)/users/page.tsx:131)) so the onboarding experience reads the same regardless of who is performing it. The page already displays the target tenant's name/slug and existing users — reusing that context to make the target tenant unambiguous before submission.
- Extract the existing inline create-user form from the Tenant Admin `Users` page ([users/page.tsx](src/portal/src/app/(auth)/users/page.tsx)) into a shared `CreateUserForm` component parameterized by an optional tenant context, used by both the Tenant Admin flow (tenant implicit) and the new System Admin flow (tenant explicit, shown read-only in the form header).

## Capabilities

### New Capabilities

- `sysadmin-user-onboarding`: System Admin cross-tenant user creation — API endpoint, authorization, and admin console UI for creating Tenant Admins, Annotators, and Business Users in any tenant.

### Modified Capabilities

- `admin-console`: Tenant Detail View gains a "Create User" control and creation flow (previously read-only user list).

## Impact

- **Backend**: `src/gateway/api/v1/admin.py` (new route), `src/gateway/dependencies.py` (no change — `require_system_admin` and `require_tenant_admin` reused exactly as they are today, no new or combined dependency), `src/gateway/services/user_service.py` (extended: tenant-active check, audit logging on creation — both additive, both apply to the existing Tenant Admin path too since it flows through the same method).
- **Frontend**: `src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx` (new "Create User" UI, same terminology as the Tenant Admin page), new shared `src/portal/src/components/users/CreateUserForm.tsx` (extracted from `users/page.tsx`), `src/portal/src/app/(auth)/users/page.tsx` (refactored to use the shared component, no behavior or wording change).
- **Database**: None. `tenant_users` table and `uq_email_per_tenant` constraint already support this; no schema change. `public.audit_events` (already exists, used by `AuditService`/`TenantService`) gains `user.create` rows; no schema change there either.
- **Tests**: New backend tests for the admin-create-user endpoint (role gating, tenant targeting, quota, duplicate email within/without target tenant, inactive-tenant rejection, audit event recorded); new/updated frontend tests for the shared form and the tenant-detail-page Create User flow.

## Open Questions

- Can a System Admin edit or deactivate users that a Tenant Admin created (and vice versa), or is this proposal creation-only? Default assumption: existing `PUT /api/v1/admin/tenants/{tenant_id}/users/{user_id}` style endpoints are out of scope for this change — only creation is added. Flag if edit/deactivate parity is also expected now.
- Duplicate emails are already unique per tenant (`uq_email_per_tenant`), so the same email may exist in two different tenants. Should System Admin-driven creation warn if the email is already registered in another tenant? Default assumption: no — same behavior as Tenant Admin path (uniqueness is per-tenant only).
- Should System Admin-created users receive a distinct email/notification (e.g., "invited by platform admin" vs. "invited by your tenant admin")? Default assumption: no notification system exists today for either path; out of scope. The new `user.create` audit event (recorded for both paths, see What Changes) covers the "who created this user" need without requiring a notification system.
