## MODIFIED Requirements

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
