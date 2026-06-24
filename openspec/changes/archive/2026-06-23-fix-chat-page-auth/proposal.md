## Why

The chat UI page at `src/portal/src/app/(auth)/chat/page.tsx` uses raw `fetch()` with only `credentials: "include"` for all API calls, but the gateway's `TenantContextMiddleware` requires an `Authorization: Bearer <token>` header. As a result, all chat API requests (list conversations, send messages, delete conversations) return 401 Unauthorized, making the chat UI completely non-functional for authenticated users.

## What Changes

- Replace all `fetch()` calls in `chat/page.tsx` with the `authFetch()` wrapper from `@/lib/auth-fetch` that injects the Bearer token and handles transparent token refresh
- Add import for `authFetch` to the chat page
- Remove redundant `credentials: "include"` options (authFetch adds these automatically)
- Ensure `/api/v1/chat` paths are handled by `authFetch`'s `resolveUrl` (either by adding it to the prefix list or confirming the dev server proxy handles it)

## Capabilities

### New Capabilities

*(none — this is a bug fix to an existing capability)*

### Modified Capabilities

- `chat-ui`: Fix authentication mechanism for all API calls — replace raw `fetch` with `authFetch` so that requests carry a valid Bearer token and are accepted by the gateway middleware

## Impact

- **Frontend only**: Single file change in `src/portal/src/app/(auth)/chat/page.tsx`
- **No API changes**: The chat API endpoints, gateway proxy, and chat-api service remain unchanged
- **No database changes**: No migrations or schema changes
- **Downstream**: Chat widget API is unaffected (it uses API key auth, not JWT)

## Open Questions

- Should `/api/v1/chat` be added to `authFetch`'s `resolveUrl` prefix list to prepend `GATEWAY_URL`, or does the dev server / deployment proxy handle it already? (If the frontend is served by the same origin as the gateway, the relative path works as-is.)
