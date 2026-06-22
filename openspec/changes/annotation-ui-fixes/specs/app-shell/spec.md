## MODIFIED Requirements

### Requirement: Topbar Layout

The system SHALL render a 62 px fixed-height topbar (`border-bottom; z-index: 50; position: sticky; top: 0`) containing: screen title + path, a flex spacer, a search placeholder, an optional role-switcher, a dark mode toggle, and a user avatar. The topbar SHALL remain visible at the top of the viewport at all times, regardless of how far the user scrolls within the main content area.

**Screen title + path**: title in Hanken Grotesk 700, path in JetBrains Mono 11 px, both derived from `SCREEN_TITLES` keyed on the current active screen id (resolved from `usePathname()`).

**Search placeholder**: a non-interactive visual element showing "⌕ search · ⌘K" in JetBrains Mono. SHALL NOT open any dialog.

**Role-switcher**: four chips (SA / TA / AN / BU) rendered only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"` (evaluated inline). Clicking a chip calls a `setDemoRole` handler that replaces `AuthUser.role` in context for UI demonstration purposes only (does not re-authenticate).

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
