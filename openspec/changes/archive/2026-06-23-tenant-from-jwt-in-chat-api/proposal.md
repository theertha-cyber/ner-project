## Why

The chatbot service routes redundantly pass `tenant_id` as a URL path parameter (`{tid}`) and then compare it against the JWT-extracted tenant. This is a needless duplication — the JWT token already carries the authenticated tenant context. Every endpoint duplicates the mismatch check (`if tenant_id != tid`), and the URL includes a parameter that serves no independent routing purpose. Removing `{tid}` from paths simplifies the API surface, eliminates a class of errors (tenant mismatch bugs), and aligns with the principle that auth context comes from the token, not the URL.

## What Changes

- **BREAKING**: Remove `{tid}` path parameter from all chatbot API route prefixes and handler signatures
- Remove `tid` parameter from every chat and widget-keys endpoint handler
- Remove tenant mismatch checks (`if tenant_id != tid`) from route handlers
- Update gateway proxy routes to remove `{tid}` from proxied paths
- Update existing spec scenarios that reference `{tid}` in URL paths
- Keep public widget endpoints as-is (they use widget key auth, not JWT)

## Capabilities

### New Capabilities

*(None — this is a refactor of existing capability.)*

### Modified Capabilities

- `chat-api`: Chat and widget-keys API routes no longer accept `{tid}` path parameter. Tenant identity is derived exclusively from the JWT token. API paths change from `/api/v1/tenants/{tid}/chat/...` to `/api/v1/chat/...` and `/api/v1/widget-keys/...`. Gateway proxy routes are updated to match.

## Impact

- **src/chat_api/api/v1/chat.py**: Remove `{tid}` from router prefix, remove `tid` param from all 4 handlers, remove tenant mismatch checks
- **src/chat_api/api/v1/widget_keys.py**: Remove `{tid}` from router prefix, remove `tid` param from all 3 handlers, remove tenant mismatch checks
- **src/gateway/api/v1/chat_proxy.py**: Remove `{tid}` from all proxy route paths and handler signatures; update internal proxy URLs
- **openspec/specs/chat-api/spec.md**: Update all scenario URL paths that reference `{tid}`
- Any client code (portal UI) that calls these endpoints will need to update its request URLs

## Open Questions

- Does the portal UI or any other client currently call these endpoints with the `{tid}` pattern? (Assumption: yes — they will need URL updates)
- Should the widget-keys endpoints also move, or stay tenant-scoped since they are admin-only? (Decision: move them — they already have JWT auth and `tenant_id` from `request.state`)
