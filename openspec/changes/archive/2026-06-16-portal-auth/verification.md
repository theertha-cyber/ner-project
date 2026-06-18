# Verification Plan

**Change:** portal-auth
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | auth-context | Auth Context Provider | Successful login sets user and stores token in memory | Given no user is authenticated, when `login()` is called and the API returns 200, then `useAuth().user` is set, the token is accessible to authFetch, and no token string appears in localStorage/sessionStorage | Unit test: `login_sets_user_and_keeps_token_in_memory` | - [ ] |
| 2 | auth-context | Auth Context Provider | Logout clears user and calls logout endpoint | Given an authenticated user, when `logout()` is called, then POST /auth/logout is called with Bearer header, `user` becomes null, and the token ref is cleared | Unit test: `logout_clears_user_and_calls_api` | - [ ] |
| 3 | auth-context | Auth Context Provider | On-mount refresh restores session from cookie | Given a valid refresh_token httpOnly cookie exists, when AuthProvider mounts, then POST /auth/refresh is called and `user` is populated with refreshed claims | Unit test: `on_mount_refresh_restores_session` | - [ ] |
| 4 | auth-context | Auth Context Provider | On-mount refresh failure leaves user as null | Given no valid refresh_token cookie exists, when AuthProvider mounts, then POST /auth/refresh returns 401 and `user` remains null | Unit test: `on_mount_refresh_failure_leaves_user_null` | - [ ] |
| 5 | auth-context | Auth Context Provider | useAuth throws when called outside AuthProvider | Given a component that calls useAuth() without AuthProvider, when it renders, then an error is thrown with message "useAuth must be used within AuthProvider" | Unit test: `use_auth_throws_outside_provider` | - [ ] |
| 6 | auth-context | Auth Context Access Token Exposure | authFetch reads token synchronously without re-render | Given an authenticated user, when authFetch reads the token, then it uses getAccessToken() synchronously and no React re-render is triggered | Unit test: `get_access_token_is_synchronous_no_rerender` | - [ ] |
| 7 | auth-context | Auth Context Access Token Exposure | authFetch updates token after silent refresh | Given a silent refresh returns a new access_token, when setAccessToken(newToken) is called, then subsequent authFetch calls use the new token | Unit test: `set_access_token_updates_subsequent_calls` | - [ ] |
| 8 | auth-fetch | Auth Fetch Interceptor | authFetch prepends gateway URL for admin routes | Given NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000, when authFetch("/api/v1/admin/tenants") is called, then fetch is called with http://localhost:8000/api/v1/admin/tenants | Unit test: `auth_fetch_prepends_gateway_for_admin_routes` | - [ ] |
| 9 | auth-fetch | Auth Fetch Interceptor | authFetch prepends document service URL for document routes | Given NEXT_PUBLIC_DOCUMENT_URL=http://localhost:8001, when authFetch("/api/v1/documents/123") is called, then fetch is called with http://localhost:8001/api/v1/documents/123 | Unit test: `auth_fetch_prepends_document_url` | - [ ] |
| 10 | auth-fetch | Auth Fetch Interceptor | authFetch passes absolute URLs through unchanged | Given an absolute URL "https://external.example.com/api/data", when authFetch is called with it, then fetch is called with that URL unchanged | Unit test: `auth_fetch_passes_absolute_url_unchanged` | - [ ] |
| 11 | auth-fetch | Auth Fetch Interceptor | authFetch injects Bearer token on authenticated requests | Given an access token "tok-abc123", when authFetch("/api/v1/documents") is called, then the outgoing request has "Authorization: Bearer tok-abc123" | Unit test: `auth_fetch_injects_bearer_token` | - [ ] |
| 12 | auth-fetch | Auth Fetch 401 Silent Refresh | 401 triggers one silent refresh and retries | Given an expired token and POST /auth/refresh returns a new token, when authFetch gets a 401, then exactly one refresh is issued, the request is retried with the new token, and the retried response is returned | Unit test: `auth_fetch_401_triggers_refresh_and_retry` | - [ ] |
| 13 | auth-fetch | Auth Fetch 401 Silent Refresh | Concurrent 401s produce only one refresh request | Given three concurrent authFetch calls all receiving 401 simultaneously, when all detect 401, then exactly one POST /auth/refresh is issued and all three callers receive retried responses | Unit test: `concurrent_401s_single_refresh_request` | - [ ] |
| 14 | auth-fetch | Auth Fetch 401 Silent Refresh | Refresh failure redirects to login | Given an expired access token and an expired refresh cookie (refresh returns 401), when authFetch gets 401 and the refresh also fails, then the user is redirected to /login and authFetch throws | Unit test: `refresh_failure_redirects_to_login` | - [ ] |
| 15 | auth-fetch | Auth Fetch 401 Silent Refresh | Second 401 after refresh does not trigger another refresh | Given a successful refresh was just completed and the retried request also returns 401, when authFetch receives this second 401, then no further refresh is triggered and the 401 response is returned to the caller | Unit test: `second_401_after_refresh_not_retried` | - [ ] |
| 16 | login-page | Login Page Layout and Submission | Successful login redirects to dashboard | Given the login page, when valid credentials are entered and submitted, then useAuth().login() is called and the user is redirected to /dashboard | Unit test: `login_success_redirects_to_dashboard` | - [ ] |
| 17 | login-page | Login Page Layout and Submission | Failed login shows form-level error | Given the login page, when invalid credentials are submitted (API returns 401), then the API error message is displayed in the card and the user remains on /login | Unit test: `login_failure_shows_error_message` | - [ ] |
| 18 | login-page | Login Page Layout and Submission | Submit button is disabled while request is in-flight | Given the login form is submitted, when the POST /auth/login request is in-flight, then the Sign in button is disabled and a loading indicator is visible | Unit test: `login_button_disabled_during_request` | - [ ] |
| 19 | login-page | Login Page Layout and Submission | Already-authenticated user is redirected away from login | Given useAuth().user is not null, when the user navigates to /login, then they are redirected to /dashboard without seeing the login form | Unit test: `authenticated_user_redirected_from_login` | - [ ] |
| 20 | login-page | Demo Role Chips | Demo chips are visible when DEMO_MODE is enabled | Given NEXT_PUBLIC_DEMO_MODE=true, when the login page renders, then four role chips (system_admin, tenant_admin, annotator, business_user) are visible in the DOM | Unit test: `demo_chips_visible_when_demo_mode_enabled` | - [ ] |
| 21 | login-page | Demo Role Chips | Clicking a demo chip fills and submits credentials | Given NEXT_PUBLIC_DEMO_MODE=true and the login page is rendered, when the tenant_admin chip is clicked, then the email and password fields are populated with hardcoded tenant_admin credentials and the form is submitted | Unit test: `demo_chip_click_fills_and_submits` | - [ ] |
| 22 | login-page | Demo Role Chips | Demo chips are absent in production mode | Given NEXT_PUBLIC_DEMO_MODE is unset, when the login page renders, then no role chip elements are present in the DOM | Unit test: `demo_chips_absent_in_production_mode` | - [ ] |
| 23 | require-auth | RequireAuth Route Guard | Unauthenticated access redirects to login | Given useAuth().user is null, when a route wrapped in RequireAuth renders, then useRouter().replace("/login") is called and children are not rendered | Unit test: `require_auth_unauthenticated_redirects_to_login` | - [ ] |
| 24 | require-auth | RequireAuth Route Guard | Authenticated access renders children | Given useAuth().user is a valid AuthUser and no roles prop is provided, when RequireAuth renders, then children are rendered and no redirect occurs | Unit test: `require_auth_authenticated_renders_children` | - [ ] |
| 25 | require-auth | RequireAuth Route Guard | Role-restricted access with matching role renders children | Given useAuth().user.role is "system_admin" and RequireAuth has roles={["system_admin"]}, when it renders, then children are rendered | Unit test: `require_auth_matching_role_renders_children` | - [ ] |
| 26 | require-auth | RequireAuth Route Guard | Role-restricted access with non-matching role redirects to dashboard | Given useAuth().user.role is "annotator" and RequireAuth has roles={["system_admin"]}, when it renders, then useRouter().replace("/dashboard") is called and children are not rendered | Unit test: `require_auth_non_matching_role_redirects_dashboard` | - [ ] |
| 27 | user-auth | User Authentication (modified) | User logs in with valid credentials and receives cookie | Given a valid user, when POST /api/v1/auth/login is called, then response is 200 with access_token body, Set-Cookie header sets refresh_token with HttpOnly;SameSite=Strict;Path=/api/v1/auth/refresh;Max-Age=604800, and refresh_token is NOT in the response body | Integration test: `login_returns_cookie_not_body_refresh_token` | - [ ] |
| 28 | user-auth | User Authentication (modified) | User logs in with incorrect password | Given wrong credentials, when POST /api/v1/auth/login is called, then response is 401 with an invalid credentials error | Integration test: `login_wrong_password_returns_401` | - [ ] |
| 29 | user-auth | User Authentication (modified) | User accesses API with expired token | Given an expired JWT, when any protected endpoint is called with Bearer header, then response is 401 with token expired message | Integration test: `expired_token_returns_401` | - [ ] |
| 30 | user-auth | User Authentication (modified) | Token refresh via cookie succeeds and sets new cookie | Given a valid refresh_token cookie, when POST /api/v1/auth/refresh is called (no body), then response is 200 with new access_token and a new Set-Cookie for refresh_token with same attributes | Integration test: `refresh_via_cookie_returns_new_token_and_cookie` | - [ ] |
| 31 | user-auth | User Authentication (modified) | Token refresh with no cookie returns 401 | Given no refresh_token cookie, when POST /api/v1/auth/refresh is called, then response is 401 and no Set-Cookie header is present | Integration test: `refresh_without_cookie_returns_401` | - [ ] |
| 32 | user-auth | User Authentication (modified) | Logout clears the refresh token cookie | Given a valid session, when POST /api/v1/auth/logout is called with Bearer header, then response is 200 and a Set-Cookie header clears the refresh_token cookie | Integration test: `logout_clears_refresh_cookie` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Access token storage | AI may store `accessToken` in `useState` (triggers re-renders on every refresh) or persist it to `localStorage` (XSS risk), violating the in-memory-only requirement | Inspect `auth.tsx`: confirm `accessTokenRef = useRef<string \| null>(null)`. Search `auth.tsx` for `localStorage`, `sessionStorage` — must return zero hits for any access_token or refresh_token write |
| 2 | Pending refresh singleton scope | AI may implement the pending-refresh lock as a `useRef` inside `AuthProvider`, which would not be accessible from the `authFetch` module and would allow multiple simultaneous refresh calls from concurrent `authFetch` calls | Inspect `auth-fetch.ts`: confirm `pendingRefresh` is a module-level `let` variable (not inside a hook or component). Verify the concurrent-401 test (#13) passes |
| 3 | Gateway cookie attributes | AI may omit `SameSite=Strict`, `Path=/api/v1/auth/refresh`, or use the wrong `Max-Age` on the Set-Cookie call, weakening the security model | Inspect `src/gateway/api/v1/auth.py`: confirm the exact `set_cookie()` call includes `httponly=True, samesite="strict", path="/api/v1/auth/refresh", max_age=604800` |
| 4 | Refresh endpoint reads from body not cookie | AI may keep the old body-based `payload["refresh_token"]` pattern in the refresh endpoint instead of reading from `request.cookies`, defeating the httpOnly protection | Inspect `src/gateway/api/v1/auth.py` refresh handler: confirm it uses `request: Request` and reads `request.cookies.get("refresh_token")` with NO `payload` body parameter |
| 5 | Demo chips unconditional rendering | AI may render the demo chips unconditionally or use a hardcoded `process.env.NODE_ENV !== "production"` check instead of the specified `NEXT_PUBLIC_DEMO_MODE` env var | Inspect `login/page.tsx`: confirm chips are wrapped in `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` check. Run scenario #22 with DEMO_MODE unset |
| 6 | RequireAuth loading state | AI may add an `isInitialising` state to RequireAuth that blocks rendering while the on-mount refresh is in-flight, contradicting the "render immediately, redirect if not authed" design decision | Inspect `require-auth.tsx`: confirm there is no loading state, no spinner, and no conditional render gated on a loading flag. Only check: `if (!user) redirect to /login` |
| 7 | authFetch URL routing for /api/v1/models | AI may route `/api/v1/models` to the gateway (GATEWAY_URL) instead of the training service (TRAINING_URL), since model registry endpoints are served by the training service on port 8003 | Inspect `auth-fetch.ts` routing map: confirm `/api/v1/models` maps to `NEXT_PUBLIC_TRAINING_URL`. Run test #9 equivalent for a models route |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | JWT must carry `tenant_id`; no client-side tenant mixing | Confirm `AuthUser.tenantId` is decoded from JWT claims (not hard-coded or guessed). Confirm `authFetch` does not inject any tenant header client-side — tenant context comes from the token only |
| ADR-004 | OpenSpec spec-driven governance | All capabilities must have specs before implementation; artifact gates (proposal → design → specs → verification → tasks) must be respected | Confirm all 5 spec files exist before any implementation task is run. Confirm `openspec validate portal-auth --type change --strict` exits clean |
| ADR-005 | OpenCode agent permissions and boundaries | Agent-generated code must not introduce new ambient credentials or bypass auth controls | Confirm no hardcoded credential strings (beyond demo chip placeholders) appear in the portal source. Confirm the demo credentials are only read from a config object, not scattered inline |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Row 1: Test output showing login succeeds, user is set, and localStorage is free of token strings
- [ ] Row 2: Test output showing logout clears user and calls POST /auth/logout
- [ ] Row 3: Test output showing on-mount refresh populates user from a mocked cookie response
- [ ] Row 4: Test output showing on-mount refresh failure leaves user as null
- [ ] Row 5: Test output showing useAuth() throws outside AuthProvider
- [ ] Row 6: Test output showing getAccessToken() reads synchronously without re-render
- [ ] Row 7: Test output showing setAccessToken updates subsequent authFetch calls
- [ ] Row 8: Test output showing authFetch("/api/v1/admin/tenants") calls fetch with full gateway URL
- [ ] Row 9: Test output showing authFetch("/api/v1/documents/123") calls fetch with full document service URL
- [ ] Row 10: Test output showing authFetch with absolute URL passes through unchanged
- [ ] Row 11: Test output showing Authorization: Bearer header is injected
- [ ] Row 12: Test output showing 401 triggers exactly one refresh and retries the original call
- [ ] Row 13: Test output showing three concurrent 401s result in one refresh request
- [ ] Row 14: Test output showing refresh failure redirects to /login and throws
- [ ] Row 15: Test output showing second 401 after refresh returns the 401 to caller (no loop)
- [ ] Row 16: Test output showing login success renders nothing and triggers redirect to /dashboard
- [ ] Row 17: Test output showing API error message is displayed in the card on failed login
- [ ] Row 18: Test output showing Sign in button has disabled attribute during in-flight request
- [ ] Row 19: Test output showing authenticated user on /login is redirected to /dashboard
- [ ] Row 20: Test output showing four demo chip elements are rendered when NEXT_PUBLIC_DEMO_MODE=true
- [ ] Row 21: Test output showing clicking a chip populates fields and submits the form
- [ ] Row 22: Test output showing no chip elements in DOM when NEXT_PUBLIC_DEMO_MODE is unset
- [ ] Row 23: Test output showing RequireAuth calls replace("/login") and renders null when user is null
- [ ] Row 24: Test output showing RequireAuth renders children when user is set and no roles prop
- [ ] Row 25: Test output showing RequireAuth renders children when user role matches
- [ ] Row 26: Test output showing RequireAuth calls replace("/dashboard") when role does not match
- [ ] Row 27: Gateway integration test or manual trace showing Set-Cookie on login with correct attributes
- [ ] Row 28: Gateway integration test showing 401 on wrong password
- [ ] Row 29: Gateway integration test showing 401 on expired token
- [ ] Row 30: Gateway integration test showing cookie refresh returns new token and rotates cookie
- [ ] Row 31: Gateway integration test showing 401 when no refresh cookie is present
- [ ] Row 32: Gateway integration test showing Set-Cookie clears the cookie on logout

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (token storage): Grep `src/portal/src/lib/auth.tsx` for `localStorage` — zero hits for token writes confirmed
- [ ] Risk 2 (singleton scope): `pendingRefresh` is module-level in `auth-fetch.ts` confirmed; concurrent-401 test passes
- [ ] Risk 3 (cookie attributes): `set_cookie()` call in `auth.py` includes all required attributes confirmed
- [ ] Risk 4 (cookie-only refresh): refresh endpoint in `auth.py` reads from `request.cookies`, no body param confirmed
- [ ] Risk 5 (demo chips guard): `NEXT_PUBLIC_DEMO_MODE` check is present; scenario #22 passes with unset env var
- [ ] Risk 6 (no loading state): RequireAuth has no loading/initialising state; renders immediately with redirect
- [ ] Risk 7 (models URL routing): authFetch routes `/api/v1/models` to TRAINING_URL confirmed

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** portal-auth
**Proposal:** `openspec/changes/portal-auth/proposal.md`
**Spec files reviewed:**
  - specs/auth-context/spec.md
  - specs/auth-fetch/spec.md
  - specs/login-page/spec.md
  - specs/require-auth/spec.md
  - specs/user-auth/spec.md (delta)

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
