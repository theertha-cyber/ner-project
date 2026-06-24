## Context

The chat UI page (`src/portal/src/app/(auth)/chat/page.tsx`) makes four types of API calls: list conversations, get conversation messages, delete conversation, and send chat message. All four use raw `fetch()` with `credentials: "include"` but without an `Authorization: Bearer <token>` header. The gateway's `TenantContextMiddleware` requires a valid Bearer JWT token on all authenticated routes and returns 401 when none is present.

Every other authenticated page in the portal uses the `authFetch()` wrapper from `@/lib/auth-fetch`, which injects the JWT access token from a React ref and handles transparent token refresh via the httpOnly refresh cookie. The chat page is the only page that deviates from this pattern.

## Goals / Non-Goals

**Goals:**

- Make the chat page's API calls carry a valid Bearer JWT token matching the rest of the portal
- Use the existing `authFetch` abstraction — no new auth infrastructure
- All four fetch call sites replaced: list conversations, get messages, delete conversation, send message

**Non-Goals:**

- No changes to the chat API service, gateway proxy, or backend auth middleware
- No changes to the auth-fetch library itself (no new prefix routes unless needed)
- No changes to the widget API (it uses API key auth, not JWT)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-005 | OpenCode Agent Boundaries | AI agents may not introduce new auth patterns without review — using established `authFetch` pattern complies |
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Chat API exposes authenticated endpoints via gateway; this fix ensures the frontend actually sends auth tokens |

## Decisions

### Decision 1: Replace raw fetch with authFetch

**Choice:** Replace all 4 `fetch()` calls in `chat/page.tsx` with `authFetch()`, importing from `@/lib/auth-fetch`.

**Rationale:** `authFetch` is the established, tested pattern used by every other authenticated page. It injects the Bearer token from the React ref, adds `credentials: "include"`, and transparently handles 401 → token refresh → retry. The gateway middleware already validates these tokens — the chat page simply wasn't sending them.

**Alternatives considered:**
- Manually adding `Authorization: Bearer` headers to each fetch — would duplicate auth logic and miss the transparent refresh handling that `authFetch` provides
- Adding cookie-based session auth to the gateway — disproportionate change for a single page fix; would require middleware changes, security review, and affect all services

### Decision 2: Do not add chat API paths to authFetch's resolveUrl prefix list

**Choice:** Use relative paths (`/api/v1/chat/...`) as-is without adding them to the `resolveUrl` prefix map.

**Rationale:** The frontend (Next.js dev server or production build) is served from the same origin as the gateway, so relative paths resolve correctly. The prefix list in `authFetch` is only needed when service endpoints live on different ports — the chat API is accessed through the gateway proxy at the same origin.

**Alternatives considered:**
- Adding `/api/v1/chat` to the prefix map — unnecessary since the dev server proxies to the gateway; would couple authFetch to chat-api's routing

## Risks / Trade-offs

- [If the frontend is deployed on a different origin than the gateway (e.g., separate subdomain)] → The relative path would fail. Mitigation: Add `/api/v1/chat` to `resolveUrl` prefix list when that deployment topology is used.

## Migration Plan

1. Add `import { authFetch } from "@/lib/auth-fetch"` to `chat/page.tsx`
2. Replace `fetch(CHAT_API_BASE + "/conversations", { credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations")`
3. Replace `fetch(CHAT_API_BASE + "/conversations/" + convId, { credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations/" + convId)`
4. Replace `fetch(CHAT_API_BASE + "/conversations/" + convId, { method: "DELETE", credentials: "include" })` with `authFetch(CHAT_API_BASE + "/conversations/" + convId, { method: "DELETE" })`
5. Replace `fetch(CHAT_API_BASE, { method: "POST", headers, credentials: "include", body })` with `authFetch(CHAT_API_BASE, { method: "POST", headers, body })`

Rollback: Revert the single file change.

## Open Questions

- How is the portal deployed relative to the gateway? If separate origins, `/api/v1/chat` must be added to `authFetch`'s `resolveUrl` prefix list.
