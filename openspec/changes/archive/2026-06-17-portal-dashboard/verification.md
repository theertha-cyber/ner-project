# Verification Plan

**Change:** portal-dashboard
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-dashboard | Dashboard Data Shape | system_admin data shape | `GET /api/v1/dashboard/summary` as system_admin returns kicker "Platform control plane", 4 stats, pTitle "Approval queue", side panel "Platform health" | Browser check / API call: response matches expected shape | - [ ] |
| 2 | portal-dashboard | Dashboard Data Shape | tenant_admin data shape | Response contains 4 pipeline stats, pTitle "Pipeline activity", side panel "Active model" | Browser check / API call | - [ ] |
| 3 | portal-dashboard | Dashboard Data Shape | annotator data shape | Response contains 4 annotation stats, pTitle "My tasks", side panel "Dataset readiness" | Browser check / API call | - [ ] |
| 4 | portal-dashboard | Dashboard Data Shape | business_user data shape | Response contains 4 extraction stats, pTitle "Recent extractions", side panel "Active model" | Browser check / API call | - [ ] |
| 5 | portal-dashboard | Dashboard Data Shape | partial service failure degrades gracefully | When a service is unavailable, affected stat cards show "—"; other cards show real values; no full-page error shown | Browser check with service mocked offline | - [ ] |
| 6 | portal-dashboard | Dashboard Summary Endpoint | system_admin summary returns tenant count | `GET /api/v1/dashboard/summary` as system_admin returns real tenant count in `stats[0].value`, `sources.tenants: true` | API test / curl | - [ ] |
| 7 | portal-dashboard | Dashboard Summary Endpoint | unauthenticated request rejected | `GET /api/v1/dashboard/summary` without JWT returns 401 | API test / curl | - [ ] |
| 8 | portal-dashboard | Hero Section | editorial layout renders large hero | Dashboard renders kicker, title, line in large typographic layout; SegmentControl shows "Editorial" as active | Browser screenshot | - [ ] |
| 9 | portal-dashboard | Hero Section | command layout renders compact hero | After switching to "Command", hero collapses to single line; description hidden | Browser screenshot | - [ ] |
| 10 | portal-dashboard | Hero Section | layout toggle persists across navigation | Switching to "Command", navigating away and back retains "Command" layout | Browser check: localStorage key "portal-layout" = "command" | - [ ] |
| 11 | portal-dashboard | Hero Section | layout toggle does not re-fetch data | Toggling layout triggers no new network request | Browser DevTools Network tab: no new fetch on toggle | - [ ] |
| 12 | portal-dashboard | Stat Card Strip | stat cards render with live values | 4 cards visible with correct value, unit, label, sub, delta for the user's role | Browser check post-load | - [ ] |
| 13 | portal-dashboard | Stat Card Strip | stat cards render skeleton while loading | During fetch, 4 skeleton placeholders visible (no spinner, no blank boxes) | Browser check on slow network or stub delay | - [ ] |
| 14 | portal-dashboard | Stat Card Strip | warn direction renders amber indicator | Stat with `dir: "warn"` (e.g., Pending approvals) shows amber delta indicator | Browser screenshot | - [ ] |
| 15 | portal-dashboard | Activity Panel | activity row navigates on click | Clicking a system_admin row with `go: "training"` navigates to `/training-jobs` | Browser check: URL changes correctly | - [ ] |
| 16 | portal-dashboard | Activity Panel | status tag colours match mockup | `tk: "pending_approval"` renders amber/warn tag; `tk: "completed"` renders green/good tag | Browser screenshot | - [ ] |
| 17 | portal-dashboard | Secondary Metrics Panel | progress bar fills to correct percentage | `bar: 62` renders bar filled to 62% width | Browser check / computed style | - [ ] |
| 18 | portal-dashboard | Secondary Metrics Panel | sideRows mini bars render correct colours | `sideRows[0].c` colour string is applied as bar background colour | Browser screenshot | - [ ] |
| 19 | portal-dashboard | Data Freshness | data refetches every 30 seconds | Background refetch fires after 30s without UI flash | Browser DevTools: network tab shows fetch at t+30s | - [ ] |
| 20 | portal-dashboard | Data Freshness | QueryClientProvider wraps the app | Any component calling `useQueryClient()` receives the shared instance without error | TypeScript check + browser console (no errors) | - [ ] |
| 21 | app-shell | Authenticated Route Group Layout | system_admin lands on dashboard (not redirected to /admin) | Navigating to `/dashboard` as system_admin renders dashboard, not a redirect to `/admin` | Browser check: URL stays `/dashboard`, hero shows "Platform control plane" | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | dashData shape field names | AI may invent field names not in the mockup (e.g., `subtitle` instead of `line`, `rows` instead of `pRows`) | Compare generated `DashboardData` TypeScript type against the mockup's `dashData` function field names exactly |
| 2 | Activity row `go` → href mapping | AI may map `go: "training"` to `/training` instead of `/training-jobs`, or miss a mapping entirely | Read generated `goToHref` mapping and compare to `navFor` hrefs in `nav-config.ts` |
| 3 | TanStack Query v5 API | AI may use v4 API (e.g., `keepPreviousData: true` instead of `placeholderData: keepPreviousData`) | Read generated hook and verify v5 API usage: `placeholderData`, not `keepPreviousData: true` |
| 4 | Gateway endpoint auth | AI may omit the `require_tenant_role` dependency on the summary endpoint, making it public | Read `dashboard.py` and verify `Depends(require_tenant_role)` is present |
| 5 | system_admin redirect removal | AI may leave the old redirect in `DashboardRouter` or add a new one | Read `(auth)/dashboard/page.tsx` — must not contain `router.replace("/admin")` |
| 6 | localStorage SSR hazard | AI may read `localStorage` at module level or in a Server Component, causing hydration errors | Read layout preference code — must be inside `useEffect` or guarded by `typeof window !== "undefined"` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant isolation via separate DB schemas | Dashboard summary endpoint must only return data scoped to the caller's tenant_id from the JWT; system_admin receives cross-tenant aggregates only via the existing admin DB path | Read `dashboard.py` — non-admin paths must use `request.state.token_tenant_id`, not a user-supplied tenant param |
| ADR-004 | OpenSpec spec-driven governance | Dashboard component and gateway endpoint implemented only under this spec | Review file diff — no new files outside the described scope |
| ADR-005 | Agent permission boundaries | No ambient developer credentials or bypasses in production | Verify no hardcoded test data or debug flags are left in production code paths |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1–4: Browser screenshots or API responses showing correct `dashData` shape for each role
- [ ] Scenario 5: Test or browser check demonstrating graceful degradation on service failure
- [ ] Scenario 6–7: `curl` or API test output for `/api/v1/dashboard/summary` (authenticated and unauthenticated)
- [ ] Scenario 8–9: Browser screenshots of Editorial and Command layouts
- [ ] Scenario 10: Browser DevTools showing `portal-layout` in localStorage after toggle
- [ ] Scenario 11: Network tab screenshot showing no fetch on layout toggle
- [ ] Scenario 12–14: Browser screenshots of stat card strip in loaded and loading states
- [ ] Scenario 15–16: Browser check of activity row click navigation and tag colours
- [ ] Scenario 17–18: Browser screenshots of secondary metrics panel
- [ ] Scenario 19: Network tab showing background refetch at t+30s
- [ ] Scenario 20: Console showing no `useQueryClient` error
- [ ] Scenario 21: Browser check confirming system_admin stays on `/dashboard`

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented patterns introduced
- [ ] No AI-invented fields or endpoints present

### Edge Case Evidence

- [ ] Risk 1 mitigation: `DashboardData` type field names verified against mockup
- [ ] Risk 2 mitigation: `go` → href mapping verified against `nav-config.ts`
- [ ] Risk 3 mitigation: TanStack Query v5 API usage confirmed (no v4 patterns)
- [ ] Risk 4 mitigation: Gateway endpoint requires authentication
- [ ] Risk 5 mitigation: No `router.replace("/admin")` in dashboard page
- [ ] Risk 6 mitigation: localStorage read is inside `useEffect`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | — | — | — | — | — |

*(To be populated during implementation review.)*

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.**

**Change slug:** portal-dashboard
**Proposal:** `openspec/changes/portal-dashboard/proposal.md`
**Spec files reviewed:**
- specs/portal-dashboard/spec.md
- specs/app-shell/spec.md

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
