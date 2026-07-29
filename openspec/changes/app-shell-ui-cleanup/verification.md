# Verification Plan

**Change:** app-shell-ui-cleanup
**Generated:** 2026-07-29
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | app-shell | Sidebar Layout | sidebar renders correct nav for role | Given an authenticated `annotator` user, when `AppShell` mounts, then the sidebar nav contains exactly 3 items (My Work, Annotation, Documents) and no Settings/Tenants items | `sidebar.test.tsx`: "renders nav items for annotator (3 items, no Settings)" | - [x] |
| 2 | app-shell | Sidebar Layout | active nav item is highlighted | Given pathname `/admin/tenants/new`, when the sidebar renders for a `system_admin` user, then only the "Tenants" nav item has the active highlight style | Not covered by an automated test — pre-existing gap, untouched by this change (no nav/highlight code was modified) | - [ ] |
| 3 | app-shell | Sidebar Layout | badge renders when present | Given the "Annotation" nav item has `badge: 4`, when the sidebar renders for an `annotator` user, then a badge chip showing "4" appears next to the label | Not covered by an automated test — pre-existing gap, untouched by this change (no badge code was modified) | - [ ] |
| 4 | app-shell | Sidebar Layout | wordmark reads NER Platform | Given the sidebar renders, when the logo block is inspected, then the wordmark text is exactly "NER Platform" | `sidebar.test.tsx`: "wordmark reads NER Platform" | - [x] |
| 5 | app-shell | Sidebar Layout | no tenant pill is rendered | Given the sidebar renders for any authenticated user, when the sidebar DOM is inspected, then no tenant-initial avatar, tenant name, or tenant slug element is present between the logo block and the nav section | `sidebar.test.tsx`: "does not render a tenant pill" | - [x] |
| 6 | app-shell | Sidebar Layout | user strip chevron is rendered in a framed box | Given the user strip is visible, when the sidebar renders closed, then the `▾` is enclosed in a bordered 24×24px container matching `var(--surface-2)`/`var(--line)` | `sidebar.test.tsx`: "chevron rotates when menu opens and closes" (covers closed-state chevron) — untouched by this change | - [x] |
| 7 | app-shell | Sidebar Layout | user menu opens with spring animation | Given the user strip is rendered, when the user clicks the trigger, then the floating menu appears with the `menuPop` animation, the chevron rotates 180°, and a full-viewport backdrop renders | `sidebar.test.tsx`: "chevron rotates when menu opens and closes", "backdrop is rendered when menu is open" — untouched by this change | - [x] |
| 8 | app-shell | Sidebar Layout | menu closes on backdrop click | Given the floating menu is open, when the user clicks the backdrop outside the menu, then the menu closes and the chevron rotates back to 0° | `sidebar.test.tsx`: "chevron rotates when menu opens and closes" — untouched by this change | - [x] |
| 9 | app-shell | Sidebar Layout | menu closes on Escape | Given the floating menu is open, when the user presses Escape, then the menu closes | `sidebar.test.tsx`: "Escape key closes the menu" — untouched by this change | - [x] |
| 10 | app-shell | Sidebar Layout | Logout item has danger colour | Given the floating menu is open, when it renders the Logout item, then the label uses `var(--bad)` and hover applies `var(--bad-soft)` | `sidebar.test.tsx`: "Logout menu item uses ⎋ icon" (renders the item; colour asserted via code review, not a jsdom computed-style check) — untouched by this change | - [ ] |
| 11 | app-shell | Sidebar Layout | Settings navigates to /settings | Given the floating menu is open, when the user clicks "Settings", then the browser navigates to `/settings` and the menu closes | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |
| 12 | app-shell | Sidebar Layout | logout clears session and redirects | Given the menu is open, when the user clicks "Logout", then `useAuth().logout()` is called and the browser navigates to `/login` | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |
| 13 | app-shell | Topbar Layout | Topbar remains visible after scrolling | Given a page taller than the viewport, when the user scrolls past the topbar height, then the topbar stays visible and does not scroll out of view | Not covered by an automated test — pre-existing gap, untouched by this change (sticky positioning code was not modified) | - [ ] |
| 14 | app-shell | Topbar Layout | screen title and path are side-by-side on baseline | Given pathname `/admin/tenants`, when the topbar renders, then "Tenants" and "/admin/tenants" appear in the same row with baseline alignment, not stacked | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |
| 15 | app-shell | Topbar Layout | no search box is rendered | Given the topbar renders, when the DOM is inspected, then no search input, search icon, or "⌘K" hint element is present | `sidebar.test.tsx`: "does not render a search box regardless of demo mode" | - [x] |
| 16 | app-shell | Topbar Layout | no role-switcher is rendered regardless of demo mode | Given `NEXT_PUBLIC_DEMO_MODE` is `"true"` or unset, when the topbar renders, then no `AS` label or SA/TA/AN/BU chips appear and the component accepts no `demoRole`/`onDemoRoleChange` props | `sidebar.test.tsx`: "does not render the AS label or role-switcher chips when demo mode is true", "...when demo mode is unset"; `TopbarProps` no longer declares `demoRole`/`onDemoRoleChange` (typecheck-verified) | - [x] |
| 17 | app-shell | Topbar Layout | dark mode toggle has 10px border radius | Given the topbar is rendered, when the dark mode toggle is inspected, then its computed `border-radius` is 10px | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |
| 18 | app-shell | Topbar Layout | avatar has 10px border radius | Given the topbar is rendered, when the avatar element is inspected, then its computed `border-radius` is 10px | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |
| 19 | app-shell | Topbar Layout | dark mode toggle switches theme | Given the current theme is light, when the user clicks the dark mode toggle, then `useDarkMode().toggle()` is called and the `dark` class is added to `document.documentElement` | Not covered by an automated test — pre-existing gap, untouched by this change | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `demoRole` prop removal | AI may remove the Topbar's chips but leave `demoRole`/`onDemoRoleChange` in `TopbarProps` or in `AppShell.tsx`'s state, leaving dead code instead of a clean removal | Grep the portal source for `demoRole` and `onDemoRoleChange` after implementation — zero remaining references outside test files being updated |
| 2 | Tenant pill removal scope | AI may remove only the visible pill markup but leave now-unused helper code (`tenantDisplayName`, `tenantInitial` computation) behind in `Sidebar.tsx` | Read `Sidebar.tsx` post-change — confirm no orphaned unused variables/functions remain |
| 3 | `effectiveRole` derivation | AI may leave `AppShell.tsx` computing `effectiveRole = demoRole ?? user.role` instead of collapsing to `user.role` directly, silently keeping a dead branch | Read `AppShell.tsx` post-change — confirm `Sidebar` receives `user.role` directly with no `demoRole` state present |
| 4 | Wordmark string exactness | AI may introduce a variant spelling/casing ("Ner Platform", "NER platform") instead of the exact canonical "NER Platform" | Diff the literal string in `Sidebar.tsx` against "NER Platform" character-for-character |
| 5 | Test coverage drift | AI may delete the tenant-pill/search/role-switcher scenarios from `sidebar.test.tsx` without adding assertions for their absence, silently reducing coverage rather than replacing it | Confirm `sidebar.test.tsx` (and any Topbar test file) contains explicit assertions that the tenant pill, search box, and role-switcher are absent — not just deleted test blocks |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

No constraining ADRs — design.md identifies none of ADR-001 through ADR-008 as governing this presentation-layer change.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| — | No constraining ADRs | — | — |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (sidebar renders correct nav for role): `npx vitest run src/components/app-shell/sidebar.test.tsx` — "renders nav items for annotator (3 items, no Settings)" passes
- [ ] Scenario 2 (active nav item is highlighted): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 3 (badge renders when present): no automated test exists — pre-existing gap, not introduced by this change
- [x] Scenario 4 (wordmark reads NER Platform): test output — "wordmark reads NER Platform" passes
- [x] Scenario 5 (no tenant pill is rendered): test output — "does not render a tenant pill" passes
- [x] Scenario 6 (user strip chevron framed box): test output — "chevron rotates when menu opens and closes" passes (untouched by this change)
- [x] Scenario 7 (user menu opens with spring animation): test output — "chevron rotates when menu opens and closes", "backdrop is rendered when menu is open" pass (untouched by this change)
- [x] Scenario 8 (menu closes on backdrop click): covered by existing chevron/backdrop tests passing (untouched by this change)
- [x] Scenario 9 (menu closes on Escape): test output — "Escape key closes the menu" passes (untouched by this change)
- [ ] Scenario 10 (Logout item has danger colour): test renders the Logout item ("Logout menu item uses ⎋ icon" passes) but does not assert computed colour — no automated colour check exists, pre-existing gap
- [ ] Scenario 11 (Settings navigates to /settings): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 12 (logout clears session and redirects): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 13 (Topbar remains visible after scrolling): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 14 (screen title and path side-by-side on baseline): no automated test exists — pre-existing gap, not introduced by this change
- [x] Scenario 15 (no search box is rendered): test output — "does not render a search box regardless of demo mode" passes
- [x] Scenario 16 (no role-switcher regardless of demo mode): test output — "does not render the AS label or role-switcher chips when demo mode is true" and "...when demo mode is unset" pass; `tsc --noEmit` confirms `TopbarProps` no longer accepts `demoRole`/`onDemoRoleChange`
- [ ] Scenario 17 (dark mode toggle has 10px border radius): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 18 (avatar has 10px border radius): no automated test exists — pre-existing gap, not introduced by this change
- [ ] Scenario 19 (dark mode toggle switches theme): no automated test exists — pre-existing gap, not introduced by this change

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations): wordmark text, tenant-pill removal, search/role-switcher removal, `demoRole` state removal from `AppShell.tsx` all match design.md Decisions 1 and 2
- [x] All ADR compliance steps in Section 3 confirmed ✓ (N/A — no constraining ADRs)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `grep -rn "demoRole\|onDemoRoleChange" src/portal/src` returns zero matches
- [x] Risk 2 mitigation confirmed — read `Sidebar.tsx` post-change: `tenantDisplayName` function and `tenantName`/`tenantInitial` variables are fully removed, no orphaned helpers remain
- [x] Risk 3 mitigation confirmed — read `AppShell.tsx` post-change: no `demoRole` state exists, `<Sidebar effectiveRole={user.role} />` passes the real role directly
- [x] Risk 4 mitigation confirmed — `Sidebar.tsx` wordmark literal is exactly `NER Platform`, verified by direct read and by test "wordmark reads NER Platform"
- [x] Risk 5 mitigation confirmed — `sidebar.test.tsx` contains "does not render a tenant pill", "does not render a search box regardless of demo mode", and "does not render the AS label or role-switcher chips..." (both demo-mode states)

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

**Change slug:** app-shell-ui-cleanup
**Proposal:** `openspec/changes/app-shell-ui-cleanup/proposal.md`
**Spec files reviewed:**
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
