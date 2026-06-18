## 1. Nav Config Module

- [x] 1.1 Create `src/portal/src/lib/nav-config.ts` with `NavItem` type, `navFor(role)` pure function, and `SCREEN_TITLES` record covering all 11 screen keys
- [x] 1.2 Verify `navFor("system_admin")` returns 6 items with correct badges (Tenants badge 6, Training Queue badge 2)
- [x] 1.3 Verify `navFor("tenant_admin")` returns 8 items with Training Jobs badge 1
- [x] 1.4 Verify `navFor("annotator")` returns 4 items with Annotation badge 4
- [x] 1.5 Verify `navFor("business_user")` returns 5 items with no badges
- [x] 1.6 Verify `SCREEN_TITLES["tenants"]` returns `["Tenants", "/admin/tenants"]` and unknown key falls back to `["Dashboard", "/dashboard"]`

## 2. AppShell Component — Sidebar

- [x] 2.1 Create `src/portal/src/components/app-shell/Sidebar.tsx` (248 px sticky, logo block, tenant pill, nav section, user strip)
- [x] 2.2 Implement logo block: orange rounded square with "n" glyph + "nerplatform" wordmark in Hanken Grotesk
- [x] 2.3 Implement tenant pill: first-letter initial, tenant name, tenant slug in JetBrains Mono; display-only (hover border highlight only, no click handler that navigates)
- [x] 2.4 Render `navFor(user.role)` as `<button>` elements with active highlight via `usePathname().startsWith(item.href)` (prefix match, not strict equality)
- [x] 2.5 Render badge pill chips in JetBrains Mono for nav items with `badge` count
- [x] 2.6 Implement user strip (pinned bottom): avatar gradient square with `userInitials`, email (truncated), role label in JetBrains Mono, logout button (⎋ icon) that calls `useAuth().logout()` then `router.push("/login")`

## 3. AppShell Component — Topbar

- [x] 3.1 Create `src/portal/src/components/app-shell/Topbar.tsx` (62 px fixed-height, border-bottom, z-index 50)
- [x] 3.2 Resolve screen title + path from `SCREEN_TITLES` keyed on current pathname; fall back to `["Dashboard", "/dashboard"]` for unknown paths
- [x] 3.3 Add non-interactive search placeholder ("⌕ search · ⌘K" in JetBrains Mono) — no click handler, no dialog
- [x] 3.4 Add role-switcher chips (SA/TA/AN/BU) rendered only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` (inline check in render body — do NOT hoist to module level)
- [x] 3.5 Add dark mode toggle (36×36 button) that calls `useDarkMode().toggle()`; icon shows ☀ in dark mode and ☽ in light mode
- [x] 3.6 Add avatar (36×36 gradient square) showing `userInitials`

## 4. AppShell Root Component

- [x] 4.1 Create `src/portal/src/components/app-shell/AppShell.tsx` as `"use client"` component; compose Sidebar + Topbar + `{children}` slot; read `useAuth()`, `useDarkMode()`, `usePathname()`
- [x] 4.2 Export `AppShell` from `src/portal/src/components/app-shell/index.ts`

## 5. Authenticated Route Group Layout

- [x] 5.1 Create directory `src/portal/src/app/(auth)/`
- [x] 5.2 Create `src/portal/src/app/(auth)/layout.tsx` (Server Component) that renders `<RequireAuth><AppShell>{children}</AppShell></RequireAuth>`
- [x] 5.3 Create `src/portal/src/app/(auth)/admin/layout.tsx` that renders `<RequireAuth roles={["system_admin"]}>{children}</RequireAuth>` (uses existing `RequireAuth` prop signature — verify prop name before writing)

## 6. File Migration (admin pages)

- [x] 6.1 Move `src/portal/src/app/dashboard/page.tsx` → `src/portal/src/app/(auth)/dashboard/page.tsx`
- [x] 6.2 Move `src/portal/src/app/admin/` → `src/portal/src/app/(auth)/admin/` (all pages and sub-layouts)
- [x] 6.3 Delete old `src/portal/src/app/admin/layout.tsx` (role-guard logic now lives in `(auth)/admin/layout.tsx`)
- [x] 6.4 Confirm all `@/…` alias imports in moved files still resolve correctly (no path changes needed due to `tsconfig.json` paths)

## 7. Placeholder Screens

- [x] 7.1 Create `PlaceholderScreen` component (`src/portal/src/components/PlaceholderScreen.tsx`) that displays the screen name prominently and a "Coming soon" sub-label; must never render blank or throw
- [x] 7.2 Create `src/portal/src/app/(auth)/annotation/page.tsx` using `PlaceholderScreen`
- [x] 7.3 Create `src/portal/src/app/(auth)/training-jobs/page.tsx` using `PlaceholderScreen`
- [x] 7.4 Create `src/portal/src/app/(auth)/models/page.tsx` using `PlaceholderScreen`
- [x] 7.5 Create `src/portal/src/app/(auth)/documents/page.tsx` using `PlaceholderScreen`
- [x] 7.6 Create `src/portal/src/app/(auth)/entity-types/page.tsx` using `PlaceholderScreen`
- [x] 7.7 Create `src/portal/src/app/(auth)/users/page.tsx` using `PlaceholderScreen`
- [x] 7.8 Create `src/portal/src/app/(auth)/extractions/page.tsx` using `PlaceholderScreen`
- [x] 7.9 Create `src/portal/src/app/(auth)/audit/page.tsx` using `PlaceholderScreen`
- [x] 7.10 Create `src/portal/src/app/(auth)/settings/page.tsx` using `PlaceholderScreen`

## 8. Smoke Tests (Browser)

- [x] 8.1 Start dev server; confirm `/dashboard` renders with sidebar and topbar; URL shows no `(auth)` prefix
- [ ] 8.2 Log in as `system_admin`; confirm 6 nav items in sidebar with correct badges; navigate to `/admin/tenants/new` and confirm Tenants item is highlighted
- [ ] 8.3 Use role-switcher (enable `NEXT_PUBLIC_DEMO_MODE=true` in `.env.local`); switch to `annotator` role and confirm sidebar shows exactly 4 items
- [ ] 8.4 Log out from user strip; confirm redirect to `/login` and shell chrome is gone
- [ ] 8.5 Navigate to `/extractions` as any authenticated user; confirm "Extractions" and "Coming soon" render within shell chrome
- [ ] 8.6 Open browser tab without session; navigate to `/admin/tenants`; confirm redirect to `/login`
- [ ] 8.7 Log in as `tenant_admin`; navigate to `/admin/tenants`; confirm redirect to `/dashboard`
- [ ] 8.8 Confirm role-switcher chips are absent with `NEXT_PUBLIC_DEMO_MODE` unset

## 9. Verification & Evidence

- [ ] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 9.6 Run `openspec validate portal-shell --type change --strict` and confirm it exits clean before archive
