## MODIFIED Requirements

### Requirement: Sidebar Layout

The system SHALL render a sticky 248 px sidebar (`position: sticky; top: 0; height: 100vh`) containing, from top to bottom: a logo block, a tenant switcher pill, a scrollable role-specific nav section, and a user strip pinned to the bottom. The sidebar background SHALL be `var(--surface-2)` (solid, no glass or backdrop-filter effect).

**Logo block**: orange rounded square (`width: 30px; height: 30px; border-radius: 8px`) with "n" glyph (`font-weight: 800; font-size: 17px`) in Hanken Grotesk with white text, followed by "nerplatform" wordmark in Hanken Grotesk (`font-weight: 700; font-size: 16px; letter-spacing: -0.02em`).

**Tenant pill**: a container with `background: var(--surface-3); border: 1px solid var(--line); border-radius: 12px; padding: 9px 11px; margin: 4px 12px 14px`. Displays a 26×26px avatar square with `background: var(--primary-soft); color: var(--primary-2)` showing `tenantInitials`, followed by `tenantName` (12.5px, weight-600) and `tenantSlug` in JetBrains Mono (10px, `var(--ink-3)`), and a `▾` caret on the right edge. The pill SHALL be display-only (no navigation or modal on click — hover `border-color: var(--primary-line)` only).

**Nav section** (`flex: 1; overflow: auto; padding: 4px 12px`): renders `navFor(user.role)` as `<button>` elements with `padding: 9px 11px; border-radius: 10px; font-family: Inter; font-size: 13.5px; margin-bottom: 2px`. Active item (pathname starts with `item.href`) SHALL have background and colour treatment driven by the mockup's primary-colour highlight variables. Badge counts render as pill chips in JetBrains Mono (10px, weight-600) when present.

**User strip** (pinned bottom, `border-top: 1px solid var(--line)`): contains a full-width trigger button with `border-radius: 11px; padding: 7px 8px`. The button shows: a 32×32px gradient avatar square (`background: linear-gradient(135deg, var(--primary), var(--primary-2)); border-radius: 9px`) displaying `userInitials` in Hanken Grotesk weight-700, the user email (truncated), the role label in JetBrains Mono, and a chevron indicator. The chevron `▾` SHALL be rendered inside a framed 24×24px container (`background: var(--surface-2); border: 1px solid var(--line); border-radius: 7px; display: grid; place-items: center; font-size: 9px`) and SHALL rotate 180° (`transform: rotate(180deg)`) when the menu is open. Clicking the trigger SHALL toggle a floating action menu positioned upward (`bottom: 62px; position: absolute`) with a `menuPop .18s cubic-bezier(.16,1,.3,1)` spring animation (`transform-origin: bottom center`). When the menu is open, a `position: fixed; inset: 0; z-index: 60` transparent backdrop div SHALL be rendered beneath the menu panel (`z-index: 61`); clicking the backdrop SHALL close the menu. Pressing Escape SHALL also close the menu. The menu SHALL contain two items: **Settings** (⚙ icon, `color: var(--ink)`, hover `background: var(--surface-3)`, navigates to `/settings`) and **Logout** (⎋ icon, `color: var(--bad)`, hover `background: var(--bad-soft)`, calls `useAuth().logout()` then redirects to `/login`).

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

#### Scenario: tenant pill shows correct values with muted avatar

- **GIVEN** `AuthUser.tenantSlug = "acme"` and the derived tenant name is "Acme"
- **WHEN** the sidebar renders
- **THEN** the tenant pill has a visible `var(--surface-3)` background fill
- **AND** the avatar square uses `var(--primary-soft)` background (not full brand orange)
- **AND** the `▾` caret is visible on the right edge

#### Scenario: user strip chevron is rendered in a framed box

- **GIVEN** the user strip is visible in the sidebar
- **WHEN** the sidebar renders in closed-menu state
- **THEN** the `▾` character is enclosed in a 24×24px bordered container
- **AND** the container has a visible border and background matching `var(--surface-2)` / `var(--line)`

#### Scenario: user menu opens with spring animation

- **GIVEN** the user strip is rendered
- **WHEN** the user clicks the trigger button
- **THEN** a floating menu appears above the trigger with the `menuPop` spring animation
- **AND** the chevron inside the framed box rotates 180°
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

#### Scenario: Logout item has danger colour

- **GIVEN** the floating menu is open
- **WHEN** the menu renders the Logout item
- **THEN** the Logout label uses `var(--bad)` text colour (red/danger)
- **AND** hovering the Logout item applies `var(--bad-soft)` background

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

The system SHALL render a 62 px fixed-height topbar (`border-bottom; z-index: 50; position: sticky; top: 0`) containing, in order: screen title + path, a flex spacer, a search placeholder, an optional role-switcher pill, a dark mode toggle, and a user avatar. The topbar SHALL remain visible at the top of the viewport at all times. The topbar background SHALL be `var(--surface-2)` (solid, no glass or backdrop-filter effect).

**Screen title + path**: displayed side-by-side with `align-items: baseline` and a `gap: 9px`. Title in Hanken Grotesk 700 16px, path in JetBrains Mono 11px `var(--ink-3)`, both derived from `SCREEN_TITLES` keyed on the current pathname.

**Search placeholder**: a non-interactive visual element showing "⌕ search · ⌘K" in JetBrains Mono, styled with `width: 230px; border-radius: 10px; padding: 7px 12px; background: var(--surface-3); border: 1px solid var(--line)`. SHALL NOT open any dialog.

**Role-switcher pill**: rendered only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"`. The ENTIRE pill container (including the `AS` label and four role chips) SHALL be wrapped in a single `<div>` with `background: var(--surface-3); border: 1px solid var(--line); border-radius: 10px; padding: 3px`. The `AS` label SHALL appear first inside the container in JetBrains Mono 10px `var(--ink-3)` with `padding: 0 6px`. The four role chips (SA / TA / AN / BU) SHALL follow. Clicking a chip calls `setDemoRole` replacing `AuthUser.role` in context for demo purposes only.

**Dark mode toggle**: a 36×36 button with `border-radius: 10px` that calls `useDarkMode().toggle()`. Icon shows ☀ in dark mode and ☽ in light mode.

**Avatar**: 36×36 gradient square with `background: linear-gradient(135deg, var(--primary), var(--primary-2)); border-radius: 10px` showing `userInitials` in Hanken Grotesk weight-700.

#### Scenario: Topbar remains visible after scrolling

- **GIVEN** a page with content taller than the viewport
- **WHEN** the user scrolls down past the height of the topbar
- **THEN** the topbar remains visible at the top of the viewport
- **AND** the topbar does NOT scroll out of view

#### Scenario: screen title and path are side-by-side on baseline

- **GIVEN** the current pathname is `/admin/tenants`
- **WHEN** the topbar renders
- **THEN** the title "Tenants" and path "/admin/tenants" are displayed in the same horizontal row with baseline alignment
- **AND** they are NOT stacked vertically

#### Scenario: role-switcher hidden in production mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE` is not `"true"`
- **WHEN** the topbar renders
- **THEN** no role-switcher pill, AS label, or SA/TA/AN/BU chips are visible

#### Scenario: role-switcher wrapped in single bordered pill

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE === "true"`
- **WHEN** the topbar renders
- **THEN** the `AS` label and four role chips (SA, TA, AN, BU) are rendered inside a single container with a visible border and background fill
- **AND** the `AS` label appears before the chips inside the same pill container

#### Scenario: dark mode toggle has 10px border radius

- **GIVEN** the topbar is rendered
- **WHEN** the dark mode toggle button is inspected
- **THEN** its computed `border-radius` is 10px

#### Scenario: avatar has 10px border radius

- **GIVEN** the topbar is rendered
- **WHEN** the user avatar element is inspected
- **THEN** its computed `border-radius` is 10px

#### Scenario: dark mode toggle switches theme

- **GIVEN** the current theme is light
- **WHEN** the user clicks the dark mode toggle
- **THEN** `useDarkMode().toggle()` is called
- **AND** the `dark` class is added to `document.documentElement`

#### Scenario: search placeholder is non-interactive

- **GIVEN** the topbar is rendered
- **WHEN** the user clicks the search area
- **THEN** no dialog, modal, or command palette opens
