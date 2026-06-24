## Context

The platform's tenant management lifecycle is nearly complete. The backend APIs for both system-admin tenant provisioning (`/api/v1/admin/tenants`) and tenant-admin user management (`/api/v1/users`) are fully implemented. The system-admin console frontend (tenant list, create, detail/quotas) is built. The only remaining gap is on the frontend:

1. `/users` — renders a `PlaceholderScreen` for tenant admins who need to manage their own users.
2. `/admin/tenants/{id}` — shows quotas and action buttons but omits the user list, which the `admin-console` spec requires.

Additionally, there is a backend gap: no API exists for a system admin to list users belonging to a specific tenant (needed to populate the user list in the admin console detail view).

## Goals / Non-Goals

**Goals:**

- Implement the tenant-admin Users page (`/users`) with full user CRUD: list, create, update role, deactivate.
- Add a backend endpoint for system admins to list users of any tenant (`GET /api/v1/admin/tenants/{id}/users`).
- Add a Users section to the admin console tenant detail page (`/admin/tenants/{id}`).

**Non-Goals:**

- No changes to authentication, JWT, or tenant context middleware.
- No frontend route changes — nav is already wired.
- No schema migrations — `public.tenant_users` already exists.
- No password reset or email verification flows.
- No pagination on the users list in the admin console (tenant user counts are bounded by `max_users` quota, typically ≤100).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Per-tenant PostgreSQL schemas; `tenant_users` lives in `public` schema | User queries from system-admin context MUST scope by `tenant_id` column in `public.tenant_users`; no cross-schema leakage |

ADR-002 through ADR-008 cover model strategy, serving topology, governance, agent boundaries, training infra, chatbot architecture, and base-model defaults — none constrain this frontend-only change.

## Decisions

### Decision 1: Add `GET /api/v1/admin/tenants/{tenant_id}/users` backend endpoint

**Choice:** Add a new route to `src/gateway/api/v1/admin.py` that calls `UserService.list_users(tenant_id)` under system-admin auth. No new service method needed — `list_users` already accepts a `tenant_id` parameter and queries `public.tenant_users`.

**Rationale:** The tenant detail page in the admin console needs to display tenant users. The existing `get_tenant` call returns only `user_count`. Rather than modifying the tenant detail response (risks adding unbounded data to a summary endpoint), a dedicated sub-resource endpoint keeps concerns separate and follows the existing REST convention used throughout the gateway.

**Alternatives considered:**
- Extend `GET /api/v1/admin/tenants/{id}` to embed a `users` array — ruled out because the tenant list endpoint returns the same response shape and embedding users in every tenant object would be wasteful.
- Call `GET /api/v1/users` from the admin console with a spoofed tenant header — ruled out because it would require bypassing JWT-based tenant resolution and breaks the auth model.

### Decision 2: Implement `/users` page as a single-page CRUD view (no separate create page)

**Choice:** The `/users` page shows a user table with an inline "Create User" form toggle and per-row inline "Edit Role" and "Deactivate" actions. No separate `/users/new` route.

**Rationale:** User objects have only three mutable fields (email, password, role). Keeping creation inline avoids the navigation overhead of a separate page for such a simple form. This is consistent with how the tenant detail page handles quota editing (inline toggle, not a new route). The bounded `max_users` quota means the list never becomes unwieldy.

**Alternatives considered:**
- Separate `/users/new` page (like `/admin/tenants/new`) — ruled out as over-engineered for a three-field form.
- Modal dialog — either approach is fine; inline toggle is simpler to implement without a modal library.

### Decision 3: Allow role changes but not re-activation via the users page

**Choice:** Tenant admins can update a user's `role` (annotator, business_user, tenant_admin). The `PUT /api/v1/users/{id}` endpoint also accepts `status` but the UI exposes only role editing. Deactivation is a one-way action via the dedicated "Deactivate" button; re-activation is not exposed.

**Rationale:** The backend spec (`tenant-user-mgmt`) exposes deactivation only via `DELETE /api/v1/users/{id}`. Re-activation is not specified and would require a separate backend endpoint. Keeping re-activation out of scope prevents half-finished implementation.

## Risks / Trade-offs

- [Admin console user list makes an additional API call per page visit to `/admin/tenants/{id}/users`] → Acceptable — bounded by tenant `max_users` quota; can add caching later if needed.
- [Tenant admin can assign `tenant_admin` role to another user, potentially creating multiple tenant admins] → By design — the spec allows it and there is no single-admin constraint in the data model.
- [Create-user form sends password in plaintext over HTTPS] → Mitigated by HTTPS-only deployment; backend hashes immediately via `hash_password`.

## Migration Plan

1. Add `GET /api/v1/admin/tenants/{tenant_id}/users` route to `src/gateway/api/v1/admin.py` (no migration, no schema change).
2. Register the updated router in `src/gateway/main.py` if not already auto-included.
3. Deploy gateway service.
4. Implement `/users` portal page in `src/portal/src/app/(auth)/users/page.tsx`.
5. Add users section to `src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx`.
6. Deploy portal.

Rollback: frontend changes are stateless (no DB writes from portal); rolling back portal to previous build restores the placeholder with no side effects. The new backend endpoint is additive and safe to leave in place.

## Open Questions

- Should deactivating a user also revoke active JWT sessions immediately, or let them expire naturally? Assumed: natural expiry (no token blocklist in scope). Requires confirmation if stricter logout is needed.
