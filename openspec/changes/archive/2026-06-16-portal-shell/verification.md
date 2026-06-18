# Verification Plan

**Change:** portal-shell
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | nav-config | Role Navigation Matrix | system_admin nav | Given role `system_admin`, `navFor("system_admin")` returns exactly 6 items in order: Dashboard, Tenants (badge 6), Training Queue (badge 2), Model Registry, Audit Log, Platform Settings | Unit test: `navFor("system_admin")` returns array of length 6 with correct labels and badges | - [ ] |
| 2 | nav-config | Role Navigation Matrix | tenant_admin nav | Given role `tenant_admin`, `navFor("tenant_admin")` returns exactly 8 items in order: Dashboard, Documents, Annotation, Entity Types, Training Jobs (badge 1), Model Registry, Users, Settings | Unit test: `navFor("tenant_admin")` returns array of length 8 with correct labels | - [ ] |
| 3 | nav-config | Role Navigation Matrix | annotator nav | Given role `annotator`, `navFor("annotator")` returns exactly 4 items: My Work, Annotation (badge 4), Documents, Settings | Unit test: `navFor("annotator")` returns array of length 4 | - [ ] |
| 4 | nav-config | Role Navigation Matrix | business_user nav | Given role `business_user`, `navFor("business_user")` returns exactly 5 items: Overview, Documents, Extractions, Models, Settings | Unit test: `navFor("business_user")` returns array of length 5 | - [ ] |
| 5 | nav-config | Screen Title Map | known screen lookup | Given the `SCREEN_TITLES` map is imported, accessing key `"tenants"` returns `["Tenants", "/admin/tenants"]` | Unit test: `SCREEN_TITLES["tenants"]` equals `["Tenants", "/admin/tenants"]` | - [ ] |
| 6 | nav-config | Screen Title Map | unknown screen fallback | Given a pathname that matches no `SCREEN_TITLES` key, the topbar resolver returns `["Dashboard", "/dashboard"]` | Unit test or component test: unresolvable pathname produces fallback title "Dashboard" | - [ ] |
| 7 | app-shell | Sidebar Layout | sidebar renders correct nav for role | Given authenticated user has role `annotator`, AppShell renders sidebar with exactly 4 nav items (My Work, Annotation, Documents, Settings) and no Tenants or Training Queue items | Component test / browser check: sidebar nav list has 4 items for annotator | - [ ] |
| 8 | app-shell | Sidebar Layout | active nav item is highlighted | Given pathname `/admin/tenants/new` and role `system_admin`, the "Tenants" nav item has the active highlight style and no other item does | Component test: active class/style present on Tenants item only when `startsWith("/admin/tenants")` is true | - [ ] |
| 9 | app-shell | Sidebar Layout | badge renders when present | Given "Annotation" nav item has `badge: 4`, sidebar renders a badge chip displaying "4" next to the Annotation label | Visual check / component test: badge chip with text "4" is rendered for annotation item | - [ ] |
| 10 | app-shell | Sidebar Layout | tenant pill shows correct values | Given `AuthUser.tenantSlug = "acme"`, the sidebar tenant pill displays the first-letter initial, the tenant name, and the slug in JetBrains Mono | Component test / browser check: all three values present in pill with correct font | - [ ] |
| 11 | app-shell | Sidebar Layout | logout clears session and redirects | Given an authenticated user, clicking the logout button (⎋) calls `useAuth().logout()` then navigates to `/login` | Component test: logout click triggers `logout()` mock and `router.push("/login")` | - [ ] |
| 12 | app-shell | Topbar Layout | screen title matches pathname | Given pathname `/admin/tenants`, topbar renders title "Tenants" and path "/admin/tenants" | Component test: topbar title text is "Tenants" and path text is "/admin/tenants" | - [ ] |
| 13 | app-shell | Topbar Layout | role-switcher hidden in production mode | Given `NEXT_PUBLIC_DEMO_MODE` is not `"true"`, no SA/TA/AN/BU chips are visible in the topbar | Component test: role-switcher chips absent when env var unset | - [ ] |
| 14 | app-shell | Topbar Layout | role-switcher visible in demo mode | Given `NEXT_PUBLIC_DEMO_MODE === "true"`, four chips (SA, TA, AN, BU) are visible in the topbar | Component test: all four chips render when `vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true")` | - [ ] |
| 15 | app-shell | Topbar Layout | dark mode toggle switches theme | Given light mode is active, clicking the dark mode toggle calls `useDarkMode().toggle()` and adds the `dark` class to `document.documentElement` | Component test: toggle click triggers `toggle()` mock; `document.documentElement.classList` contains `"dark"` | - [ ] |
| 16 | app-shell | Topbar Layout | search placeholder is non-interactive | Given the topbar is rendered, clicking the search area opens no dialog, modal, or command palette | Browser check / component test: click handler absent or no-op; no dialog element mounts | - [ ] |
| 17 | app-shell | Placeholder Screens | placeholder renders screen name | Given the user navigates to `/extractions`, the page displays "Extractions" and a "Coming soon" indicator, with sidebar and topbar still visible | Browser check: `/extractions` renders PlaceholderScreen with correct title and shell chrome | - [ ] |
| 18 | app-shell | Placeholder Screens | placeholder does not crash on unknown role | Given any authenticated user navigates to a placeholder route, no error boundary is triggered | Browser check / component test: placeholder renders without thrown error for any role | - [ ] |
| 19 | auth-layout | Authenticated Route Group Layout | unauthenticated access redirects to login | Given no valid session, navigating directly to `/admin/tenants` redirects to `/login` and renders no sidebar or topbar | Integration test: unauthenticated request to `/admin/tenants` resolves at `/login` with no shell chrome | - [ ] |
| 20 | auth-layout | Authenticated Route Group Layout | authenticated access renders shell | Given an authenticated user, navigating to `/dashboard` renders sidebar and topbar around page content, with URL remaining `/dashboard` (no `(auth)` prefix) | Browser check: URL bar shows `/dashboard`, sidebar visible, no `(auth)` in URL | - [ ] |
| 21 | auth-layout | Authenticated Route Group Layout | existing admin URLs unchanged | Given an authenticated `system_admin`, navigating to `/admin/tenants` renders the Tenants page within the shell with no 404 | Browser check: `/admin/tenants` returns 200 with shell chrome after file migration | - [ ] |
| 22 | auth-layout | Admin Sub-Layout Role Guard | non-admin role blocked from /admin/* | Given role `tenant_admin`, navigating to `/admin/tenants` redirects to `/dashboard` with no admin content rendered | Integration test: `tenant_admin` session redirected from `/admin/tenants` to `/dashboard` | - [ ] |
| 23 | auth-layout | Admin Sub-Layout Role Guard | system_admin accesses admin route | Given role `system_admin`, navigating to `/admin/tenants` renders the Tenants page without redirect | Browser check / integration test: `system_admin` session loads `/admin/tenants` successfully | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | navFor badge counts | AI may invent badge numbers not specified in spec (e.g., assign badge to Model Registry, or use wrong count for Tenants) | Compare generated `navFor` return values against the role→nav table in `specs/nav-config/spec.md` exactly — any badge count not listed in the spec table is suspect |
| 2 | Route group URL transparency | AI may generate layout files that include `(auth)` in the emitted URL, breaking the route group contract | Navigate to `/dashboard` and `/admin/tenants` in browser after migration — URL bar must show no `(auth)` segment |
| 3 | NEXT_PUBLIC_DEMO_MODE evaluation timing | AI may hoist the env var check to module level (`const isDemoMode = process.env…`) which breaks `vi.stubEnv` in tests | Read the generated topbar component — `process.env.NEXT_PUBLIC_DEMO_MODE` must be evaluated inline inside the render function, not hoisted |
| 4 | RequireAuth `roles` prop usage | AI may pass `roles` prop to `RequireAuth` with the wrong type or invent a `role` (singular) prop that doesn't exist | Read `src/portal/src/lib/auth.tsx` and verify `RequireAuth` signature — the generated `(auth)/admin/layout.tsx` must pass `roles={["system_admin"]}` matching the actual prop name |
| 5 | Placeholder screen routes | AI may omit some of the 9 required placeholder routes or use wrong paths (e.g., `/training-jobs` vs `/jobs`) | Count generated placeholder pages: annotation, training-jobs, models, documents, entity-types, users, extractions, audit, settings — all 9 must exist |
| 6 | Active nav highlight logic | AI may use strict equality (`pathname === item.href`) instead of prefix matching (`pathname.startsWith(item.href)`), causing nested routes like `/admin/tenants/new` to have no active item | Verify generated sidebar code uses `usePathname().startsWith(item.href)` — check by navigating to `/admin/tenants/new` and confirming Tenants item is highlighted |
| 7 | Tenant pill navigation | AI may add a click handler that opens a modal or navigates, which the spec explicitly forbids (display-only, hover border highlight only) | Read generated tenant pill component — must have no `onClick` that navigates or opens a modal; only a hover-state CSS style change is permitted |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant isolation via separate DB schemas | Sidebar must display `tenantSlug` / `tenantName` from JWT (`AuthUser` context) — never cross-tenant data or hardcoded tenant values | Read generated sidebar component — tenant pill must read from `useAuth().user.tenantSlug` / `tenantName`, never from a static import or a separate API call |
| ADR-004 | OpenSpec spec-driven governance | Shell layout must be implemented only under this change's reviewed artifacts; no ambient code added outside the spec scope | Review file diff — any new file or function not described in proposal.md, design.md, or the three spec files is a violation |
| ADR-005 | Agent permission boundaries | Role-switcher chips (SA/TA/AN/BU) must be gated behind `NEXT_PUBLIC_DEMO_MODE === "true"` so they cannot appear in production builds | Read generated topbar; confirm role-switcher is wrapped in a conditional on `process.env.NEXT_PUBLIC_DEMO_MODE === "true"`. Confirm `.env.local` or `.env.production` does not set this flag to true |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1–4: Unit test output showing `navFor` returns correct item arrays for all four roles
- [ ] Scenario 5–6: Unit test output showing `SCREEN_TITLES` lookup and fallback behaviour
- [ ] Scenario 7: Browser screenshot or component test output showing annotator sidebar with exactly 4 nav items
- [ ] Scenario 8: Browser screenshot or component test showing active highlight on Tenants item when at `/admin/tenants/new`
- [ ] Scenario 9: Screenshot or test output showing badge chip "4" on Annotation item
- [ ] Scenario 10: Browser screenshot showing tenant pill with initials, name, and slug in JetBrains Mono
- [ ] Scenario 11: Component test output showing logout triggers `logout()` and navigates to `/login`
- [ ] Scenario 12: Browser screenshot or component test showing topbar title "Tenants" and path "/admin/tenants"
- [ ] Scenario 13: Test output showing no role-switcher chips when `NEXT_PUBLIC_DEMO_MODE` is unset
- [ ] Scenario 14: Test output showing four chips visible when `NEXT_PUBLIC_DEMO_MODE === "true"`
- [ ] Scenario 15: Test output showing `toggle()` called and `document.documentElement` gains `dark` class
- [ ] Scenario 16: Test/browser evidence that clicking search area opens no dialog
- [ ] Scenario 17: Browser screenshot of `/extractions` showing "Extractions" + "Coming soon" with shell chrome
- [ ] Scenario 18: Browser check or test confirming no error boundary triggered on any placeholder route
- [ ] Scenario 19: Test or browser trace showing unauthenticated request to `/admin/tenants` lands at `/login`
- [ ] Scenario 20: Browser screenshot of `/dashboard` with sidebar + topbar visible and correct URL
- [ ] Scenario 21: Browser check that `/admin/tenants` loads correctly after file migration (no 404)
- [ ] Scenario 22: Test or browser trace showing `tenant_admin` redirected from `/admin/tenants` to `/dashboard`
- [ ] Scenario 23: Browser check that `system_admin` loads `/admin/tenants` without redirect

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — `navFor` badge counts compared against spec table; no extra badges present
- [ ] Risk 2 mitigation confirmed — URL bar checked in browser; no `(auth)` segment appears
- [ ] Risk 3 mitigation confirmed — `NEXT_PUBLIC_DEMO_MODE` check is inline in render, not module-level hoisted
- [ ] Risk 4 mitigation confirmed — `RequireAuth` prop name verified against existing auth implementation
- [ ] Risk 5 mitigation confirmed — all 9 placeholder routes exist as files and render without error
- [ ] Risk 6 mitigation confirmed — `startsWith` used for active nav; `/admin/tenants/new` highlights Tenants item
- [ ] Risk 7 mitigation confirmed — tenant pill has no navigation click handler

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | — | — | — | — | — |

*(To be populated during implementation review. Every row in Section 1 requires at least one entry here.)*

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** portal-shell
**Proposal:** `openspec/changes/portal-shell/proposal.md`
**Spec files reviewed:**
- specs/nav-config/spec.md
- specs/app-shell/spec.md
- specs/auth-layout/spec.md

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
