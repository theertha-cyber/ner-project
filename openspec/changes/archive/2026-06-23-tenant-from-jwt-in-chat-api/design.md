## Context

The chatbot API routes (chat, conversations, widget-keys) currently accept `{tid}` as a URL path parameter and compare it against `request.state.tenant_id` from the JWT token. The middleware already extracts `tenant_id` from the JWT and validates tenant existence/activity before routes execute. The URL param adds no security value — it introduces the risk of mismatch errors and duplicates a value already available from a trusted source.

The gateway proxy mirrors this pattern, forwarding the `{tid}` path through to the chat service.

## Goals / Non-Goals

**Goals:**
- Remove `{tid}` from all chatbot API route paths
- Remove `tid` parameter from all handler function signatures
- Remove tenant mismatch checks from all route handlers
- Update gateway proxy routes to match new paths
- Keep tenant scoping intact — `request.state.tenant_id` remains the single source of truth

**Non-Goals:**
- Not changing the JWT auth middleware or how `request.state.tenant_id` is set
- Not changing public widget endpoints (they use widget key auth, not JWT)
- Not changing other services (document, annotation, training, etc.)
- Not changing the shared `tenant_context.py` dependency functions

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-007 — Chatbot Architecture with Full RAG and Guardrails | All chatbot interactions MUST be tenant-scoped | Tenant scoping remains enforced via JWT-extracted `request.state.tenant_id` |
| ADR-001 — Tenant Data Isolation via Separate Database Schemas | Database schemas per tenant | Unchanged — schema resolution via `request.state.tenant_id` is preserved |

## Decisions

### Decision 1: Remove `{tid}` entirely from chat API paths

**Choice:** Change routes from `/api/v1/tenants/{tid}/chat/...` to `/api/v1/chat/...` and from `/api/v1/tenants/{tid}/widget-keys` to `/api/v1/widget-keys`.

**Rationale:** The `{tid}` parameter serves no purpose once tenant identity comes from JWT. Removing it simplifies the API surface and eliminates the mismatch check pattern. The router prefix in FastAPI is the single change point — every handler registered on that router automatically gets the new prefix.

**Alternatives considered:**
- Keep `{tid}` as a redundant parameter but stop validating against JWT — adds no value, keeps dead code
- Replace `{tid}` with a non-validating placeholder — worse UX, still pollutes URL

### Decision 2: Remove `tid` mismatch checks from handlers

**Choice:** Delete the `if tenant_id != tid: raise HTTPException(403, "Tenant mismatch")` blocks from all handlers in `chat.py` and `widget_keys.py`.

**Rationale:** With `{tid}` removed from the URL, there is nothing to compare against. Tenant identity comes exclusively from the middleware. The `if not tenant_id` guard remains to ensure the middleware has populated the state.

**Alternatives considered:**
- Keep the checks against a hardcoded value — pointless
- Replace with a FastAPI `Depends(get_tenant_id)` — desirable but out of scope for this focused refactor

### Decision 3: Update gateway proxy routes

**Choice:** Change gateway proxy paths from `/tenants/{tid}/chat/...` to `/chat/...` and proxy URLs from `/api/v1/tenants/{tid}/chat/...` to `/api/v1/chat/...`.

**Rationale:** The gateway is a pass-through. Its paths must match what the chat service exposes. Since the JWT auth happens in the chat service middleware (not the gateway), the gateway does not need to extract or validate tenant from the URL.

**Alternatives considered:**
- Have the gateway strip `{tid}` and inject it from JWT — adds unnecessary complexity since the chat service already handles JWT auth

### Decision 4: Update existing spec scenarios

**Choice:** Update all URL references in `openspec/specs/chat-api/spec.md` to use the new paths.

**Rationale:** The spec is the source of truth. Scenarios referencing `/api/v1/tenants/{tid}/chat` must be updated to `/api/v1/chat` to reflect the new contract.

## Risks / Trade-offs

- [**Client URL breakage**] → All external callers (portal UI, integration tests) must update their request URLs. This is a **BREAKING** change and should be communicated. The `chat_proxy.py` update in the same change ensures gateway clients are handled.
- [**Widget key admin routes move**] → Tenant admins managing widget keys now use `/api/v1/widget-keys` instead of `/api/v1/tenants/{tid}/widget-keys`. The JWT auth on these routes ensures the same access control.
- [**Public widget endpoints unaffected**] → Public routes (`/api/v1/public/chat`, `/api/v1/public/widget.js`) don't use `{tid}` — they use widget key auth, so no change needed.

## Migration Plan

1. Update `chat.py` — router prefix to `/api/v1/chat`, remove `tid` param + mismatch check from all handlers
2. Update `widget_keys.py` — router prefix to `/api/v1/widget-keys`, remove `tid` param + mismatch check from all handlers
3. Update `chat_proxy.py` — remove `{tid}` from all proxy routes, update internal URLs
4. Update `openspec/specs/chat-api/spec.md` — update all URL references
5. Update portal UI client code if it constructs these URLs
6. Deploy as a single PR with clear breaking-change notes

Rollback: Revert the PR. The old routes will be restored.

## Open Questions

- Portal UI may hardcode these URLs — needs verification during implementation
- No in-force ADRs are contradicted by this change
