## MODIFIED Requirements

### Requirement: Sidebar Layout

The system SHALL render a sticky 248 px sidebar (`position: sticky; top: 0; height: 100vh`) containing, from top to bottom: a logo block, a tenant switcher pill, a scrollable role-specific nav section, and a user strip pinned to the bottom.

**Logo block**: orange rounded square with "n" glyph + "nerplatform" wordmark in Hanken Grotesk.

**Tenant pill**: displays `tenantInitials` (first letter of tenant name, uppercased), `tenantName`, and `tenantSlug` in JetBrains Mono, and a `▾` caret on the right edge. The pill SHALL be display-only (no click handler that navigates or opens a modal — hover border highlight only).

**Nav section** (`flex: 1; overflow: auto`): renders `navFor(user.role)` as `<button>` elements. Active item (pathname starts with `item.href`) SHALL have a distinct visual treatment matching the mockup's primary-colour highlight. Badge counts render as pill chips in JetBrains Mono when present.

**User strip** (pinned bottom, border-top): avatar gradient square showing `userInitials`, email (truncated), role label in JetBrains Mono, and a `▾` chevron trigger button. The trigger SHALL be a full-width button element with state-driven border colour and background. Clicking the trigger SHALL toggle a floating action menu positioned upward (`bottom: 62px`) with a `menuPop .18s cubic-bezier(.16,1,.3,1)` spring animation (`transform-origin: bottom center`). The open/closed state of the chevron SHALL be indicated by rotating it 180° (`transform: rotate(180deg)` when open). When the menu is open, a `position:fixed; inset:0; z-index:60` transparent backdrop div SHALL be rendered beneath the menu panel (`z-index:61`); clicking the backdrop SHALL close the menu. Pressing Escape SHALL also close the menu. The menu SHALL contain two items: **Settings** (⚙ icon, navigates to `/settings`) and **Logout** (⎋ icon, calls `useAuth().logout()` then redirects to `/login`).

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

#### Scenario: tenant pill shows correct values with caret

- **GIVEN** `AuthUser.tenantSlug = "acme"` and `AuthUser.tenantName` derived from context
- **WHEN** the sidebar renders
- **THEN** the tenant pill shows the first letter initial, the tenant name, the slug in JetBrains Mono, and a `▾` caret

#### Scenario: user menu opens with spring animation

- **GIVEN** the user strip is rendered in the sidebar
- **WHEN** the user clicks the chevron trigger button
- **THEN** a floating menu appears above the trigger with a `menuPop` spring animation
- **AND** the chevron rotates 180° to indicate the open state
- **AND** a full-viewport backdrop overlay is rendered beneath the menu

#### Scenario: menu closes on backdrop click

- **GIVEN** the floating menu is open
- **WHEN** the user clicks anywhere on the backdrop overlay outside the menu
- **THEN** the menu closes
- **AND** the chevron rotates back to 0°

#### Scenario: menu closes on Escape

- **GIVEN** the floating menu is open
- **WHEN** the user presses the Escape key
- **THEN** the menu closes

#### Scenario: Settings navigates to /settings

- **GIVEN** the floating menu is open
- **WHEN** the user clicks the "Settings" item
- **THEN** the browser navigates to `/settings`
- **AND** the menu closes

#### Scenario: logout clears session and redirects

- **GIVEN** the menu is open
- **WHEN** the user clicks the "Logout" item (⎋ icon)
- **THEN** `useAuth().logout()` is called
- **AND** the browser navigates to `/login`

---

### Requirement: Topbar Layout

The system SHALL render a 62 px fixed-height topbar (`border-bottom; z-index: 50; position: sticky; top: 0`) containing: screen title + path, a flex spacer, a search placeholder, an optional role-switcher, a dark mode toggle, and a user avatar. The topbar SHALL remain visible at the top of the viewport at all times, regardless of how far the user scrolls within the main content area.

**Screen title + path**: title in Hanken Grotesk 700, path in JetBrains Mono 11 px, both derived from `SCREEN_TITLES` keyed on the current active screen id (resolved from `usePathname()`).

**Search placeholder**: a non-interactive visual element showing "⌕ search · ⌘K" in JetBrains Mono. SHALL NOT open any dialog.

**Role-switcher**: rendered only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` (evaluated inline). The pill container SHALL begin with a static `AS` label chip (JetBrains Mono 10px, `var(--ink-3)` colour) followed by four role chips (SA / TA / AN / BU). Clicking a chip calls a `setDemoRole` handler that replaces `AuthUser.role` in context for UI demonstration purposes only (does not re-authenticate).

**Dark mode toggle**: a 36×36 button that calls `useDarkMode().toggle()`. Icon shows ☀ in dark mode and ☽ in light mode.

**Avatar**: 36×36 gradient square (primary → primary-2) showing `userInitials`.

#### Scenario: Topbar remains visible after scrolling

- **GIVEN** a page with content taller than the viewport (e.g. a long documents list)
- **WHEN** the user scrolls down past the height of the topbar
- **THEN** the topbar SHALL remain visible at the top of the viewport
- **AND** the topbar SHALL NOT scroll out of view

#### Scenario: screen title matches pathname

- **GIVEN** the current pathname is `/admin/tenants`
- **WHEN** the topbar renders
- **THEN** the title reads "Tenants" and the path reads "/admin/tenants"

#### Scenario: role-switcher hidden in production mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE` is not `"true"`
- **WHEN** the topbar renders
- **THEN** no SA / TA / AN / BU chips and no `AS` label are visible

#### Scenario: role-switcher shows AS label in demo mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE === "true"`
- **WHEN** the topbar renders
- **THEN** the `AS` label chip is visible before the four role chips (SA, TA, AN, BU)
- **AND** `AS` is rendered in JetBrains Mono 10px with `var(--ink-3)` colour

#### Scenario: dark mode toggle switches theme

- **GIVEN** the current theme is light
- **WHEN** the user clicks the dark mode toggle
- **THEN** `useDarkMode().toggle()` is called
- **AND** the `dark` class is added to `document.documentElement`

#### Scenario: search placeholder is non-interactive

- **GIVEN** the topbar is rendered
- **WHEN** the user clicks the search area
- **THEN** no dialog, modal, or command palette opens
