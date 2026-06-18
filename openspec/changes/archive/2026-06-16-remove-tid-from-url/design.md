## Context

The extraction service and model serving service currently embed `{tid}` in their URL path prefixes (`/api/v1/tenants/{tid}/...` and `/internal/v1/tenants/{tid}/...`). Every endpoint handler then reads `tenant_id` from both the URL path parameter and `request.state.tenant_id` (set by `TenantContextMiddleware` from JWT), and validates they match. This is redundant — the middleware already extracts tenant_id from the JWT and makes it available on `request.state`.

Other services (document service, annotation service, training service models) do NOT require `{tid}` in the URL — they rely solely on `request.state.tenant_id`. This inconsistency forces external callers to manually include `tenant_id` in extraction URLs when it is already authenticated in the JWT.

The gateway's extraction proxy mirrors this pattern, accepting `{tid}` in its prefix and forwarding it to the downstream extraction service.

## Goals / Non-Goals

**Goals:**

- Remove `{tid}` from all extraction service endpoint URLs (gateway proxy + direct service)
- Remove `{tid}` from all model serving internal endpoint URLs
- Remove redundant `tid` path parameter and `tid != tenant_id` validation from all affected handlers
- Update all callers that construct the old URLs
- Maintain identical tenant-scoping behavior — tenant_id continues to be resolved from JWT via middleware

**Non-Goals:**

- Not changing how tenant_id is resolved for services that already work correctly (document, annotation, training)
- Not changing the gateway user management endpoints (which use slug-based tenant resolution with `resolve_tenant` dependency)
- Not adding or removing endpoints — only changing their path structure
- Not changing authentication/authorization flow

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate PostgreSQL schemas per tenant | Tenant_id must still be available for schema resolution — unchanged (still in JWT → middleware → `request.state`) |
| ADR-003 | Shared Model Serving Layer with per-tenant routing, endpoint `POST /internal/v1/tenants/{tenant_id}/infer` | The endpoint URL is part of the ADR-003 architecture spec. This design changes that URL — ADR-003 should be updated or superseded to reflect `POST /internal/v1/infer` with tenant_id carried via JWT |
| ADR-008 | Base model as default (version 0) for tenants without promoted fine-tuned model | No constraint — tenant resolution is orthogonal to model selection |

## Decisions

### Decision 1: Remove `{tid}` from URL path, rely entirely on JWT for tenant context

**Choice:** Strip `{tid}` from the router prefix in extraction service, model serving service, and gateway extraction proxy. Remove the `tid` path parameter from every handler. Remove the `tid != tenant_id` validation guard.

**Rationale:**
- Matches the established pattern in document, annotation, and training services — they do not require `{tid}` in URLs
- Eliminates a redundant data source (tenant_id comes from JWT, not URL, so URL-based tenant_id is always validated against JWT — making it dead weight)
- Simplifies handler signatures and reduces boilerplate
- Breaking change is acceptable — extraction API is currently in pre-release stage
- The downstream extraction service and model serving service already have the `TenantContextMiddleware` that sets `request.state.tenant_id`

**Alternatives considered:**
- Keep `{tid}` in URL — ruled out because it perpetuates inconsistency with other services and forces external callers to provide redundant information
- Add `{tid}` to all other services for consistency — ruled out because it would be a worse API design (requiring authenticated users to repeat information already in their JWT)

### Decision 2: Extraction engine `infer()` function must pass JWT to model serving

**Choice:** The `infer()` function in `extraction_engine.py` (used by the synchronous extract endpoint) currently does not forward any JWT. After removing `{tid}` from the inference URL, the model serving service has no other way to determine the tenant_id. The `infer()` function must accept and forward the JWT as an `Authorization` header.

**Rationale:**
- The worker.py caller already forwards a JWT — this brings the synchronous path in line with the async batch path
- Model serving middleware already decodes JWT to set `request.state.tenant_id` — no changes needed on the serving side
- The extraction endpoint has access to the original request headers (including `Authorization`) via `request.headers`

**Alternatives considered:**
- Pass tenant_id as a query parameter — ruled out because it exposes tenant_id in logs/URLs and breaks the pattern of JWT-only tenant resolution
- Add a separate header like `X-Tenant-ID` — ruled out because the JWT is already available and is the canonical source

### Decision 3: Gateway extraction proxy forwards Authorization header transparently

**Choice:** The gateway extraction proxy already forwards `request.headers` (including `Authorization`) to the downstream extraction service via httpx. No changes to header forwarding logic are needed — the proxy simply forwards what it receives from the external caller.

**Rationale:**
- Existing `_proxy()` function passes `headers = dict(request.headers)` — this includes the JWT
- The extraction service `TenantContextMiddleware` will decode the JWT and set `request.state.tenant_id`
- No additional configuration needed

## Risks / Trade-offs

- [Callers that construct inference/warmup URLs directly (bypassing the gateway) must update their URLs] → All known callers (extraction engine, worker, training service warmup) are updated as part of this change
- [Breaking change for any external consumers already using the extraction API] → The API is in pre-release; README documents the old URLs and is updated with the new ones
- [ADR-003 specifies the endpoint URL in its architecture] → A new ADR superseding ADR-003 for the URL change will be created in the adr step

## Migration Plan

1. Update extraction service endpoints (extraction.py, entities.py) — change router prefix, remove `tid` params and `tid != tenant_id` checks
2. Update model serving endpoints (inference.py, warmup.py) — same pattern
3. Update extraction_engine.py — remove tenant_id from URL construction, add JWT forwarding
4. Update worker.py — remove tenant_id from URL construction (JWT already forwarded)
5. Update training_service/models.py `_warmup_model` — remove tenant_id from URL construction (JWT already forwarded)
6. Update gateway extraction proxy — remove `{tid}` from prefix, remove `tid` param from handlers
7. Update tests — fix endpoint URLs
8. Update README — fix documentation
9. Create new ADR to supersede ADR-003's endpoint URL spec

Rollback: Revert the router prefix change in each file. URLs return to previous form. No data migration needed.

## Open Questions

- None. The design is straightforward and follows existing patterns in the codebase.
