## Context

The gateway's auth endpoints (`login`, `refresh`, `logout`) return JSON responses with no cookies — the `refresh` endpoint currently expects the refresh token in the request body. The portal's prototype `auth.tsx` stored both access and refresh tokens in `localStorage`, which is XSS-vulnerable and violates the security model described in the SP-02 decomposition. The `authFetch` stub passes through to raw `fetch` with no token injection.

This change ships the real auth layer: access token in React memory, refresh token in an `httpOnly` cookie managed entirely by the backend, and a single `authFetch` interceptor that all subsequent portal specs will use for every API call.

## Goals / Non-Goals

**Goals:**
- Access token stored only in React context (`useRef` for the raw value; `useState` for the user object that drives re-renders).
- Refresh token set and cleared exclusively by the backend as an `httpOnly; Secure; SameSite=Strict` cookie — JavaScript never reads or writes it.
- `authFetch` is safe to call concurrently: at most one in-flight refresh, shared via a module-level singleton.
- Login page matches the mockup's glassmorphism design. Demo role chips rendered only when `NEXT_PUBLIC_DEMO_MODE=true`.
- `<RequireAuth>` redirects to `/login` on first render if `user` is null — no blocking loading state (per user preference).
- On page reload, `AuthProvider` calls `POST /auth/refresh` (browser auto-sends the cookie); session is silently restored if the cookie is valid.

**Non-Goals:**
- Multi-tab session synchronisation (BroadcastChannel or storage events).
- PKCE / OAuth 2.0 / SSO — JWT email+password only.
- Session inactivity timeout on the client.
- Role-switcher UI (that is SP-03's concern).
- Password reset / forgot-password flow.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | JWT must carry `tenant_id`; backend must validate it on every request — no client-side tenant switching. |
| ADR-004 | OpenSpec spec-driven governance | All capabilities must have specs before implementation; this design feeds directly into the spec and verification artifacts. |
| ADR-005 | OpenCode agent permissions and boundaries | Agent-generated code must not introduce new ambient credentials; refresh token managed server-side satisfies this. |

## Decisions

### Decision 1: Access token in `useRef`, user object in `useState`

**Choice:** `AuthProvider` keeps `accessTokenRef = useRef<string | null>(null)` for the raw token string and `const [user, setUser] = useState<AuthUser | null>(null)` for the decoded user claims. `authFetch` reads `accessTokenRef.current` synchronously. Login/logout mutations update both.

**Rationale:** Storing the access token in state would cause every `authFetch` call to re-render consumers that subscribed to the context value. The ref holds the token without triggering renders; only the `user` object (needed to gate UI) lives in state.

**Alternatives considered:**
- Token in state — causes unnecessary re-renders across the whole tree on every silent refresh.
- Token in a closure captured at provider mount — stale closure issue; ref avoids this.

### Decision 2: Concurrent-safe refresh via module-level singleton

**Choice:** A module-level `let pendingRefresh: Promise<string> | null = null` in `auth-fetch.ts`. When a 401 is detected, the interceptor checks: if `pendingRefresh` is null, it creates a new refresh request and assigns the promise; if it already exists, it awaits the existing promise. The promise resolves with the new access token string (obtained via `AuthContext`'s `refreshSession()` callback, passed into `authFetch` at construction time).

**Rationale:** Multiple parallel `authFetch` calls can all receive a 401 simultaneously. A module-level singleton ensures only one refresh request goes out regardless of how many concurrent calls detected the 401. A `useRef` inside the context cannot be accessed from the `authFetch` module without dependency injection; a module-level variable is simpler and avoids circular context dependencies.

**Alternatives considered:**
- `useRef` inside `AuthProvider` — would require `authFetch` to import from the context module, creating a circular dependency.
- Semaphore/mutex library — unnecessary complexity for a single-value case.

### Decision 3: Backend `refresh` reads from cookie, not body

**Choice:** `POST /api/v1/auth/refresh` reads the refresh token exclusively from the `refresh_token` cookie (via FastAPI's `Request.cookies`), not from the JSON body. The body parameter is removed. `login` and `refresh` both call `Response.set_cookie(...)` on their `JSONResponse`. `logout` calls `Response.delete_cookie(...)`.

**Rationale:** If the refresh token were also accepted in the body, JavaScript code could still read it from `localStorage` and call the endpoint directly, defeating the purpose of the `httpOnly` cookie. Accepting the token only from the cookie means no JS can ever access it.

**Alternatives considered:**
- Keep body-based refresh for backward compat, add cookie as alternative — creates two refresh code paths, harder to audit, and still exposes the body-based attack surface.

### Decision 4: `Secure` cookie flag is environment-conditional

**Choice:** The gateway reads `settings.ENVIRONMENT` (already present in `src/gateway/core/config.py`). If `ENVIRONMENT == "production"`, `secure=True` on `set_cookie`. Otherwise `secure=False` to support plain HTTP on localhost.

**Rationale:** Browsers reject `Secure` cookies on `http://localhost`, breaking local development entirely. The conditional approach matches standard practice.

**Alternatives considered:**
- Always `secure=True` — breaks local dev without HTTPS setup.
- Always `secure=False` — ships insecure cookies to production.

### Decision 5: On-mount silent refresh, immediate child rendering

**Choice:** `AuthProvider` launches `POST /auth/refresh` in a `useEffect` on mount. While the request is in-flight, `user` is `null`. `<RequireAuth>` renders the redirect to `/login` immediately if `user === null` — no loading spinner. Once the refresh succeeds, `user` is set and the app re-renders the authenticated tree.

**Rationale:** The user explicitly chose "render immediately, redirect if not authed" over a blocking loading screen. The tradeoff is a brief redirect flash on reload if the user was authenticated, but this is acceptable for the MVP.

**Alternatives considered:**
- Block rendering with a spinner — requires an `isInitializing` state and adds complexity; rejected by user preference.
- Restore from `localStorage` — violates the access-token-in-memory requirement.

### Decision 6: `authFetch` routes URLs by service prefix

**Choice:** `authFetch` checks the URL path against known prefixes to decide which base URL to prepend:
- `/api/v1/admin/` or `/api/v1/auth/` → `NEXT_PUBLIC_GATEWAY_URL`
- `/api/v1/documents/` → `NEXT_PUBLIC_DOCUMENT_URL`
- `/api/v1/annotation-` → `NEXT_PUBLIC_ANNOTATION_URL`
- `/api/v1/training-` or `/api/v1/models` → `NEXT_PUBLIC_TRAINING_URL`
- `/api/v1/extractions` → `NEXT_PUBLIC_EXTRACTION_URL`
- Absolute URLs (starting with `http`) — passed through unchanged.

**Rationale:** Matches the existing `src/portal/src/lib/api.ts` constants from SP-01 and aligns with the decomposition's cross-cutting concern. Centralising routing here means no other spec needs to know which service handles which prefix.

**Alternatives considered:**
- Caller passes the full URL — each screen spec must import service URL constants and compose URLs; error-prone and duplicated.
- A routing map config file — adds an indirection layer with no benefit for this scale.

## Risks / Trade-offs

- [Brief login redirect flash on page reload when previously authenticated] → Accepted per user preference; can be mitigated in SP-03 with an `<AppShell>` skeleton that shows instantly before auth resolves.
- [Cookie `SameSite=Strict` prevents the refresh cookie from being sent on top-level navigation from an external link] → Not a concern for an SPA where all navigations are client-side router pushes.
- [Concurrent 401s cleared after the singleton refresh resolves — if that refresh also 401s, all pending calls redirect to /login] → Correct and intended behaviour. The redirect toast "Session expired" gives user feedback.
- [The `tenant_slug` field in the login response is `null` for `system_admin`] → `AuthUser.tenantSlug` must be `string | null`; user screens that need the slug (SP-11) must guard on role.

## Migration Plan

1. Deploy the gateway change (`src/gateway/api/v1/auth.py`) first — it is backward-compatible in one direction: the old portal (if any tab is open) still works because the JSON body `access_token` / `refresh_token` fields are still returned; only the cookie is new.
2. Deploy the portal change. The new `authFetch` now injects the Bearer token; protected routes return real data instead of 401s.
3. No database migration required. No existing user sessions are invalidated.
4. Rollback: revert `auth.py` and `auth.tsx` / `auth-fetch.ts` independently. The cookie is not relied on by any other system component.

## Open Questions

- `src/gateway/services/auth_service.py` — confirm the `login` return value includes `tenant_slug` (or `null` for `system_admin`). If not, it needs to be added to the response shape before the frontend `AuthUser` type can be finalised.
- Confirm `settings.ENVIRONMENT` is the correct field in `src/gateway/core/config.py` for the `Secure` flag conditional (vs a dedicated `COOKIE_SECURE` boolean flag).
