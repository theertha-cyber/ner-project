## Context

The gateway's users router (`src/gateway/api/v1/users.py`) exposes user management endpoints under `/api/v1/tenants/{tenant_id}/users`. The `{tenant_id}` segment is named as an identifier but is treated by the middleware as a **slug** (`WHERE slug = :slug`). The `resolve_tenant` dependency then cross-checks that slug against the JWT's `tenant_id` claim.

This creates a redundant and misleading requirement: a tenant admin authenticated via JWT must also supply their tenant's slug in the URL to access their own users — a slug they may not know. The pattern is inconsistent with `entity_types.py`, which already uses `resolve_tenant_from_jwt` and works without any URL tenant segment.

The `resolve_tenant_from_jwt` dependency already exists in `src/gateway/dependencies.py` and does exactly what is needed: validates tenant from the JWT claim alone, without a URL parameter.

## Goals / Non-Goals

**Goals:**

- Remove the `{tenant_id}` slug requirement from user management URLs
- Make tenant resolution for users consistent with entity types (JWT-only)
- Fix the Swagger UI usability issue (no manual slug entry required)
- Correct the spec to match the intended design

**Non-Goals:**

- Changing any business logic (user creation, role enforcement, quota checks)
- Changing response shapes or status codes
- Adding pagination or new query parameters
- Addressing any other endpoint that uses `resolve_tenant`

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | JWT `tenant_id` is the authoritative tenant identity at the API gateway layer; all tenant-scoped operations must validate it | `resolve_tenant_from_jwt` validates the JWT `tenant_id` claim and confirms the tenant is active — this satisfies the ADR requirement. The URL slug approach was an additive cross-check, not the mandated mechanism. |

## Decisions

### Decision 1: Use `resolve_tenant_from_jwt` and drop the URL slug segment

**Choice:** Replace `resolve_tenant` with `resolve_tenant_from_jwt` in all users router endpoints, and change the router prefix from `/api/v1/tenants/{tenant_id}/users` to `/api/v1/users`.

**Rationale:** The JWT `tenant_id` claim is already the authoritative tenant identity per ADR-001. `resolve_tenant_from_jwt` validates it against the database (confirms tenant exists and is active) and is already used by `entity_types.py`. The URL slug was a redundant cross-check that added friction without adding security — a tenant admin's JWT already scopes them to exactly one tenant.

**Alternatives considered:**
- Keep URL slug but fix the parameter name to `{tenant_slug}` — still requires users to know/supply their slug, doesn't fix the Swagger friction, and adds no security value since the JWT already enforces tenant scope.
- Keep URL slug and auto-populate it from JWT in Swagger (via `x-default` or similar) — non-standard, fragile, and still redundant.

### Decision 2: Cut the old URL immediately, no deprecated alias

**Choice:** Remove `/api/v1/tenants/{tenant_id}/users` with no forwarding route.

**Rationale:** This is an internal project. There are no external consumers and no SLA that requires a deprecation window. A temporary alias would add dead code, test surface, and confusion about which path is canonical.

**Alternatives considered:**
- 301 redirect from old path to new — FastAPI routing doesn't support dynamic redirects for path-parameterised routes cleanly; adds complexity for zero benefit given no external consumers.

## Risks / Trade-offs

- [Breaking URL change may surprise developers used to the old path] → Communicated via this change and the spec update; Swagger UI will reflect the new path immediately.
- [Other endpoints using `resolve_tenant` may have the same issue] → Out of scope for this change; flagged as a separate concern. Only `users.py` is changed here.

## Migration Plan

1. Update `src/gateway/api/v1/users.py`: change router prefix and swap dependency.
2. Update `openspec/specs/tenant-user-mgmt/spec.md`: rewrite scenarios to use `/api/v1/users` and `resolve_tenant_from_jwt`.
3. Restart the gateway service.
4. Verify in Swagger UI: users endpoints should now appear under `/api/v1/users` and work with Bearer token alone.

Rollback: revert the two file changes and restart. No database or migration changes involved.

## Open Questions

- Are there other routers in the gateway that use `resolve_tenant` with the same redundancy pattern? (Out of scope here but worth a follow-up audit.)
