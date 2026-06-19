## MODIFIED Requirements

### Requirement: Sidebar Layout

The system SHALL render a sticky 248 px sidebar (`position: sticky; top: 0; height: 100vh`) containing, from top to bottom: a logo block, a tenant switcher pill, a scrollable role-specific nav section, and a user strip pinned to the bottom.

**Logo block**: orange rounded square with "n" glyph + "nerplatform" wordmark in Hanken Grotesk.

**Tenant pill**: displays `tenantInitials` (first letter of tenant name, uppercased), `tenantName`, and `tenantSlug` in JetBrains Mono. The pill SHALL be display-only (no click handler that navigates or opens a modal — hover border highlight only).

**Nav section** (`flex: 1; overflow: auto`): renders `navFor(user.role)` as `<button>` elements. Active item (pathname starts with `item.href`) SHALL have a distinct visual treatment matching the mockup's primary-colour highlight. Badge counts render as pill chips in JetBrains Mono when present.

**User strip** (pinned bottom, border-top): avatar gradient square showing `userInitials`, email (truncated), role label in JetBrains Mono, and a `⋮` (vertical ellipsis) trigger button. Clicking the trigger SHALL toggle a floating action menu positioned upward with a 150ms fade-in/out opacity transition. The menu SHALL contain two items: **Settings** (navigates to `/settings`) and **Logout** (calls `useAuth().logout()` then redirects to `/login`). Clicking outside the menu or pressing Escape SHALL close it.

#### Scenario: sidebar renders correct nav for role

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** the `AppShell` mounts
- **THEN** the sidebar nav contains exactly 3 items: My Work, Annotation, Documents
- **AND** no Settings or Tenants items are visible

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

#### Scenario: floating menu opens and closes on trigger

- **GIVEN** the user strip is rendered in the sidebar
- **WHEN** the user clicks the `⋮` trigger button
- **THEN** a floating menu appears above the trigger with a 150ms fade-in transition
- **AND** the menu contains a "Settings" item and a "Logout" item

#### Scenario: menu closes on outside click

- **GIVEN** the floating menu is open
- **WHEN** the user clicks anywhere outside the menu or the trigger button
- **THEN** the menu fades out and closes

#### Scenario: menu closes on Escape

- **GIVEN** the floating menu is open
- **WHEN** the user presses the Escape key
- **THEN** the menu fades out and closes

#### Scenario: Settings navigates to /settings

- **GIVEN** the floating menu is open
- **WHEN** the user clicks the "Settings" item
- **THEN** the browser navigates to `/settings`
- **AND** the menu closes

#### Scenario: logout clears session and redirects

- **GIVEN** the menu is open
- **WHEN** the user clicks the "Logout" item
- **THEN** `useAuth().logout()` is called
- **AND** the browser navigates to `/login`
