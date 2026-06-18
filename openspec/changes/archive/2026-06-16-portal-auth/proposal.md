## Why

The portal has no authentication layer: the SP-01 `authFetch` stub is a pass-through with no token injection, and the prototype `auth.tsx` stores tokens in `localStorage` (a security violation). Without a real auth flow the rest of the portal UI cannot ship.

## What Changes

- **BREAKING** `src/portal/src/lib/auth.tsx` — completely replaced with a spec-compliant `AuthProvider` that holds the access token in React memory only (never `localStorage`).
- **BREAKING** `src/portal/src/lib/auth-fetch.ts` — replaced with a real interceptor: injects `Authorization: Bearer`, detects 401, triggers one silent refresh via the cookie, retries, then redirects to `/login` if refresh fails.
- New `src/portal/src/app/login/page.tsx` — glassmorphism login screen matching the mockup; demo role chips gated by `NEXT_PUBLIC_DEMO_MODE=true`.
- New `src/portal/src/components/require-auth.tsx` — `<RequireAuth roles?>` guard wrapping authenticated routes.
- **Backend** `src/gateway/api/v1/auth.py` — `login` and `refresh` endpoints add `Set-Cookie: refresh_token=…; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=604800` on their `JSONResponse`. Logout endpoint clears the cookie.
- New `NEXT_PUBLIC_DEMO_MODE` env var in `.env.local.example` to gate the demo chips.

## Capabilities

### New Capabilities

- `auth-context`: React `AuthProvider` / `useAuth()` hook — access token stored in `useRef` (not state, not `localStorage`); `AuthUser` interface with `userId`, `tenantId`, `role`, `email`, `tenantSlug`; on mount, calls `POST /auth/refresh` via cookie to restore session; exposes `login()`, `logout()`, `user`, `accessToken`.
- `auth-fetch`: `authFetch(url, init)` interceptor — prepends service base URL by route prefix, injects `Authorization: Bearer`, detects 401, fires one concurrent-safe refresh (pending-promise singleton via `useRef`), retries original request; on second 401 redirects to `/login`.
- `login-page`: Login screen matching the mockup glassmorphism card: email + password fields, "Sign in →" CTA, form-level error display, redirect to `/dashboard` on success. Demo role chips (`system_admin / tenant_admin / annotator / business_user`) rendered only when `NEXT_PUBLIC_DEMO_MODE=true`.
- `require-auth`: `<RequireAuth roles?>` route guard — reads `user` from `useAuth()`; renders children when authenticated (and role matches if `roles` supplied); redirects to `/login` via `useRouter().replace()` otherwise. Renders immediately without a loading screen (redirect fires on first render if not authed).

### Modified Capabilities

- `user-auth`: Add `Set-Cookie` requirement — the `login` and `refresh` endpoints SHALL set an `httpOnly; Secure; SameSite=Strict` cookie for the refresh token on every successful response; the `logout` endpoint SHALL clear this cookie. This is a requirement addition to the existing backend spec.

## Impact

- `src/gateway/api/v1/auth.py` — 3 endpoint handlers modified (`login`, `refresh`, `logout`).
- `src/portal/src/lib/auth.tsx` — full rewrite (prototype code removed).
- `src/portal/src/lib/auth-fetch.ts` — full rewrite (stub replaced).
- `src/portal/src/app/login/page.tsx` — replaces placeholder login page.
- `src/portal/src/app/layout.tsx` — no change to file but `<RequireAuth>` is now expected to be used in the authenticated route group layout.
- `src/portal/.env.local.example` — one new variable (`NEXT_PUBLIC_DEMO_MODE`).
- All downstream specs (SP-03 through SP-11) depend on `authFetch` from this change.

## Open Questions

- The SP-02 decomposition note says `Set-Cookie` should use `Secure` in production but dev can omit it. The gateway will add `Secure` only when `ENVIRONMENT != "development"` — this needs verification against `src/gateway/core/config.py` settings.
- The login response currently includes `tenant_slug: null` for `system_admin`. The `AuthContext` should handle this gracefully (store `null` and skip slug-dependent user API calls).
