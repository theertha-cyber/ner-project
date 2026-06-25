# Verification Plan

**Change:** app-shell-v2
**Generated:** 2026-06-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | app-shell | Sidebar Layout | sidebar renders correct nav for role | Given an `annotator` user, when AppShell mounts, then exactly 3 nav items (My Work, Annotation, Documents) appear and no Settings or Tenants items are visible | | - [ ] |
| 2 | app-shell | Sidebar Layout | active nav item is highlighted | Given pathname `/admin/tenants/new` and a `system_admin` user, when sidebar renders, then only the "Tenants" item has the active highlight style | | - [ ] |
| 3 | app-shell | Sidebar Layout | badge renders when present | Given Annotation nav item has `badge: 4`, when sidebar renders for `annotator`, then a badge chip showing "4" appears next to Annotation | | - [ ] |
| 4 | app-shell | Sidebar Layout | tenant pill shows correct values with caret | Given `tenantSlug = "acme"`, when sidebar renders, then the pill shows the initial, tenant name, slug, and a `▾` caret | | - [ ] |
| 5 | app-shell | Sidebar Layout | user menu opens with spring animation | Given the user strip is rendered, when the user clicks the chevron trigger, then the menu appears with `menuPop` animation, the chevron rotates 180°, and a full-viewport backdrop overlay is present | | - [ ] |
| 6 | app-shell | Sidebar Layout | menu closes on backdrop click | Given the floating menu is open, when the user clicks the backdrop overlay, then the menu closes and the chevron returns to 0° | | - [ ] |
| 7 | app-shell | Sidebar Layout | menu closes on Escape | Given the floating menu is open, when Escape is pressed, then the menu closes | | - [ ] |
| 8 | app-shell | Sidebar Layout | Settings navigates to /settings | Given the menu is open, when the user clicks Settings, then the router navigates to `/settings` and the menu closes | | - [ ] |
| 9 | app-shell | Sidebar Layout | logout clears session and redirects | Given the menu is open, when the user clicks Logout (⎋ icon), then `useAuth().logout()` is called and the router navigates to `/login` | | - [ ] |
| 10 | app-shell | Topbar Layout | Topbar remains visible after scrolling | Given a page taller than the viewport, when the user scrolls down, then the topbar remains visible at the top of the viewport | | - [ ] |
| 11 | app-shell | Topbar Layout | screen title matches pathname | Given pathname `/admin/tenants`, when topbar renders, then title reads "Tenants" and path reads "/admin/tenants" | | - [ ] |
| 12 | app-shell | Topbar Layout | role-switcher hidden in production mode | Given `NEXT_PUBLIC_DEMO_MODE` is not `"true"`, when topbar renders, then no SA / TA / AN / BU chips and no `AS` label are visible | | - [ ] |
| 13 | app-shell | Topbar Layout | role-switcher shows AS label in demo mode | Given `NEXT_PUBLIC_DEMO_MODE === "true"`, when topbar renders, then the `AS` label chip appears before the four role chips in JetBrains Mono 10px `var(--ink-3)` colour | | - [ ] |
| 14 | app-shell | Topbar Layout | dark mode toggle switches theme | Given light mode is active, when the dark mode toggle is clicked, then `useDarkMode().toggle()` is called and `dark` class is added to `document.documentElement` | | - [ ] |
| 15 | app-shell | Topbar Layout | search placeholder is non-interactive | Given the topbar is rendered, when the user clicks the search area, then no dialog, modal, or command palette opens | | - [ ] |
| 16 | portal-dashboard | Hero Variant B | system_admin hero renders Variant B dark mesh | Given the user has role `system_admin`, when the dashboard renders, then the hero shows an animated dark mesh with orange and slate orbs and all hero text is white | | - [ ] |
| 17 | portal-dashboard | Hero Variant B | non-admin roles render Variant A light hero | Given the user has role `annotator`, `tenant_admin`, or `business_user`, when the dashboard renders, then the hero uses `var(--surface-2)` background with standard ink token text colours | | - [ ] |
| 18 | portal-dashboard | Hero Variant B | Variant B still respects Editorial/Command layout | Given `system_admin` user with "Command" layout preference, when dashboard renders, then the dark mesh background is present AND the hero collapses to compact single-line (body hidden) | | - [ ] |
| 19 | portal-dashboard | Hero Variant B | heroVariant helper is pure and testable (system_admin) | Given `heroVariant("system_admin")` is called, then it returns `'b'` without side effects | | - [ ] |
| 20 | portal-dashboard | Hero Variant B | heroVariant helper is pure and testable (non-admin) | Given `heroVariant` is called with any role other than `system_admin`, then it returns `'a'` | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Chevron rotation CSS | AI may use `transform: scaleY(-1)` or swap characters instead of the specified `rotate(180deg)` | Inspect the rendered trigger in both open and closed states; verify the chevron character `▾` is a single DOM node with `transform: rotate(180deg)` applied when open |
| 2 | `menuPop` keyframe registration | AI may inline the animation style or omit the keyframe from `globals.css`, causing the animation to silently fall back to no animation | Check `globals.css` for `@keyframes menuPop` (or the prefixed `ner-menu-pop`) and verify `animate-menu-pop` is registered in `tailwind.config.ts` |
| 3 | Backdrop z-index stacking | AI may assign the backdrop and menu panel the same z-index or reverse them, causing the backdrop to intercept menu clicks | Inspect the DOM when the menu is open: backdrop element must have z-index 60, menu panel must have z-index 61 |
| 4 | `heroVariant` scope creep | AI may read `useAuth()` inside `heroVariant()` instead of accepting `role` as an argument, coupling the helper to auth context and breaking unit testability | Call `heroVariant` in a unit test without a React/auth context and confirm it returns the correct variant without throwing |
| 5 | `AS` label conditionality | AI may render the `AS` label unconditionally (outside the `NEXT_PUBLIC_DEMO_MODE` guard) | Toggle `NEXT_PUBLIC_DEMO_MODE` off and verify the `AS` label is absent; toggle it on and verify it appears |
| 6 | `menuPop` vs `popIn` animation confusion | The codebase already has a `popIn` keyframe; AI may apply `popIn` to the user menu instead of the new `menuPop` spring cubic-bezier | Search for `animation:` on the user menu panel element; confirm it references `menuPop` not `popIn` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 | OpenSpec SDD mandatory artifacts | All change artifacts (proposal, design, specs, verification, tasks) must be present and coherent before implementation | Confirm all artifact files exist in `openspec/changes/app-shell-v2/` and pass `openspec status` |
| ADR-005 | Role-specific agents, bounded scope | Frontend implementation must not introduce infra, backend, or auth changes | Verify the diff is scoped to `src/portal/` only; no changes to `src/gateway/`, `docker-compose.yml`, or infra configs |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Row 1 — Annotator nav screenshot or Storybook story showing exactly 3 items with no Settings/Tenants
- [ ] Row 2 — Screenshot or test showing "Tenants" highlighted at `/admin/tenants/new` and no other item highlighted
- [ ] Row 3 — Screenshot showing badge chip "4" next to Annotation for annotator role
- [ ] Row 4 — Screenshot of tenant pill with `▾` caret visible
- [ ] Row 5 — Screen recording or test trace showing menu opens with spring animation, chevron rotates, backdrop is present
- [ ] Row 6 — Test trace or screen recording showing backdrop click closes menu and chevron returns to 0°
- [ ] Row 7 — Test output: keyboard event Escape closes the menu
- [ ] Row 8 — Test output or trace: clicking Settings triggers navigation to `/settings` and menu closes
- [ ] Row 9 — Test output: clicking Logout (⎋ icon) calls `useAuth().logout()` and navigates to `/login`
- [ ] Row 10 — Visual verification: scroll a long page and confirm topbar stays fixed at top
- [ ] Row 11 — Screenshot or test: topbar shows "Tenants" + "/admin/tenants" at the correct pathname
- [ ] Row 12 — Screenshot in production mode (`NEXT_PUBLIC_DEMO_MODE` not set): no AS label or role chips
- [ ] Row 13 — Screenshot in demo mode: AS label + 4 role chips visible in topbar
- [ ] Row 14 — Test output: dark mode toggle calls `useDarkMode().toggle()` and `dark` class is set
- [ ] Row 15 — Test trace: clicking search area produces no dialog/modal/command palette
- [ ] Row 16 — Screenshot of `system_admin` dashboard showing dark mesh hero with white text and animated gradients
- [ ] Row 17 — Screenshot of annotator/tenant_admin/business_user dashboard showing light `var(--surface-2)` hero
- [ ] Row 18 — Screenshot of `system_admin` dashboard in Command layout: dark mesh present + compact hero (no body text)
- [ ] Row 19 — Unit test output: `heroVariant("system_admin")` returns `'b'`
- [ ] Row 20 — Unit test output: `heroVariant` returns `'a'` for all non-system_admin roles

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 — DOM inspection confirms chevron is a single `▾` node with `rotate(180deg)` applied when open (not character swap)
- [ ] Risk 2 — `globals.css` contains `@keyframes menuPop`; `tailwind.config.ts` registers `animate-menu-pop`
- [ ] Risk 3 — DOM inspection confirms backdrop z-index 60 < menu panel z-index 61
- [ ] Risk 4 — `heroVariant` unit test passes without any React context provider (pure function confirmed)
- [ ] Risk 5 — `AS` label absent when `NEXT_PUBLIC_DEMO_MODE` is not `"true"`, present when it is
- [ ] Risk 6 — User menu panel references `menuPop` animation, not `popIn`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** app-shell-v2
**Proposal:** `openspec/changes/app-shell-v2/proposal.md`
**Spec files reviewed:**
- specs/app-shell/spec.md
- specs/portal-dashboard/spec.md

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
