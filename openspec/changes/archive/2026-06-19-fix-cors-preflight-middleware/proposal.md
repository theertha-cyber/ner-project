## Why

CORS preflight requests (HTTP OPTIONS) sent by the browser to the document service (port 8001) are rejected with 401 by `TenantContextMiddleware` before `CORSMiddleware` can respond with the required CORS headers. This surfaces as a "Failed to load document" error whenever an annotator clicks a task in the annotation workspace. The annotation service (port 8005) has the identical bug but is masked by a cached CORS preflight from the task-list request that fires on page mount.

## What Changes

- Add an OPTIONS method exemption at the top of `dispatch()` in `src/document_service/middleware/tenant_context.py` — pass OPTIONS through to `call_next` without auth checks.
- Add the same OPTIONS method exemption to `src/annotation_service/middleware/tenant_context.py` — eliminates the latent bug that is currently hidden by the CORS preflight cache.
- No API contracts, data models, or frontend code change.

## Capabilities

### New Capabilities

- `cors-preflight-passthrough`: Both `TenantContextMiddleware` implementations must allow OPTIONS requests to pass through unauthenticated so the CORS layer can respond with the correct preflight headers.

### Modified Capabilities

<!-- No existing spec-level requirements change. This is a middleware correctness fix. -->

## Impact

- **Files changed**: `src/document_service/middleware/tenant_context.py`, `src/annotation_service/middleware/tenant_context.py`
- **Services affected**: document-service (port 8001), annotation-service (port 8005)
- **Frontend**: no change — `authFetch` routing and retry logic are unchanged
- **Security**: OPTIONS requests carry no credentials and are used only for CORS negotiation; exempting them from auth does not expose protected data

## Open Questions

- No open questions. The fix is deterministic and fully contained within the two middleware files.
