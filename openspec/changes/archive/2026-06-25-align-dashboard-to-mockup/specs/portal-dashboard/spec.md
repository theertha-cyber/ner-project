## MODIFIED Requirements

### Requirement: Hero Section

The dashboard page SHALL render a hero section at the top that displays the `kicker` (small caps label), `title` (large heading), and `line` (supporting sentence). The hero SHALL use large typographic treatment: title font-size 38px, Hanken Grotesk weight 800, line-height 1.02. The `kicker` SHALL use 12px JetBrains Mono uppercase with 0.14em letter-spacing. The `line` SHALL use 15px body text, max-width 560px.

A breadcrumb line SHALL be rendered above the hero showing `"DASHBOARD ◦ {roleLabel}"` in 11px JetBrains Mono, with the role label formatted as capitalized words (underscore → space).

The SegmentControl for Editorial/Command layout toggle SHALL NOT be rendered on the dashboard page. The `heroVariant(role)` function SHALL continue to determine Variant A vs B by role. Layout is always "Editorial" (large typographic) — there is no Command layout mode for the hero.

#### Scenario: editorial layout renders large hero

- **GIVEN** the dashboard page loads
- **WHEN** the hero section renders
- **THEN** the kicker, title, and line are displayed in large typographic layout with title at 38px
- **AND** no SegmentControl is visible

#### Scenario: breadcrumb renders above hero

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** the dashboard page renders
- **THEN** a breadcrumb line reading `"DASHBOARD ◦ System Admin"` appears above the hero section

---

### MODIFIED Requirements

### Requirement: Hero Variant B (system_admin dark mesh)

The dashboard page SHALL determine a `heroVariant` from the authenticated user's role using a pure `heroVariant(role: UserRole): 'a' | 'b'` helper. `system_admin` resolves to `'b'`; all other roles resolve to `'a'`. The `DashboardHero` component SHALL accept `variant` as a prop and render the appropriate visual treatment.

**Variant A** (roles: `tenant_admin`, `annotator`, `business_user`): renders the hero on a `var(--surface-2)` card background. The kicker, title, and body text use their default ink colours as defined in the Hero Section requirement.

**Variant B** (`system_admin`): renders the hero with a dark card background (border-radius 24px) containing two animated mesh gradient orbs — an orange radial (`#c2410c`, `meshDrift 18s ease-in-out infinite alternate`) and a slate radial (`#475569`, `meshDrift 23s ease-in-out infinite alternate-reverse`). All text within Variant B SHALL be white (`#ffffff` or equivalent high-contrast token).

There is only one layout mode (Editorial). The layout is not togglable; the hero always renders with the full kicker, title, and line text.

#### Scenario: system_admin hero renders Variant B dark mesh

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** the dashboard page renders
- **THEN** the hero background shows an animated dark mesh gradient with orange and slate orbs, border-radius 24px
- **AND** all hero text (kicker, title, body) is white

#### Scenario: non-admin roles render Variant A light hero

- **GIVEN** the authenticated user has role `annotator`, `tenant_admin`, or `business_user`
- **WHEN** the dashboard page renders
- **THEN** the hero background uses `var(--surface-2)` (light card)
- **AND** text colours follow the standard ink tokens

#### Scenario: heroVariant helper is pure and testable

- **GIVEN** `heroVariant` is called with `role = "system_admin"`
- **WHEN** the function executes
- **THEN** it returns `'b'` without accessing auth context or side effects

- **GIVEN** `heroVariant` is called with any role other than `system_admin`
- **WHEN** the function executes
- **THEN** it returns `'a'`

---

### MODIFIED Requirements

### Requirement: Stat Card Strip

The dashboard page SHALL render exactly 4 `StatCard` components in a 4-column CSS grid (`grid-template-columns: repeat(4, 1fr)`) with 14px gap below the hero. Each card SHALL display: `label` (card title) with `delta` pill inline at the top-right, `value` + `unit` below as the primary figure, `sub` (context line), and a directional delta indicator (`up` = green `#16a34a`, `warn` = amber `#d97706`, neither = neutral). The delta pill SHALL be positioned on the same row as the label, right-aligned.

Cards SHALL have a hover effect that translates the card up by 2px and changes the border-color to `var(--primary-line)`. While data is loading the stat cards SHALL display skeleton shimmer placeholders. A null `value` SHALL render as `—`.

#### Scenario: stat cards render in 4-column grid with inline delta

- **GIVEN** the dashboard summary has loaded successfully
- **WHEN** the stat strip renders
- **THEN** 4 cards are visible in a 4-column grid layout
- **AND** each card shows the label and delta pill on the same row (delta right-aligned)
- **AND** the value, unit, and sub appear below

#### Scenario: stat cards render skeleton while loading

- **GIVEN** the dashboard query is in-flight
- **WHEN** the stat strip renders
- **THEN** 4 skeleton placeholder cards are visible (no spinner, no empty boxes)

#### Scenario: warn direction renders amber indicator

- **GIVEN** a stat item has `dir: "warn"` (e.g., "Pending approvals")
- **WHEN** the card renders
- **THEN** the delta indicator is amber, not green

---

### MODIFIED Requirements

### Requirement: Activity Panel

The dashboard page SHALL render a primary activity panel displaying `pTitle` and `pMeta` as the panel header, followed by a list of exactly 4 `ActivityRow` items. Each row SHALL show: a coloured dot indicator (left side), `title` (primary text), `sub` (secondary text), and a coloured status `tag` pill (right-aligned). The dot indicator SHALL be a small `<div>` with `border-radius: 50%` coloured according to the row's `tk` status key (same colour mapping as the existing tag colours).

Each row SHALL be clickable and navigate to the screen identified by `row.go` (mapped via `navFor` hrefs — `"training"` → `/training-jobs`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/models`).

#### Scenario: activity row navigates on click

- **GIVEN** a `system_admin` activity row has `go: "training"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/training-jobs`

#### Scenario: status dot and tag render correct colours

- **GIVEN** a row has `tk: "pending_approval"`
- **WHEN** the row renders
- **THEN** the dot indicator and tag use the amber/warn colour
- **AND** the tag is positioned to the right of the title/sub text

---

### MODIFIED Requirements

### Requirement: Secondary Metrics Panel

The dashboard page SHALL render a secondary panel to the right of the activity panel (two-column grid on desktop, 16px gap). The top section SHALL display: `sideTop` title and `sideMeta` label stacked vertically (title above, meta below with 4px and 16px margins respectively), `big` + `bigUnit` as the primary metric, a horizontal progress bar (height 8px) filled to `bar` percent using the brand primary colour, and three `sideMetrics` displayed as an inline flex row (space-between) with each metric showing `k` label and `v` value in JetBrains Mono.

Below the top section, if `sideRows` is non-empty, a bottom section SHALL render showing `sideBot` as the sub-header followed by a mini bar chart where each row shows a colour-coded bar (height 6px) scaled to `pct` and a label + value.

#### Scenario: progress bar fills to correct percentage

- **GIVEN** `bar: 62` in the dashboard data
- **WHEN** the secondary panel renders
- **THEN** the progress bar is filled to 62% of its container width
- **AND** the progress bar height is 8px

#### Scenario: sideMetrics render as inline row

- **GIVEN** three sideMetrics are returned in the dashboard data
- **WHEN** the top section renders
- **THEN** the three metrics appear in a single inline flex row with space-between alignment
- **AND** each metric shows its `k` label and `v` value in JetBrains Mono

#### Scenario: sideRows mini bars render correct colours

- **GIVEN** `sideRows[0].c` is `"oklch(0.64 0.15 25)"`
- **WHEN** the mini bar renders
- **THEN** the bar background colour matches the specified CSS colour string

---

## REMOVED Requirements

### Requirement: Hero Section — Command Layout / SegmentControl

The Command layout mode and SegmentControl toggle mechanism are removed. The `useLayoutPreference` hook is no longer used on the dashboard page.

**Reason:** The mockup removes the Editorial/Command layout toggle. Hero layout is determined solely by `heroVariant(role)` (Variant A or B), each of which always renders in the large typographic style. The `useLayoutPreference` hook and `SegmentControl` component are no longer needed on the dashboard page.

**Migration:** Remove the SegmentControl import and JSX from `dashboard/page.tsx`. Remove the `useLayoutPreference` import. The `useLayoutPreference` hook itself remains available for other screens that may need it.
