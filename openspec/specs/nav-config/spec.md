## ADDED Requirements

### Requirement: Role Navigation Matrix

The system SHALL provide a pure function `navFor(role: AuthUser["role"]): NavItem[]` that returns the ordered list of navigation items for each role, matching the mockup's `navFor()` implementation exactly. Each `NavItem` SHALL carry an `id`, `icon` (single character/symbol), `label`, `href` (absolute path), `roles` array, and an optional `badge` count.

The role → nav mapping SHALL be:

| Role | Nav items (in order) |
|------|----------------------|
| `system_admin` | Dashboard `/dashboard`, Tenants `/admin/tenants` (badge 6), Training Queue `/training-jobs` (badge 2), Model Registry `/models`, Audit Log `/audit`, Platform Settings `/settings` |
| `tenant_admin` | Dashboard `/dashboard`, Documents `/documents`, Annotation `/annotation`, Entity Types `/entity-types`, Training Jobs `/training-jobs` (badge 1), Model Registry `/models`, Users `/users`, Settings `/settings` |
| `annotator` | My Work `/dashboard`, Annotation `/annotation` (badge 4), Documents `/documents`, Settings `/settings` |
| `business_user` | Overview `/dashboard`, Documents `/documents`, Extractions `/extractions`, Models `/models`, Settings `/settings` |

#### Scenario: system_admin nav

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `navFor("system_admin")` is called
- **THEN** it returns 6 items in order: Dashboard, Tenants (badge 6), Training Queue (badge 2), Model Registry, Audit Log, Platform Settings

#### Scenario: tenant_admin nav

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `navFor("tenant_admin")` is called
- **THEN** it returns 8 items: Dashboard, Documents, Annotation, Entity Types, Training Jobs (badge 1), Model Registry, Users, Settings

#### Scenario: annotator nav

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `navFor("annotator")` is called
- **THEN** it returns 4 items: My Work, Annotation (badge 4), Documents, Settings

#### Scenario: business_user nav

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `navFor("business_user")` is called
- **THEN** it returns 5 items: Overview, Documents, Extractions, Models, Settings

### Requirement: Screen Title Map

The system SHALL export a `SCREEN_TITLES` record mapping screen id to `[title: string, path: string]` tuples used by the topbar. The map SHALL cover: `dashboard`, `annotation`, `tenants`, `training-jobs`, `models`, `documents`, `entity-types`, `users`, `extractions`, `audit`, `settings`.

#### Scenario: known screen lookup

- **GIVEN** the `SCREEN_TITLES` map is imported
- **WHEN** the key `"tenants"` is accessed
- **THEN** it returns `["Tenants", "/admin/tenants"]`

#### Scenario: unknown screen fallback

- **GIVEN** the active pathname does not match any `SCREEN_TITLES` key
- **WHEN** the topbar resolves the title
- **THEN** it falls back to `["Dashboard", "/dashboard"]`
