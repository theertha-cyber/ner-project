## ADDED Requirements

### Requirement: Authenticated Route Group Layout

The system SHALL implement a Next.js App Router route group at `app/(auth)/` with a `layout.tsx` that wraps all nested routes in `<RequireAuth><AppShell>{children}</AppShell></RequireAuth>`. Unauthenticated users who access any `(auth)` route SHALL be redirected to `/login` by `RequireAuth`.

The `(auth)` group SHALL NOT appear in the URL. Existing URLs (`/admin/tenants`, `/dashboard`, etc.) SHALL remain unchanged after the file migration.

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

### Requirement: Admin Sub-Layout Role Guard

The system SHALL implement `app/(auth)/admin/layout.tsx` that wraps admin routes with `<RequireAuth roles={["system_admin"]}>`. Users with any other role who navigate to `/admin/*` SHALL be redirected to `/dashboard`.

#### Scenario: non-admin role blocked from /admin/*

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** they navigate to `/admin/tenants`
- **THEN** they are redirected to `/dashboard`
- **AND** no admin content is rendered

#### Scenario: system_admin accesses admin route

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** they navigate to `/admin/tenants`
- **THEN** the Tenants page renders without redirect
