## ADDED Requirements

### Requirement: Widget Keys Screen

The system SHALL render a Widget Keys screen at the route `/widget-keys`, accessible only to users with role `tenant_admin`. The screen SHALL be added to `navFor("tenant_admin")` in `nav-config.ts` and to `SCREEN_TITLES` for topbar display.

**Screen layout**: full-width content area with `padding: 28px 32px 60px; max-width: 1100px; margin: 0 auto` and `animate-fade-up` entrance animation. Contains a page header, a toolbar row, and a keys table.

**Page header**: A breadcrumb label in JetBrains Mono 11px `var(--ink-3)` showing the API path (`/api/v1/tenants/{slug}/widget-keys · port 8006`) above the page title "Widget Keys" in Hanken Grotesk weight-800 34px and a subtitle describing the purpose of embeddable widget keys.

**Keys table**: Displays a list of widget keys for the tenant. Each row SHALL show: key name, key prefix (first 8 chars + `…`), creation date in JetBrains Mono, status badge (`active` / `revoked`), and a copy-to-clipboard button. The table header row SHALL be styled consistently with the rest of the portal's data tables.

**Empty state**: If no keys exist OR the API endpoint returns a non-2xx response, the screen SHALL display an empty-state message indicating no widget keys are configured, with a placeholder "Create Key" button that is non-functional in this version (visually present, no click handler beyond a `console.log`).

**Data source**: The screen SHALL call `GET /api/v1/tenants/{slug}/widget-keys` via the authenticated gateway proxy. If the endpoint is unavailable (network error or 4xx/5xx), the screen SHALL silently fall back to the empty state WITHOUT crashing or displaying a raw error.

**No mutation in this version**: Key creation and revocation are out of scope for this change. The "Create Key" and any "Revoke" buttons SHALL be visually present but non-functional placeholders.

#### Scenario: widget-keys nav item appears for tenant_admin

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** the sidebar renders
- **THEN** a "Widget Keys" nav item is visible in the sidebar
- **AND** clicking it navigates to `/widget-keys`

#### Scenario: widget-keys nav item hidden for other roles

- **GIVEN** the authenticated user has role `annotator`, `business_user`, or `system_admin`
- **WHEN** the sidebar renders
- **THEN** no "Widget Keys" item is visible

#### Scenario: topbar shows correct title for /widget-keys

- **GIVEN** the user navigates to `/widget-keys`
- **WHEN** the topbar renders
- **THEN** the title reads "Widget Keys" and the path reads "/widget-keys"

#### Scenario: screen renders API path breadcrumb

- **GIVEN** the user is on the `/widget-keys` screen
- **WHEN** the page renders
- **THEN** the breadcrumb label `/api/v1/tenants/{slug}/widget-keys · port 8006` is visible above the page title

#### Scenario: keys table renders when API returns data

- **GIVEN** `GET /api/v1/tenants/{slug}/widget-keys` returns a list of keys
- **WHEN** the Widget Keys screen mounts
- **THEN** each key is shown as a row with its name, prefix, creation date, status badge, and copy button

#### Scenario: empty state shown when API returns empty list

- **GIVEN** `GET /api/v1/tenants/{slug}/widget-keys` returns an empty array
- **WHEN** the Widget Keys screen mounts
- **THEN** an empty-state message is displayed
- **AND** a placeholder "Create Key" button is visible

#### Scenario: empty state shown on API error

- **GIVEN** `GET /api/v1/tenants/{slug}/widget-keys` returns a 5xx error
- **WHEN** the Widget Keys screen mounts
- **THEN** the empty-state message is displayed without a raw error or crash
- **AND** no error boundary is triggered

#### Scenario: copy button copies key prefix to clipboard

- **GIVEN** a widget key row is rendered in the table
- **WHEN** the user clicks the copy button on that row
- **THEN** the key's full value (or prefix) is written to the clipboard via `navigator.clipboard.writeText`
