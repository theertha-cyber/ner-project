## Context

The platform runs multiple FastAPI services (gateway :8000, document :8001, annotation :8005) each accessed directly from the Next.js frontend via `authFetch`. Every service uses two middleware layers:

1. `TenantContextMiddleware` (extends `BaseHTTPMiddleware`) — validates the Bearer token, resolves the tenant, and stores context on `request.state`.
2. Starlette's `CORSMiddleware` — responds to CORS preflight (OPTIONS) requests with the appropriate `Access-Control-Allow-*` headers.

Both middleware are registered in the same order in every service:

```python
app.add_middleware(TenantContextMiddleware)
app.add_middleware(CORSMiddleware, ...)
```

Despite `CORSMiddleware` being registered last (making it outermost in the Starlette stack), browser network traces show that OPTIONS preflight requests to the document service return **401** — the response signature of `TenantContextMiddleware` — rather than a proper CORS preflight response. The annotation service exhibits the same code path but is shielded by the browser's CORS preflight cache, which was populated when the task-list query (port 8005) was first executed on page mount.

The result is: clicking any annotation task triggers `GET /api/v1/documents/{id}/text` to port 8001 (a fresh origin with no cached preflight), the browser sends OPTIONS, gets 401 with no CORS headers, and blocks the request with a CORS error. The frontend catches the network exception and shows "Failed to load document".

## Goals / Non-Goals

**Goals:**
- OPTIONS requests reach the CORS layer unauthenticated so the browser receives a valid preflight response.
- Fix is applied to both `TenantContextMiddleware` files (document service and annotation service) to eliminate the latent bug.
- No change to auth behaviour for all other HTTP methods.

**Non-Goals:**
- Refactoring middleware into a shared module — that is a separate concern.
- Changing CORS configuration (`allow_origins`, `allow_headers`, etc.).
- Any frontend changes.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Each tenant's data is schema-isolated; JWT carries `tenant_id` | Auth middleware must still validate token and set tenant context for all non-preflight requests |
| ADR-005-opencode-agent-boundaries | Services own their own middleware stacks | Fix is applied per-service; no shared middleware abstraction is introduced here |

## Decisions

### Decision 1: Exempt OPTIONS in `TenantContextMiddleware`, not in a new middleware layer

**Choice:** Add a guard at the top of `TenantContextMiddleware.dispatch()` that short-circuits to `call_next(request)` when `request.method == "OPTIONS"`.

**Rationale:** The problem is that `TenantContextMiddleware` runs before the CORS layer can respond. Passing OPTIONS through via `call_next` lets the rest of the middleware stack (including `CORSMiddleware`) handle the preflight correctly and add the required `Access-Control-Allow-*` headers to the response on its way back out. This is a minimal, surgical fix with no new abstractions and no risk of altering auth logic for other methods.

**Alternatives considered:**
- **Add a standalone `CORSPreflightMiddleware` registered before `TenantContextMiddleware`** — achieves the same result but adds an extra class and registration step; more code for no benefit.
- **Move `CORSMiddleware` registration before `TenantContextMiddleware`** — counterintuitively this makes `TenantContextMiddleware` the outermost layer in Starlette's reversed-stack model, which is the exact configuration already in effect and causing the bug. Not a fix.
- **Return an early 200 response with manually constructed CORS headers from `TenantContextMiddleware`** — duplicates CORS logic, risks diverging from `CORSMiddleware` config.

### Decision 2: Apply the fix to both services simultaneously

**Choice:** Patch both `src/document_service/middleware/tenant_context.py` and `src/annotation_service/middleware/tenant_context.py` in the same change.

**Rationale:** The annotation service has an identical latent bug. Fixing only the document service leaves the annotation service one cache-clear away from the same user-visible failure.

## Risks / Trade-offs

- [OPTIONS requests bypass auth and tenant validation] → This is acceptable and expected. OPTIONS preflights carry no user data and receive no protected data — the browser sends them automatically before the credentialled request. Skipping auth on OPTIONS is the standard pattern for FastAPI + CORS stacks.
- [Annotation service preflight cache may mask the fix for existing sessions] → On first page load after the fix is deployed, the browser may already have a cached preflight for port 8005. This is harmless — the cache will expire and the new code path will serve future preflights correctly.

## Migration Plan

1. Apply the two-line guard to both middleware files.
2. Restart both services (`document-service`, `annotation-service`).
3. Verify by opening the annotation workspace in a browser with DevTools open: clicking a task should no longer show a CORS error on the `text` request, and the document viewer should populate.
4. No database migration. No rollback complexity — reverting removes the four added lines.

## Open Questions

None. The fix is fully deterministic and contained.
