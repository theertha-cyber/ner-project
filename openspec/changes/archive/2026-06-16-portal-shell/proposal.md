## Why

SP-02 (portal-auth) delivered a working login flow but every authenticated route lands on a bare page with no persistent navigation. Users have no way to move between screens, no identity context visible, and no route structure to support the screens built in SP-04 through SP-11. The app shell unblocks all subsequent feature specs by establishing the authenticated layout contract.

## What Changes

- Add a Next.js App Router route group `app/(auth)/` with a shared layout that wraps every authenticated screen in `<RequireAuth>` + `<AppShell>`.
- Implement `AppShell`: a 248 px sticky sidebar (logo, tenant switcher pill, role-specific nav, user strip + logout) and a 62 px topbar (screen title/path, search placeholder, role-switcher chips, dark mode toggle, avatar).
- Define the role → nav-item matrix (`navFor`) for all four roles (system_admin, tenant_admin, annotator, business_user).
- **BREAKING**: Move existing admin pages from `app/admin/…` into `app/(auth)/admin/…` so they inherit the authenticated layout automatically. URLs remain the same.
- Add `PlaceholderScreen` variants for nav items whose destination screens are out of scope for this change (`/audit`, `/settings`, `/extractions`, and any other role-specific items not yet built).
- Gate the topbar role-switcher chips behind `NEXT_PUBLIC_DEMO_MODE=true`.
- Wire dark mode toggle to the existing `useDarkMode()` hook (SP-01).

## Capabilities

### New Capabilities

- `app-shell`: The `AppShell` layout component — sidebar, topbar, main content slot. Consumed by all authenticated screens.
- `nav-config`: Role-specific navigation configuration (`navFor` function, `NavItem` type, `screenTitles` map). Centralises routing metadata so every screen spec can reference it.
- `auth-layout`: The Next.js `(auth)` route group layout — applies `RequireAuth` and `AppShell` to all nested routes, and migrates existing admin pages into the group.

### Modified Capabilities

- `user-auth`: Add `tenantSlug` and `tenantName` display fields to the sidebar tenant pill. No requirement change — already in `AuthUser.tenantSlug`; just first use.

## Impact

- **Files moved**: `app/admin/` → `app/(auth)/admin/` (all existing tenant and job pages).
- **Files added**: `app/(auth)/layout.tsx`, `src/components/app-shell/`, `src/lib/nav-config.ts`.
- **Existing `app/admin/layout.tsx`**: Replaced by the new `(auth)` group layout; role-guard logic moves there.
- **`src/app/dashboard/page.tsx`**: Moves into `(auth)/dashboard/page.tsx` so the shell wraps it.
- **No API changes** — shell is purely frontend.
- **Dependency**: `useDarkMode` hook from SP-01 must exist (confirmed present).

## Open Questions

- None — role-switcher gate (`NEXT_PUBLIC_DEMO_MODE`) and route migration strategy confirmed before spec creation.
