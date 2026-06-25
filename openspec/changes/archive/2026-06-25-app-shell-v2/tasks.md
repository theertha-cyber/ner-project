## 1. Global Styles — `menuPop` keyframe

- [x] 1.1 Add `@keyframes ner-menu-pop` to `src/portal/src/app/globals.css` with the spec'd cubic-bezier: `0%{opacity:0;transform:translateY(8px) scale(.97)} 100%{opacity:1;transform:none}`
- [x] 1.2 Register `animate-menu-pop` in `src/portal/tailwind.config.ts` under `theme.extend.animation` pointing at `ner-menu-pop .18s cubic-bezier(.16,1,.3,1) both`
- [x] 1.3 Verify `globals.css` already contains `@keyframes meshDrift`; if not, add it (needed for hero Variant B)

## 2. Sidebar — User Strip Trigger (Sidebar.tsx)

- [x] 2.1 In `src/portal/src/components/app-shell/Sidebar.tsx`, remove the `useRef`+`useEffect` `handleClickOutside` pattern (the `mousedown` document listener)
- [x] 2.2 Replace the `⋮` ellipsis trigger button with a full-width `<button>` that renders `userInitials`, `email` (truncated), `roleLabel`, and a `▾` character styled with `transition: transform 0.18s ease; transform: rotate({menuOpen ? 180 : 0}deg)`
- [x] 2.3 Apply state-driven border and background to the trigger: border `var(--primary-line)` / background `var(--primary-soft)` when open, `var(--line)` / transparent when closed
- [x] 2.4 When `menuOpen` is true, render a `position:fixed; inset:0; z-index:60` transparent `<div onClick={() => setMenuOpen(false)}>` as the backdrop (mount it above everything else but below the menu panel)
- [x] 2.5 Render the floating menu panel at `position:absolute; left:12px; right:12px; bottom:62px; z-index:61` with `animation: ner-menu-pop .18s cubic-bezier(.16,1,.3,1) both` and `transform-origin: bottom center`
- [x] 2.6 Update the Logout menu item: change icon to `⎋` and verify it still calls `useAuth().logout()` then `router.push('/login')`
- [x] 2.7 Retain the Escape key handler (already present via `useEffect` on `keydown`)

## 3. Sidebar — Tenant Pill Caret

- [x] 3.1 In `Sidebar.tsx`, add a `▾` character to the right of the tenant pill (display-only; no onClick change)

## 4. Topbar — Demo Role Switcher `AS` Label (Topbar.tsx)

- [x] 4.1 In `src/portal/src/components/app-shell/Topbar.tsx`, inside the `isDemoMode` block, prepend a static `<span>` with text `"AS"` using JetBrains Mono 10px, colour `var(--ink-3)`, inside the role-switcher pill container and before the four role chip buttons
- [x] 4.2 Ensure the `AS` span is excluded when `isDemoMode` is false (it is inside the same conditional block)

## 5. Dashboard Hero — Variant B (`heroVariant` helper + DashboardHero)

- [x] 5.1 Create `src/portal/src/lib/dashboard.ts` and export a pure function `heroVariant(role: string): 'a' | 'b'` — returns `'b'` for `'system_admin'`, `'a'` for all other values
- [x] 5.2 In `src/portal/src/components/dashboard/DashboardHero.tsx`, add a `variant: 'a' | 'b'` prop alongside the existing `layout` prop
- [x] 5.3 Implement Variant B rendering: wrap hero content in a `position:relative` container with two absolutely-positioned mesh gradient orbs (`background:radial-gradient(circle,#c2410c,transparent 60%)` + `#475569` + respective `meshDrift` animation durations 18s/23s); set all text to `color:#fff`
- [x] 5.4 Variant A rendering remains unchanged (`var(--surface-2)` background, standard ink token text)
- [x] 5.5 Update `src/portal/src/app/(auth)/dashboard/page.tsx` to call `heroVariant(user.role)` and pass `variant` to `<DashboardHero>`

## 6. Tests

- [x] 6.1 Update `src/portal/src/components/app-shell/sidebar.test.tsx`:
  - Add test for chevron rotation (open/closed state) — *covers rows 5–6 in verification.md*
  - Add test for backdrop presence when menu open — *covers row 5*
  - Add test for Escape key closes menu — *covers row 7*
  - Add test for Logout icon is `⎋` — *covers row 9*
  - Add test for tenant pill contains `▾` — *covers row 4*
- [x] 6.2 Add test to `sidebar.test.tsx` or a new topbar test file for `AS` label conditional rendering — *covers rows 12–13 in verification.md*
- [x] 6.3 Create `src/portal/src/lib/dashboard.test.ts` with unit tests for `heroVariant`:
  - `heroVariant("system_admin") === 'b'` — *covers row 19*
  - All other roles return `'a'` (test at least `annotator`, `tenant_admin`, `business_user`) — *covers row 20*
- [x] 6.4 Add tests (or Storybook stories) for `DashboardHero` with `variant="b"`:
  - Variant B renders dark background and white text — *covers row 16*
  - Variant A renders light background — *covers row 17*
  - Variant B + Command layout collapses hero but keeps dark background — *covers row 18*

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 7.6 Run `openspec validate app-shell-v2 --type change --strict` and confirm it exits clean before archive.
