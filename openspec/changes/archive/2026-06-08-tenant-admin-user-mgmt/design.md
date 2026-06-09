## Context

The user-auth spec requires Tenant Admin to manage users within their own tenant. Currently all user CRUD endpoints live under `/api/v1/admin/tenants/{tid}/users` and are gated by `require_system_admin`. Tenant Admin gets a 403 on every user operation — even within their own tenant.

A tenant-scoped route pattern already exists for entity types at `/api/v1/tenants/{slug}/entity-types`, using `resolve_tenant` + `require_tenant_role` dependencies. This design extends that pattern to user management, adding a `require_tenant_admin` dependency for the tighter role gate.

## Goals / Non-Goals

**Goals:**
- Tenant Admin can create, read, update, and deactivate users in their own tenant via `/api/v1/tenants/{slug}/users`
- Cross-tenant user operations from a Tenant Admin return 403 (enforced by `resolve_tenant`)
- Remove `system_admin` user CRUD endpoints from `/api/v1/admin/...` — user management is delegated entirely to Tenant Admin
- A new `require_tenant_admin` dependency to gate tenant-scoped user endpoints

**Non-Goals:**
- Not introducing role hierarchies or permission levels beyond the exact role check
- Not changing entity-type or other existing tenant-scoped routes

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation | API Gateway validates JWT `tenant_id`, injects tenant context | Must use `resolve_tenant` (or equivalent) to enforce tenant match on all scoped endpoints |

## Decisions

### Decision 1: New `users.py` router module

**Choice:** Create `src/gateway/api/v1/users.py` with `prefix="/api/v1/tenants/{slug}/users"`, mirroring the `entity_types.py` structure.

**Rationale:** Keeps route organization clean — each domain has its own module. The existing `entity_types.py` provides a proven pattern to follow.

**Alternatives considered:**
- Adding routes to `admin.py` with a separate router — would mix system-admin and tenant-scoped concerns in one file
- Inlining into `auth.py` — auth (login/refresh/logout) and user CRUD are separate concerns

### Decision 2: `require_tenant_admin` admits only `tenant_admin`

**Choice:** A dependency that checks `role == "tenant_admin"` (exact match, no hierarchy).

**Rationale:** User management is delegated entirely to Tenant Admin — the `/api/v1/admin/...` user CRUD endpoints have been removed. `system_admin` with their `tenant_id = "system"` JWT would fail `resolve_tenant` for any real tenant anyway, so admitting them would be dead code.

**Alternatives considered:**
- Admitting `system_admin` too — unnecessary, since they can't pass `resolve_tenant` for non-system tenants
- A role-hierarchy check (`role in ("tenant_admin", "system_admin")`) — clearer intent but functionally identical given `resolve_tenant` behavior

### Decision 3: Remove admin user CRUD endpoints

**Choice:** Delete the 5 user management endpoints from `admin.py` (POST, GET list, GET by id, PUT, DELETE).

**Rationale:** User management is a tenant-level concern. System Admin should manage tenants (provisioning, quotas, deactivation), not the users within them. This separation of concerns keeps the admin surface area focused and prevents confusion about which role manages users.

**Alternatives considered:**
- Keeping admin routes and adding tenant-scoped routes as alternatives — would create duplicate surface area with ambiguous ownership

### Decision 4: `tenant_admin` can create other `tenant_admin` users

**Choice:** The user creation endpoint accepts any valid role from the `UserRole` enum (`tenant_admin`, `business_user`, `annotator`).

**Rationale:** Simplicity — the service layer already validates roles against the enum. No additional restriction in this change. Can be tightened later if policy demands it.

## Risks / Trade-offs

- [Bootstrapping: the first tenant_admin in a new tenant cannot be created via API] → Tenant provisioning (seed scripts, system admin tools) must handle first-user creation. Tests bypass this by creating tenant_admin tokens directly (no DB lookup required for token validation).
- [`require_tenant_admin` is a new dependency that could be confused with `require_tenant_role`] → Name it distinctly and document in the module; `require_tenant_admin` is stricter (single role), `require_tenant_role` is looser (any authenticated tenant user)

## Migration Plan

1. Add `require_tenant_admin` to `dependencies.py`
2. Create `users.py` router
3. Wire `users.router` into `main.py`
4. Remove user CRUD endpoints from `admin.py`
5. Update `user-auth` delta spec paths
6. Update tests — rewrite `test_scenario_10`, add own-tenant CRUD tests, remove admin route dependencies
7. Run full test suite to verify
8. Update README

Rollback: Restore `admin.py` user CRUD endpoints and remove `users.router` from `main.py`.

## Open Questions

- None — decisions were settled during exploration.
