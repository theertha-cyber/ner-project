## 1. Gateway Backend — Set-Cookie on Auth Endpoints

- [x] 1.1 Modify `src/gateway/api/v1/auth.py` `login` handler: wrap return value in `JSONResponse`, call `response.set_cookie("refresh_token", refresh_token, httponly=True, samesite="strict", path="/api/v1/auth/refresh", max_age=604800, secure=settings.ENVIRONMENT=="production")`, and remove `refresh_token` from the JSON body *(verification rows 27–28)*
- [x] 1.2 Modify `refresh` handler: add `request: Request` parameter, read `refresh_token = request.cookies.get("refresh_token")`, return 401 if absent; remove `payload: dict` body parameter; on success, set the same `Set-Cookie` to rotate the token *(verification rows 30–31)*
- [x] 1.3 Modify `logout` handler: call `response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")` before returning success *(verification row 32)*
- [x] 1.4 Confirm `settings.ENVIRONMENT` exists in `src/gateway/core/config.py`; if the field is named differently (e.g. `APP_ENV`), use the correct field name for the `secure` conditional *(verification row 27, hallucination risk 3)*
  — **Note:** Settings at `src/shared/config.py` (not gateway/core). Added `environment: str = "development"` field; used `settings.environment == "production"` in auth.py.

## 2. Auth Context Rewrite

- [x] 2.1 Define the `AuthUser` interface in `src/portal/src/lib/auth.tsx`: `{ userId, tenantId, role: "system_admin"|"tenant_admin"|"annotator"|"business_user", email, tenantSlug: string | null }` *(verification row 1)*
- [x] 2.2 Replace `AuthContextType` with `{ user: AuthUser | null; getAccessToken: () => string | null; setAccessToken: (t: string) => void; login: (email, password) => Promise<void>; logout: () => Promise<void> }` *(verification rows 6–7)*
- [x] 2.3 Rewrite `AuthProvider`: change access token storage from `useState` to `accessTokenRef = useRef<string | null>(null)`; keep `user` in `useState`; expose `getAccessToken` and `setAccessToken` via the ref *(verification rows 1, 6–7, hallucination risk 1)*
- [x] 2.4 Implement `login(email, password)`: call `POST /api/v1/auth/login` via raw `fetch` (not authFetch — avoids circular dependency); parse response; set `accessTokenRef.current = data.access_token`; set `user` via `setUser(decodeUser(data))` *(verification row 1)*
- [x] 2.5 Implement `logout()`: call `POST /api/v1/auth/logout` with `Authorization: Bearer ${accessTokenRef.current}`; clear `accessTokenRef.current = null`; call `setUser(null)` *(verification row 2)*
- [x] 2.6 Implement on-mount silent refresh in `useEffect`: call `POST /api/v1/auth/refresh` (no body — cookie is sent automatically); on success populate token ref and user; on failure leave user as null *(verification rows 3–4)*
  — **Note:** `auth_service.refresh()` was updated to also return user data via DB lookup so the client can populate `AuthUser` from the refresh response.
- [x] 2.7 Rewrite `useAuth()` to throw `"useAuth must be used within AuthProvider"` when context is undefined *(verification row 5)*
- [x] 2.8 Remove all `localStorage`/`sessionStorage` writes for access and refresh tokens from `auth.tsx` *(hallucination risk 1)*

## 3. Auth Fetch Interceptor Rewrite

- [x] 3.1 Rewrite `src/portal/src/lib/auth-fetch.ts`: add module-level `let pendingRefresh: Promise<string> | null = null`; import env-var URL constants from `@/lib/api` *(hallucination risk 2)*
- [x] 3.2 Implement service URL routing: check `url` for path prefixes in order (`/api/v1/admin`, `/api/v1/auth`, `/api/v1/tenants` → `GATEWAY_URL`; `/api/v1/document` → `DOCUMENT_URL`; `/api/v1/annotation` → `ANNOTATION_URL`; `/api/v1/training`, `/api/v1/models` → `TRAINING_URL`; `/api/v1/extraction` → `EXTRACTION_URL`; absolute URLs pass through unchanged) *(verification rows 8–10, hallucination risk 7)*
- [x] 3.3 Implement Bearer token injection: before every `fetch` call, read `getAccessToken()` from the auth context and add `Authorization: Bearer <token>` to headers if token is present *(verification row 11)*
- [x] 3.4 Implement 401 silent refresh: on 401 response, if `pendingRefresh` is null create a refresh promise (calls `POST /api/v1/auth/refresh`, calls `setAccessToken(newToken)`, clears `pendingRefresh` after resolve/reject); await `pendingRefresh`; retry the original request with the new token *(verification rows 12–13, hallucination risk 2)*
- [x] 3.5 Implement redirect on double 401: if the retried request also returns 401, call `router.replace("/login")` and throw *(verification row 14)*
- [x] 3.6 Ensure a second 401 on the retried request does not trigger another refresh call (the singleton is already cleared by this point) *(verification row 15)*
- [x] 3.7 Accept `getAccessToken`, `setAccessToken`, and `router` as constructor-time arguments (or module-level setters) to avoid circular imports and allow test injection

## 4. Login Page

- [x] 4.1 Replace `src/portal/src/app/login/page.tsx` with a glassmorphism card layout matching the mockup: centred card with `backdrop-blur` / `bg-surface` / `shadow-overlay` classes, logo or title at top *(visual reference: `docs/NER Platform.dc.html`)*
- [x] 4.2 Add controlled email input (`type="email"`, required) and password input (`type="password"`, required) with label text *(verification row 16)*
- [x] 4.3 Add "Sign in →" button: disable and show loading indicator (spinner or text swap) while `isPending` state is true *(verification row 18)*
- [x] 4.4 Display form-level error message below the form fields when login fails (read from the `error.message` thrown by `useAuth().login()`) *(verification row 17)*
- [x] 4.5 On successful login, call `router.replace("/dashboard")` *(verification row 16)*
- [x] 4.6 On mount (or via `useEffect`), if `useAuth().user !== null`, call `router.replace("/dashboard")` immediately *(verification row 19)*
- [x] 4.7 Render the four demo role chips (`system_admin`, `tenant_admin`, `annotator`, `business_user`) conditionally: `process.env.NEXT_PUBLIC_DEMO_MODE === "true"`; clicking a chip populates form fields with hardcoded dev credentials and programmatically submits *(verification rows 20–22, hallucination risk 5)*
- [x] 4.8 Add `NEXT_PUBLIC_DEMO_MODE=false` to `src/portal/.env.local.example` *(verification row 20)*

## 5. RequireAuth Guard

- [x] 5.1 Create `src/portal/src/components/require-auth.tsx` accepting props `{ roles?: AuthUser["role"][]; children: ReactNode }` *(verification rows 23–26)*
- [x] 5.2 Implement unauthenticated redirect: if `user === null`, call `router.replace("/login")` and return `null` — no loading state, no spinner *(verification row 23, hallucination risk 6)*
- [x] 5.3 Implement role check: if `roles` is supplied and `user.role` is not in the array, call `router.replace("/dashboard")` and return `null` *(verification rows 25–26)*
- [x] 5.4 Render `children` when authenticated (and role matches if supplied) *(verification row 24)*

## 6. Unit Tests

- [x] 6.1 Write `src/portal/src/lib/auth.test.tsx` covering rows 1–7: login sets user (no localStorage writes), logout calls API and clears user, on-mount refresh success, on-mount refresh failure, useAuth throws outside provider, getAccessToken is synchronous, setAccessToken updates subsequent reads
- [x] 6.2 Write `src/portal/src/lib/auth-fetch.test.ts` covering rows 8–11: URL routing for each service prefix, absolute URL pass-through, Bearer token injection
- [x] 6.3 Extend `src/portal/src/lib/auth-fetch.test.ts` covering rows 12–15: 401 triggers one refresh and retry, three concurrent 401s produce one refresh, refresh failure redirects, second 401 on retry returns to caller
- [x] 6.4 Write `src/portal/src/app/login/login.test.tsx` covering rows 16–22: success redirect, failure error display, button disabled during request, authenticated redirect, demo chips visible, chip click fills and submits, chips absent in production
- [x] 6.5 Write `src/portal/src/components/require-auth.test.tsx` covering rows 23–26: unauthenticated redirect, authenticated render, role match render, role mismatch dashboard redirect
- [ ] 6.6 Verify gateway auth scenarios (rows 27–32) via Python integration tests in `src/gateway/tests/` or manual API traces; document evidence for each row in verification.md § Evidence Log

## 7. Build and Type Verification

- [x] 7.1 Run `npm run typecheck --workspace=src/portal` and confirm it exits 0 — `AuthUser`, `authFetch` parameter types, and `RequireAuth` props all resolve correctly
- [x] 7.2 Run `npm run lint --workspace=src/portal` and confirm no errors
- [x] 7.3 Run `npx prettier --check "src/**/*.{ts,tsx,js,jsx}"` from `src/portal/` and confirm no formatting issues
- [x] 7.4 Run `npm run test --workspace=src/portal` and confirm all tests pass (rows 1–26 covered)
- [x] 7.5 Run `npm run build --workspace=src/portal` and confirm it exits 0

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (`npm test --workspace=src/portal` exits 0 with all 32 scenarios covered)
- [ ] 8.2 Collect functional evidence (test output / log / API trace) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register (token storage grep, singleton scope inspection, cookie attributes, refresh-from-cookie check, demo chips guard, no loading state in RequireAuth, models URL routing)
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (ADR-001 tenant isolation, ADR-004 artifact gates, ADR-005 no ambient credentials)
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 8.6 Run `openspec validate portal-auth --type change --strict` and confirm it exits clean before archive
