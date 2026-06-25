## ADDED Requirements

### Requirement: Hero Variant B (system_admin dark mesh)

The dashboard page SHALL determine a `heroVariant` from the authenticated user's role using a pure `heroVariant(role: UserRole): 'a' | 'b'` helper. `system_admin` resolves to `'b'`; all other roles resolve to `'a'`. The `DashboardHero` component SHALL accept `variant` as a prop and render the appropriate visual treatment.

**Variant A** (roles: `tenant_admin`, `annotator`, `business_user`): renders the hero on a `var(--surface-2)` card background. The kicker, title, and body text use their default ink colours as defined in the existing Hero Section requirement.

**Variant B** (`system_admin`): renders the hero with a dark card background containing two animated mesh gradient orbs — an orange radial (`#c2410c`, `meshDrift 18s ease-in-out infinite alternate`) and a slate radial (`#475569`, `meshDrift 23s ease-in-out infinite alternate-reverse`). All text within Variant B SHALL be white (`#ffffff` or equivalent high-contrast token). The `heroKicker`, `heroTitle`, and `heroLine` content values are role-driven and unchanged from the existing `DashboardData` shape.

The Editorial/Command layout toggle is orthogonal to variant: both Editorial (large typographic) and Command (compact single-line) treatments apply within each variant.

#### Scenario: system_admin hero renders Variant B dark mesh

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** the dashboard page renders
- **THEN** the hero background shows an animated dark mesh gradient with orange and slate orbs
- **AND** all hero text (kicker, title, body) is white
- **AND** the `meshDrift` animation is applied to both gradient orbs

#### Scenario: non-admin roles render Variant A light hero

- **GIVEN** the authenticated user has role `annotator`, `tenant_admin`, or `business_user`
- **WHEN** the dashboard page renders
- **THEN** the hero background uses `var(--surface-2)` (light card)
- **AND** text colours follow the standard ink tokens

#### Scenario: Variant B still respects Editorial/Command layout

- **GIVEN** the authenticated user has role `system_admin` and the layout preference is "Command"
- **WHEN** the dashboard renders
- **THEN** the dark mesh gradient background is present
- **AND** the hero collapses to a compact single-line treatment (kicker + title inline, body hidden)

#### Scenario: heroVariant helper is pure and testable

- **GIVEN** `heroVariant` is called with `role = "system_admin"`
- **WHEN** the function executes
- **THEN** it returns `'b'` without accessing auth context or side effects

- **GIVEN** `heroVariant` is called with any role other than `system_admin`
- **WHEN** the function executes
- **THEN** it returns `'a'`
