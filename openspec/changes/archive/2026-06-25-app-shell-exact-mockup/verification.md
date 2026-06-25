# Verification Plan

**Change:** app-shell-exact-mockup
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | app-shell | Sidebar Layout | sidebar renders correct nav for role | Given an annotator user, when AppShell mounts, then exactly 3 nav items (My Work, Annotation, Documents) are visible and no Tenants or Settings item appears | — | - [ ] |
| 2 | app-shell | Sidebar Layout | active nav item is highlighted | Given pathname `/admin/tenants/new` for system_admin, when sidebar renders, then the Tenants item has active highlight style and no other item does | — | - [ ] |
| 3 | app-shell | Sidebar Layout | badge renders when present | Given Annotation nav item has badge 4, when sidebar renders for annotator, then a chip showing "4" appears next to the Annotation label | — | - [ ] |
| 4 | app-shell | Sidebar Layout | tenant pill shows correct values with muted avatar | Given tenantSlug "acme", when sidebar renders, then the tenant pill has a visible surface-3 background fill and the avatar uses var(--primary-soft) background (not full brand orange) and the ▾ caret is visible | — | - [ ] |
| 5 | app-shell | Sidebar Layout | user strip chevron is rendered in a framed box | Given the sidebar in closed-menu state, when rendered, then the ▾ character is enclosed in a 24×24px bordered container with visible border and var(--surface-2) background | — | - [ ] |
| 6 | app-shell | Sidebar Layout | user menu opens with spring animation | Given the user strip is visible, when the trigger button is clicked, then a floating menu appears with menuPop spring animation and the chevron inside its box rotates 180° and a full-viewport backdrop overlay is rendered | — | - [ ] |
| 7 | app-shell | Sidebar Layout | menu closes on backdrop click | Given the floating menu is open, when the user clicks the backdrop overlay, then the menu closes and the chevron rotates back to 0° | — | - [ ] |
| 8 | app-shell | Sidebar Layout | menu closes on Escape | Given the floating menu is open, when Escape is pressed, then the menu closes | — | - [ ] |
| 9 | app-shell | Sidebar Layout | Logout item has danger colour | Given the floating menu is open, when rendered, then the Logout label text colour is var(--bad) red and hovering it applies var(--bad-soft) background | — | - [ ] |
| 10 | app-shell | Sidebar Layout | Settings navigates to /settings | Given the floating menu is open, when the Settings item is clicked, then the browser navigates to /settings and the menu closes | — | - [ ] |
| 11 | app-shell | Sidebar Layout | logout clears session and redirects | Given the menu is open, when Logout is clicked, then useAuth().logout() is called and browser navigates to /login | — | - [ ] |
| 12 | app-shell | Topbar Layout | Topbar remains visible after scrolling | Given a page with content taller than the viewport, when the user scrolls down, then the topbar remains visible at the top and does not scroll out of view | — | - [ ] |
| 13 | app-shell | Topbar Layout | screen title and path are side-by-side on baseline | Given pathname /admin/tenants, when topbar renders, then title "Tenants" and path "/admin/tenants" appear in the same horizontal row with baseline alignment (not stacked vertically) | — | - [ ] |
| 14 | app-shell | Topbar Layout | role-switcher hidden in production mode | Given NEXT_PUBLIC_DEMO_MODE is not "true", when topbar renders, then no role-switcher pill, AS label, or SA/TA/AN/BU chips are visible | — | - [ ] |
| 15 | app-shell | Topbar Layout | role-switcher wrapped in single bordered pill | Given NEXT_PUBLIC_DEMO_MODE is "true", when topbar renders, then the AS label and four role chips are rendered inside a single container with a visible border and background fill | — | - [ ] |
| 16 | app-shell | Topbar Layout | dark mode toggle has 10px border radius | Given the topbar is rendered, when the dark mode toggle button is inspected, then its computed border-radius is 10px | — | - [ ] |
| 17 | app-shell | Topbar Layout | avatar has 10px border radius | Given the topbar is rendered, when the user avatar element is inspected, then its computed border-radius is 10px | — | - [ ] |
| 18 | app-shell | Topbar Layout | dark mode toggle switches theme | Given theme is light, when the dark mode toggle is clicked, then useDarkMode().toggle() is called and the dark class is added to document.documentElement | — | - [ ] |
| 19 | app-shell | Topbar Layout | search placeholder is non-interactive | Given the topbar is rendered, when the user clicks the search area, then no dialog, modal, or command palette opens | — | - [ ] |
| 20 | design-tokens | Page enter animation keyframe | animate-fade-up class is registered in Tailwind config | Given tailwind.config.ts is loaded, when the animation extension key is inspected, then an entry for fade-up exists mapping to ner-fade-up 0.35s ease both | — | - [ ] |
| 21 | design-tokens | Page enter animation keyframe | screen root div receives the animation class | Given the user navigates to /dashboard, when the page component mounts, then the root div of the page has the animate-fade-up class and transitions from partially transparent and offset to fully opaque | — | - [ ] |
| 22 | design-tokens | Page enter animation keyframe | animation fires on each route change | Given the user navigates from Documents to Annotation, when the Annotation page mounts, then its root element plays the fadeUp animation | — | - [ ] |
| 23 | widget-keys-screen | Widget Keys Screen | widget-keys nav item appears for tenant_admin | Given authenticated user with role tenant_admin, when the sidebar renders, then a "Widget Keys" nav item is visible and clicking it navigates to /widget-keys | — | - [ ] |
| 24 | widget-keys-screen | Widget Keys Screen | widget-keys nav item hidden for other roles | Given authenticated user with role annotator, business_user, or system_admin, when the sidebar renders, then no "Widget Keys" item is visible | — | - [ ] |
| 25 | widget-keys-screen | Widget Keys Screen | topbar shows correct title for /widget-keys | Given the user navigates to /widget-keys, when the topbar renders, then the title reads "Widget Keys" and the path reads "/widget-keys" | — | - [ ] |
| 26 | widget-keys-screen | Widget Keys Screen | screen renders API path breadcrumb | Given the user is on /widget-keys, when the page renders, then the breadcrumb label `/api/v1/tenants/{slug}/widget-keys · port 8006` is visible above the page title | — | - [ ] |
| 27 | widget-keys-screen | Widget Keys Screen | keys table renders when API returns data | Given GET /widget-keys returns a list of keys, when the screen mounts, then each key row shows name, prefix, creation date, status badge, and copy button | — | - [ ] |
| 28 | widget-keys-screen | Widget Keys Screen | empty state shown when API returns empty list | Given GET /widget-keys returns an empty array, when the screen mounts, then an empty-state message and placeholder "Create Key" button are displayed | — | - [ ] |
| 29 | widget-keys-screen | Widget Keys Screen | empty state shown on API error | Given GET /widget-keys returns a 5xx error, when the screen mounts, then the empty-state message is displayed without crash and no error boundary is triggered | — | - [ ] |
| 30 | widget-keys-screen | Widget Keys Screen | copy button copies key prefix to clipboard | Given a widget key row is rendered, when the copy button is clicked, then navigator.clipboard.writeText is called with the key value | — | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Sidebar background token | AI may retain the `backdropFilter` or `rgba` opacity glass style instead of replacing with solid `var(--surface-2)`, causing the change to be incomplete | Inspect the compiled sidebar element in the browser DevTools — `backdrop-filter` must be absent; background must resolve to a solid colour |
| 2 | Tenant pill avatar colour | AI may use `var(--primary)` (full brand orange) for the avatar instead of `var(--primary-soft)` / `var(--primary-2)` (muted variant) | Compare the rendered tenant pill avatar background colour against the mockup — it should appear as a muted/pale tint, not the full brand orange |
| 3 | Chevron framed box sizing | AI may render the chevron box with incorrect dimensions (e.g., 20×20 or 28×28) or omit the border, making it look like a plain text `▾` | Visually inspect the user strip trigger in the browser; the framed box should be clearly distinct from the previous plain chevron |
| 4 | Role-switcher container vs loose flex | AI may only add a border to the outer flex container already in place (which has `gap: 4` with no background) rather than introducing a proper pill wrapper with `background: var(--surface-3)` and inner `padding: 3px` | Inspect the role-switcher in the topbar — the `AS` label and all four chips should be visually contained within a single bounded pill with a filled background |
| 5 | Topbar title/path layout direction | AI may set `flexDirection: 'row'` without also setting `alignItems: 'baseline'`, making the path drop to the bottom of the title text rather than sitting on the baseline | Check the topbar at different font sizes; both title and path should share the same text baseline line |
| 6 | fadeUp applied to layout instead of page | AI may add `animate-fade-up` to the `(auth)/layout.tsx` component rather than each `page.tsx`, meaning the animation only fires on initial app load and not on route changes | Navigate between two screens after the change — each navigation should trigger the fade-up on the new screen's content |
| 7 | Logout colour applies to wrong element | AI may apply `color: var(--bad)` to the logout button's container rather than the text/icon content, or may omit the hover background variant entirely | Click to open the user menu — Logout text should appear in a clearly distinct red; hovering should show a red-tinted background |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 | OpenSpec SDD mandatory artifacts | All change artifacts (proposal, design, specs, verification, tasks) must be present before implementation | Confirm all six artifacts exist at `openspec/changes/app-shell-exact-mockup/` |
| ADR-005 | Role-specific agents, bounded scope | Frontend changes must stay within portal boundary; no infra or backend changes | Confirm git diff touches only `src/portal/` and `openspec/` files; no backend service files modified |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Row 1 — Browser screenshot or test output showing annotator sidebar with exactly 3 nav items and no Tenants/Settings
- [ ] Row 2 — Screenshot of active nav highlight on Tenants item for system_admin at /admin/tenants
- [ ] Row 3 — Screenshot of "4" badge chip on Annotation nav item for annotator
- [ ] Row 4 — Screenshot of tenant pill showing surface-3 background fill and muted-orange avatar (not full brand red)
- [ ] Row 5 — Screenshot of closed user strip with the framed 24×24 bordered chevron box visible
- [ ] Row 6 — Screen recording or sequential screenshots showing: click trigger → menu appears with animation → chevron rotates 180° → backdrop visible
- [ ] Row 7 — Screenshot or recording showing backdrop click closes the menu and chevron returns to 0°
- [ ] Row 8 — Recording or test showing Escape key closes the menu
- [ ] Row 9 — Screenshot of open user menu with Logout in red text; hover state showing red-tinted background
- [ ] Row 10 — Recording or test showing Settings click navigates to /settings and closes menu
- [ ] Row 11 — Test output or recording showing logout() called and redirect to /login
- [ ] Row 12 — Recording showing topbar stays fixed while page content scrolls
- [ ] Row 13 — Screenshot of topbar showing title and path in the same row (horizontal, baseline-aligned)
- [ ] Row 14 — Screenshot of topbar in production mode (no DEMO flag) with no role chips visible
- [ ] Row 15 — Screenshot of topbar in demo mode showing AS label and all four chips inside a single bordered pill container
- [ ] Row 16 — DevTools style inspection confirming dark mode toggle border-radius is 10px
- [ ] Row 17 — DevTools style inspection confirming avatar border-radius is 10px
- [ ] Row 18 — Test output confirming useDarkMode().toggle() is called on click and dark class is toggled
- [ ] Row 19 — Test output confirming no dialog, modal, or command palette opens on search placeholder click
- [ ] Row 20 — `tailwind.config.ts` inspection showing `fade-up: 'ner-fade-up 0.35s ease both'` in the animation config
- [ ] Row 21 — Screenshot of /dashboard with the root div having `animate-fade-up` class in DevTools
- [ ] Row 22 — Recording of navigating between two screens showing the fadeUp animation fires on each arrival
- [ ] Row 23 — Screenshot of tenant_admin sidebar with Widget Keys nav item visible; click navigating to /widget-keys
- [ ] Row 24 — Screenshots of sidebar for annotator, business_user, and system_admin roles confirming Widget Keys item is absent
- [ ] Row 25 — Screenshot of topbar on /widget-keys showing "Widget Keys" title and "/widget-keys" path
- [ ] Row 26 — Screenshot of /widget-keys page showing the API path breadcrumb above the page title
- [ ] Row 27 — Screenshot of the keys table with at least one row showing name, prefix, date, status badge, and copy button (may require mock data)
- [ ] Row 28 — Screenshot of empty-state UI with the "Create Key" placeholder button when no keys exist
- [ ] Row 29 — Screenshot or test showing empty-state renders when the API call fails (no crash, no error boundary)
- [ ] Row 30 — Test output or recording showing navigator.clipboard.writeText is called when the copy button is clicked

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (glass removal) — DevTools confirms no `backdrop-filter` on sidebar or topbar elements
- [ ] Risk 2 (tenant pill avatar colour) — Computed background of avatar element matches var(--primary-soft) (muted tint, not #c2410c)
- [ ] Risk 3 (chevron box size) — DevTools confirms chevron container is exactly 24×24px with a visible border
- [ ] Risk 4 (role-switcher container) — DevTools confirms a single bordered pill wrapper around all role chips and AS label in demo mode
- [ ] Risk 5 (title/path baseline) — Screenshot at multiple viewport widths confirming title and path share the same baseline
- [ ] Risk 6 (fadeUp on page not layout) — Navigate between 3+ screens and confirm animation fires each time
- [ ] Risk 7 (logout danger colour) — DevTools computed style of Logout label text colour matches the value of var(--bad)

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry. Do not pre-fill.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** app-shell-exact-mockup
**Proposal:** `openspec/changes/app-shell-exact-mockup/proposal.md`
**Spec files reviewed:**
- specs/app-shell/spec.md
- specs/design-tokens/spec.md
- specs/widget-keys-screen/spec.md

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
