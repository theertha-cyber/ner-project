## Context

Today `POST /api/v1/users` ([users.py:22](src/gateway/api/v1/users.py:22)) creates a user via `require_tenant_admin` + `resolve_tenant_from_jwt` ([dependencies.py:31](src/gateway/dependencies.py:31), [dependencies.py:65](src/gateway/dependencies.py:65)) — tenant is always the caller's own JWT tenant, never a parameter. `UserService.create_user(tenant_id, payload)` ([user_service.py:12](src/gateway/services/user_service.py:12)) is already tenant-agnostic: it takes `tenant_id` as an explicit argument, runs password validation, `max_users` quota check, per-tenant email-uniqueness check, then inserts into `public.tenant_users`. Nothing in that service assumes the caller is a Tenant Admin.

Separately, System Admin already has a fully-scoped cross-tenant surface: `require_system_admin` ([dependencies.py:17](src/gateway/dependencies.py:17)), `TenantService`, and routes under `/api/v1/admin/*` ([admin.py](src/gateway/api/v1/admin.py)) including `GET /api/v1/admin/tenants/{tenant_id}/users` (read-only list, [admin.py:87](src/gateway/api/v1/admin.py:87)). The admin console's tenant detail page ([admin/tenants/[id]/page.tsx](src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx)) already fetches and renders that list under a heading that shows the tenant's `name`/`slug`.

The Tenant Admin's own onboarding UI is a single page ([users/page.tsx](src/portal/src/app/(auth)/users/page.tsx)) with an inline create form bound to `ROLES = ["annotator", "business_user", "tenant_admin"]` and `POST /api/v1/users`.

## Goals / Non-Goals

**Goals:**
- Let System Admin create a `tenant_admin`, `business_user`, or `annotator` in any explicitly-chosen tenant.
- Reuse `UserService.create_user` as the single source of truth for creation business logic (quota, password rules, per-tenant uniqueness, tenant-active check, audit logging) for both roles.
- Leave the Tenant Admin flow's route, request/response shape, and authorization dependency byte-for-byte unchanged; leave its UI wording unchanged (both flows use the same wording, not different wording).
- Make the target tenant unambiguous in the UI before submission.
- Guarantee that a request that reaches `UserService.create_user` for an inactive target tenant is rejected, regardless of which route called it.
- Record who created a user (actor email + role) so cross-tenant creation is auditable.

**Non-Goals:**
- Editing or deactivating users cross-tenant as System Admin (creation only — see Open Questions in proposal.md).
- Any change to `tenant_users` schema, migrations, or the quota model.
- Cross-tenant email uniqueness (uniqueness stays per-tenant, matching existing `uq_email_per_tenant`).
- Notifications/emails on user creation (none exist today for either role) — the new audit event is not a notification.
- Any new or combined authorization dependency — `require_system_admin` and `require_tenant_admin` are reused exactly as they exist today.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|----------------------------|
| ADR-009-system-admin-sets-training-hyperparameters | System Admin actions get their own endpoint rather than widening a tenant-facing one, even when they share underlying logic. | Confirms the chosen approach: a distinct `POST /api/v1/admin/tenants/{tenant_id}/users` endpoint, not a role-widened `POST /api/v1/users`. |

ADR-001 (tenant-data-isolation, schema-per-tenant) has **Status: Proposed**, not Accepted, and current code (`user_service.py`, `dependencies.py`) already implements isolation via a shared `public.tenant_users` table filtered by `tenant_id` column rather than per-tenant Postgres schemas — the accepted, in-force reality diverges from that ADR's draft decision. This design follows the code's actual (row-scoped) isolation model, not ADR-001's draft schema-per-tenant model, and does not attempt to reconcile them.

## Decisions

### Decision 1: New endpoint, not a widened `POST /api/v1/users`

**Choice:** Add `POST /api/v1/admin/tenants/{tenant_id}/users`, gated by `require_system_admin`, alongside the unchanged `POST /api/v1/users` (still `require_tenant_admin`-only).

**Rationale:** `resolve_tenant_from_jwt` explicitly rejects `tenant_id == "system"` ([dependencies.py:67](src/gateway/dependencies.py:67)), so a System Admin's JWT has no usable tenant context — the caller-derived-tenant model that `POST /api/v1/users` relies on structurally cannot serve System Admin without a path/body-supplied `tenant_id`, which changes its contract. A separate route keeps each endpoint's authorization model single-purpose and matches the precedent in ADR-009 (System Admin actions get dedicated endpoints under `/api/v1/admin/*` rather than added conditionals inside tenant-facing routes) and the existing pattern of `/api/v1/admin/tenants/{tenant_id}/users` already existing for the GET case.

**Alternatives considered:**
- Widen `POST /api/v1/users` to accept `system_admin` and an optional `tenant_id` body field — rejected: couples two different authorization/tenant-resolution models in one handler, risks a system_admin-with-no-tenant_id falling through `resolve_tenant_from_jwt`'s `"system"` rejection path in a confusing way, and breaks the proposal's explicit requirement that the existing flow stay unchanged.
- Add a `tenant_id` query param to the existing endpoint, defaulted from JWT — rejected: same coupling problem, plus silently-optional tenant targeting is easy to misuse.

### Decision 2: Reuse `UserService.create_user` as-is, no new authorization abstraction

**Choice:** The new route calls the exact same `UserService.create_user(tenant_id, payload, ...)` used today. Authorization is the existing `require_system_admin` dependency on the new route and the existing `require_tenant_admin` dependency on `POST /api/v1/users` — both used exactly as they are today. No new dependency, no combined/parameterized role-check helper is introduced; the two routes simply declare different existing dependencies, which is sufficient because they are genuinely different endpoints with different tenant-resolution mechanics (path vs. JWT), not one endpoint needing to branch on caller role.

**Rationale:** The service is already tenant-parameterized and contains all the business rules (password validation, quota, per-tenant email uniqueness) that must apply identically regardless of which admin role initiated creation — duplicating this logic would risk drift (e.g., a quota bypass for System Admin-created users). On authorization: `require_system_admin` and `require_tenant_admin` ([dependencies.py:17](src/gateway/dependencies.py:17), [dependencies.py:31](src/gateway/dependencies.py:31)) are each a single `role != "x"` check — introducing a combined dependency (e.g., accepting a set of allowed roles) would be premature abstraction for two call sites that already have distinct, adequate checks.

**Alternatives considered:**
- New `AdminUserService` with its own creation logic — rejected: pure duplication of `UserService.create_user`, exactly the sort of drift risk the proposal calls out as a goal to avoid.
- A combined `require_tenant_or_system_admin`-style dependency parameterized by allowed roles — rejected: no call site needs to accept both roles on one route; each route has exactly one allowed role today, so a combined dependency adds indirection without removing any duplication.

### Decision 3: Tenant-active validation moves into `UserService.create_user`

**Choice:** `UserService.create_user` is extended to look up the target tenant's `status` alongside `max_users` (single query, no new round-trip) and raise `TenantInactiveError` (403) if the tenant is not `active`, before proceeding to the quota/uniqueness checks.

**Rationale:** Today this check only exists incidentally, via `resolve_tenant_from_jwt` ([dependencies.py:65-79](src/gateway/dependencies.py:65)), which the Tenant Admin route depends on but the new System Admin route does not (and structurally cannot, per Decision 1 — System Admin has no per-tenant JWT to resolve). Without this change, the System Admin route would be able to create users in a deactivated tenant, and there would be a real window between a System Admin opening the create-user form and submitting it during which the target tenant could be deactivated with no server-side re-check. Placing the check inside the shared service, rather than duplicating an inactive-tenant check in the new route, guarantees both callers get identical behavior from one place, matching the proposal's assumption that "the same tenant validation performed by `UserService.create_user()` should continue to apply regardless of origin."

**Alternatives considered:**
- Add a redundant `TenantService.get_tenant(tenant_id)` status check in the new admin route only — rejected: duplicates a check that already conceptually belongs to "can a user be created in this tenant right now," which is squarely `UserService.create_user`'s responsibility; leaves the Tenant Admin path's protection dependent on an unrelated middleware dependency instead of the service itself.
- Leave as-is, relying on `TenantService.get_tenant` (existence only, no status filter) before calling `create_user` — rejected: this is exactly the gap identified above; `get_tenant` does not reject inactive tenants, so it provides no real protection for the System Admin path.

### Decision 4: Audit logging added to `UserService.create_user`

**Choice:** `UserService.create_user` accepts `actor_email: str = ""` and `actor_role: str = ""` (mirroring `TenantService.create_tenant`'s existing signature, [tenant_service.py:13](src/gateway/services/tenant_service.py:13)) and, on successful creation, records a `user.create` audit event via the existing `AuditService.record` ([audit_service.py:11](src/gateway/services/audit_service.py:11)) with `actor=actor_email`, `role=actor_role`, `target=<new user's email>`, `tenant_id=<target tenant>`, `kind=AuditEventKind.create`. Both routes pass `actor_email`/`actor_role` from `request.state`, exactly as `admin.py`'s existing tenant routes already do ([admin.py:32-34](src/gateway/api/v1/admin.py:32)).

**Rationale:** User creation currently produces zero audit trail for either role — `AuditService` is used for tenant lifecycle events only. Once System Admin can create users cross-tenant, "who created this user, and were they that tenant's own admin or a platform admin" becomes a real question with no answer today; the existing audit infrastructure already solves exactly this shape of problem (actor + role + action + target + tenant) for tenant lifecycle events, so extending it to user creation is a direct application of an established pattern, not a new one. Applying it inside the shared service means the Tenant Admin path gets an audit trail too, at no extra cost, closing an existing gap rather than introducing an asymmetry between the two creation paths.

**Alternatives considered:**
- Audit only System Admin-initiated creations, leave Tenant Admin path unaudited — rejected: creates an inconsistent audit trail (some `tenant_users` rows traceable, most not) and requires the service to know which caller it is, reintroducing the kind of role-branching Decision 2 avoids.
- A dedicated `user.created` webhook/event bus instead of `AuditService` — rejected: no event bus exists in this codebase; `AuditService` already exists, is already used for comparable admin actions, and needs no new infrastructure.

### Decision 5: Frontend — extract shared `CreateUserForm`, mount on tenant detail page, reuse existing terminology

**Choice:** Extract the create-form JSX/state from `users/page.tsx` into `src/portal/src/components/users/CreateUserForm.tsx`, accepting props `{ roles: Role[], onSubmit, tenantLabel?: string }`. Tenant Admin's page passes no `tenantLabel` (implicit own-tenant, unchanged UX). The admin tenant-detail page passes `tenantLabel={`${tenant.name} (${tenant.slug})`}` and an `onSubmit` that posts to `/api/v1/admin/tenants/{id}/users`, and renders the form under the existing "Users" section next to the current read-only table. The toggle button and form heading keep the Tenant Admin page's exact existing wording — "Create User" (button, [users/page.tsx:125](src/portal/src/app/(auth)/users/page.tsx:125)) and "New User" (panel heading, [users/page.tsx:131](src/portal/src/app/(auth)/users/page.tsx:131)) — rather than introducing new wording like "Add User" on the admin console side.

**Rationale:** The proposal explicitly asks to reuse the existing onboarding experience and extend the existing form (tenant + role selection) rather than duplicate it. The tenant detail page already establishes tenant context visually (`tenant.name`, `tenant.slug` shown at the top of the page, [page.tsx:108-109](src/portal/src/app/(auth)/admin/tenants/[id]/page.tsx:108)); showing that same label inside the form header satisfies "clearly communicate which tenant" without adding a tenant picker widget, since the tenant is already fixed by the page the admin is on.

**Alternatives considered:**
- A separate cross-tenant "Users" page under `/admin/users` with a tenant `<select>` — rejected: proposal asks to reuse the existing experience where practical; the tenant detail page already provides tenant selection (by navigating there) and tenant context display, so a second, parallel tenant-picker UI would duplicate that navigation and increase surface area without benefit.
- Duplicate the form markup into the tenant detail page instead of extracting a shared component — rejected: proposal explicitly asks to avoid duplication; two independently-maintained copies of the same email/password/role form would drift (e.g., password hint text, validation messages).

## Risks / Trade-offs

- [Two endpoints implementing "create a user" could drift in validation/error-handling if one is changed without the other.] → Both call the same `UserService.create_user`; only the authorization dependency and tenant-source differ. Code review checklist item: any change to user-creation business rules touches the shared service, not per-route logic.
- [System Admin creating a `tenant_admin` in a tenant that already has one could be surprising (no "only one tenant_admin" constraint exists today).] → Out of scope: the existing Tenant Admin path already allows multiple `tenant_admin` users per tenant (no uniqueness constraint on role); this change does not alter that behavior for either path.
- [Reusing `TenantService.get_tenant` to validate the path `tenant_id` exists before calling `create_user` adds a query, on top of the status/quota lookup `create_user` now performs itself.] → Accepted trade-off, one extra indexed lookup on an admin-only, low-volume endpoint, to get a clean 404 (nonexistent tenant) distinct from `create_user`'s 403 (inactive tenant) rather than one error path conflating both; matches existing pattern in `list_tenant_users` ([admin.py:87-96](src/gateway/api/v1/admin.py:87)).
- [Adding a tenant-active check and audit call inside the shared `UserService.create_user` changes behavior for the existing Tenant Admin path too (new audit rows appear; a request that was previously blocked pre-service by `resolve_tenant_from_jwt` would now also be blocked inside the service).] → Intentional and low-risk: the Tenant Admin path was already blocked by `resolve_tenant_from_jwt` for inactive tenants, so the service-level check is redundant-but-harmless there (defense in depth, not a behavior change in practice); the new audit rows are strictly additive (no existing reader of `tenant_users` or the creation response is affected).

## Migration Plan

No data migration required (no schema change). Deploy as a standard backend + frontend release:
1. Ship backend `UserService.create_user` extensions (tenant-active check, audit logging) plus tests confirming the existing Tenant Admin path's response shape/status codes are unchanged, then the new admin route and its tests.
2. Ship frontend `CreateUserForm` extraction with tests confirming the Tenant Admin page's behavior and wording are unchanged (regression coverage before adding the new consumer).
3. Ship the admin tenant-detail-page "Create User" UI wired to the new endpoint.
Rollback: revert the route/UI commits independently; no stateful migration to unwind.

## Open Questions

- Same as proposal.md's Open Questions (edit/deactivate parity, cross-tenant duplicate email handling, notifications) — carried forward for verification/tasks scoping, not re-litigated here.
