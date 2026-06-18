## ADDED Requirements

### Requirement: Sidebar Layout

The system SHALL render a sticky 248 px sidebar (`position: sticky; top: 0; height: 100vh`) containing, from top to bottom: a logo block, a tenant switcher pill, a scrollable role-specific nav section, and a user strip pinned to the bottom.

**Logo block**: orange rounded square with "n" glyph + "nerplatform" wordmark in Hanken Grotesk.

**Tenant pill**: displays `tenantInitials` (first letter of tenant name, uppercased), `tenantName`, and `tenantSlug` in JetBrains Mono. The pill SHALL be display-only (no click handler that navigates or opens a modal — hover border highlight only).

**Nav section** (`flex: 1; overflow: auto`): renders `navFor(user.role)` as `<button>` elements. Active item (pathname starts with `item.href`) SHALL have a distinct visual treatment matching the mockup's primary-colour highlight. Badge counts render as pill chips in JetBrains Mono when present.

**User strip** (pinned bottom, border-top): avatar gradient square showing `userInitials`, email (truncated), role label in JetBrains Mono, and a logout button (⎋ icon). Clicking logout calls `useAuth().logout()` then redirects to `/login`.

#### Scenario: sidebar renders correct nav for role

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** the `AppShell` mounts
- **THEN** the sidebar nav contains exactly 4 items: My Work, Annotation, Documents, Settings
- **AND** no Tenants or Training Queue items are visible

#### Scenario: active nav item is highlighted

- **GIVEN** the current pathname is `/admin/tenants/new`
- **WHEN** the sidebar renders for a `system_admin` user
- **THEN** the "Tenants" nav item has the active highlight style
- **AND** no other nav item has the active highlight

#### Scenario: badge renders when present

- **GIVEN** the nav item for "Annotation" has `badge: 4`
- **WHEN** the sidebar renders for an `annotator` user
- **THEN** a badge chip displaying "4" appears next to the Annotation label

#### Scenario: tenant pill shows correct values

- **GIVEN** `AuthUser.tenantSlug = "acme"` and `AuthUser.tenantName` derived from context
- **WHEN** the sidebar renders
- **THEN** the tenant pill shows the first letter initial, the tenant name, and the slug in JetBrains Mono

#### Scenario: logout clears session and redirects

- **GIVEN** the user is authenticated
- **WHEN** they click the logout button (⎋) in the user strip
- **THEN** `useAuth().logout()` is called
- **AND** the browser navigates to `/login`

### Requirement: Topbar Layout

The system SHALL render a 62 px fixed-height topbar (`border-bottom; z-index: 50`) containing: screen title + path, a flex spacer, a search placeholder, an optional role-switcher, a dark mode toggle, and a user avatar.

**Screen title + path**: title in Hanken Grotesk 700, path in JetBrains Mono 11 px, both derived from `SCREEN_TITLES` keyed on the current active screen id (resolved from `usePathname()`).

**Search placeholder**: a non-interactive visual element showing "⌕ search · ⌘K" in JetBrains Mono. SHALL NOT open any dialog.

**Role-switcher**: four chips (SA / TA / AN / BU) rendered only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` (evaluated inline). Clicking a chip calls a `setDemoRole` handler that replaces `AuthUser.role` in context for UI demonstration purposes only (does not re-authenticate).

**Dark mode toggle**: a 36×36 button that calls `useDarkMode().toggle()`. Icon shows ☀ in dark mode and ☽ in light mode.

**Avatar**: 36×36 gradient square (primary → primary-2) showing `userInitials`.

#### Scenario: screen title matches pathname

- **GIVEN** the current pathname is `/admin/tenants`
- **WHEN** the topbar renders
- **THEN** the title reads "Tenants" and the path reads "/admin/tenants"

#### Scenario: role-switcher hidden in production mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE` is not `"true"`
- **WHEN** the topbar renders
- **THEN** no SA / TA / AN / BU chips are visible

#### Scenario: role-switcher visible in demo mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE === "true"`
- **WHEN** the topbar renders
- **THEN** four chips (SA, TA, AN, BU) are visible in the topbar

#### Scenario: dark mode toggle switches theme

- **GIVEN** the current theme is light
- **WHEN** the user clicks the dark mode toggle
- **THEN** `useDarkMode().toggle()` is called
- **AND** the `dark` class is added to `document.documentElement`

#### Scenario: search placeholder is non-interactive

- **GIVEN** the topbar is rendered
- **WHEN** the user clicks the search area
- **THEN** no dialog, modal, or command palette opens

### Requirement: Placeholder Screens

The system SHALL render a `PlaceholderScreen` component for every nav-linked route that does not yet have an implemented screen. The placeholder SHALL display the screen name prominently and a "Coming soon" sub-label. It SHALL NOT render an empty page or throw an error.

Placeholder routes (at minimum): `/annotation`, `/training-jobs`, `/models`, `/documents`, `/entity-types`, `/users`, `/extractions`, `/audit`, `/settings`.

#### Scenario: placeholder renders screen name

- **GIVEN** the user navigates to `/extractions`
- **WHEN** the page renders within the `(auth)` layout
- **THEN** the screen displays "Extractions" and a "Coming soon" indicator
- **AND** the sidebar and topbar are still visible

#### Scenario: placeholder does not crash on unknown role

- **GIVEN** any authenticated user navigates to a placeholder route
- **WHEN** the page renders
- **THEN** no error boundary is triggered

### Requirement: Authenticated Route Group Layout

The system SHALL implement a Next.js App Router route group at `app/(auth)/` with a `layout.tsx` that wraps all nested routes in `<RequireAuth><AppShell>{children}</AppShell></RequireAuth>`. Unauthenticated users who access any `(auth)` route SHALL be redirected to `/login` by `RequireAuth`.

The `(auth)` group SHALL NOT appear in the URL. Existing URLs (`/admin/tenants`, `/dashboard`, etc.) SHALL remain unchanged.

**Change from SP-03:** The `DashboardRouter` redirect that sent `system_admin` users from `/dashboard` to `/admin` is removed. All roles, including `system_admin`, now land on the dashboard page at `/dashboard`. The Tenants page remains accessible at `/admin/tenants` via the sidebar.

#### Scenario: unauthenticated access redirects to login

- **GIVEN** a user is not authenticated (no valid session)
- **WHEN** they navigate directly to `/admin/tenants`
- **THEN** they are redirected to `/login`
- **AND** the sidebar and topbar are NOT rendered

#### Scenario: authenticated access renders shell

- **GIVEN** the user is authenticated
- **WHEN** they navigate to `/dashboard`
- **THEN** the sidebar and topbar render around the page content
- **AND** the URL remains `/dashboard` (no `(auth)` prefix)

#### Scenario: existing admin URLs unchanged

- **GIVEN** existing bookmarks point to `/admin/tenants`
- **WHEN** the user (authenticated as `system_admin`) navigates to that URL
- **THEN** the Tenants page renders within the shell
- **AND** no 404 occurs

#### Scenario: system_admin lands on dashboard (not redirected to /admin)

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** they navigate to `/dashboard`
- **THEN** the dashboard page renders (not redirected to `/admin`)
- **AND** the dashboard shows the system_admin hero with "Platform control plane" kicker
