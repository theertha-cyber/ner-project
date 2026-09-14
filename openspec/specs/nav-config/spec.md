## Purpose

`nav-config` is the single source of truth for the portal's role-based navigation: the
`navFor(role)` function the sidebar renders, and the `SCREEN_TITLES` map the topbar reads
for the active screen's title. Keeping the role → nav mapping in one pure, testable module
means a route only appears for the roles permitted to use it, and the sidebar and topbar
never disagree about what a screen is called.

## Requirements

### Requirement: Role Navigation Matrix

The system SHALL provide a pure function `navFor(role: AuthUser["role"]): NavItem[]` where
`NavItem` is a union of `NavLeaf` (`kind: "link"`, with `id`, `icon`, `label`, `href`,
optional `badge`, optional `children: NavLeaf[]`) and `NavSection` (`kind: "section"`, with
`id`, `label`, `items: NavLeaf[]`). A `NavSection`'s `label` is a non-navigable header. A
`NavLeaf`'s `children` are landing-page sub-screens used for breadcrumb derivation and are
NOT rendered as sidebar rows.

`system_admin` and `business_user` SHALL return a flat list of `NavLeaf` items.
`tenant_admin` and `annotator` SHALL return a tree grouped into sections. A section whose
permitted `items` list is empty SHALL be dropped before render.

The role → nav mapping SHALL be:

| Role | Structure |
|------|-----------|
| `system_admin` | flat: Dashboard `/dashboard`, Tenants `/admin/tenants`, Models & Training `/training-jobs`, Audit Log `/audit` |
| `tenant_admin` | Dashboard `/dashboard`; section **Annotate**: Manual `/annotate/manual`, Automated `/annotate/automated`, Import `/annotate/import`; section **Setup**: Uploaded Documents `/documents`, Entity Types `/entity-types`; Models & Training `/training-jobs`; section **Admin**: Create User `/users`, Widget Keys `/widget-keys`, Chat `/chat` |
| `annotator` | Dashboard `/dashboard`; section **Annotate**: Manual `/annotate/manual`, Import `/annotate/import` |
| `business_user` | flat: Dashboard `/dashboard`, Documents `/documents`, Extractions `/extractions`, Chat `/chat` |

`Manual` SHALL carry child `Workspace /annotation`. `Automated` SHALL carry children for four
routes: the three numbered pipeline steps `/annotate/automated/schema`,
`/annotate/automated/prelabel`, `/annotate/automated/prelabel?tab=review`, and a fourth,
un-numbered `Retraining` route `/annotate/automated/retrain` that is not part of that pipeline —
its label carries no step-number prefix, unlike the three pipeline steps' labels.
`Import` SHALL carry child `Imported Files /imported-documents`.

Settings is not a nav item for any role.

#### Scenario: system_admin nav

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `navFor("system_admin")` is called
- **THEN** it returns a flat list of 4 `NavLeaf` items and no `NavSection`: Dashboard, Tenants, Models & Training, Audit Log
- **AND** Settings is not in the returned items

#### Scenario: tenant_admin nav

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `navFor("tenant_admin")` is called
- **THEN** the returned items include sections labelled `Annotate`, `Setup`, and `Admin` in that order
- **AND** the `Annotate` section's links are `/annotate/manual`, `/annotate/automated`, `/annotate/import`
- **AND** Settings is not in the returned items

#### Scenario: annotator nav

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `navFor("annotator")` is called
- **THEN** the flattened links include `/annotate/manual` and `/annotate/import`
- **AND** the flattened links do NOT include `/annotate/automated`
- **AND** Settings is not in the returned items

#### Scenario: business_user nav

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `navFor("business_user")` is called
- **THEN** it returns a flat list of 4 `NavLeaf` items and no `NavSection`: Dashboard, Documents, Extractions, Chat
- **AND** Settings is not in the returned items

#### Scenario: a section with no permitted links is dropped

- **GIVEN** a role whose `Setup` and `Admin` sections have zero permitted links
- **WHEN** its nav tree is rendered
- **THEN** no `Setup` or `Admin` header SHALL appear

#### Scenario: Manual no longer carries a Review Queue child

- **GIVEN** the authenticated user has role `tenant_admin` or `annotator`
- **WHEN** `navFor(role)` is called and the `Manual` leaf is inspected
- **THEN** its `children` SHALL be exactly `[Workspace /annotation]`

#### Scenario: Automated's Retraining child carries no step-number prefix

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `navFor("tenant_admin")` is called and the `Automated` leaf's children are inspected
- **THEN** the child whose `href` is `/annotate/automated/retrain` SHALL have label `Retraining`
- **AND** its label SHALL NOT begin with a step number, unlike its three sibling children

### Requirement: Screen Title Map

The system SHALL provide a `SCREEN_TITLES` map from a screen key to `[title, path]`, a
`resolveScreenTitle(pathname)` longest-prefix matcher, and a `crumbsFor(navItems, pathname)`
function that derives a breadcrumb trail (`section → landing → screen`) by walking a role's
nav tree, falling back to `SCREEN_TITLES` for routes not in the tree. The map SHALL include
keys for `/annotate/manual`, `/annotate/automated`, `/annotate/automated/schema`,
`/annotate/automated/prelabel`, `/annotate/automated/retrain`, and `/annotate/import`, and
SHALL retain keys for every legacy route reached via a landing tab.

#### Scenario: known screen lookup

- **GIVEN** the `SCREEN_TITLES` map is imported
- **WHEN** the key `"tenants"` is accessed
- **THEN** it returns `["Tenants", "/admin/tenants"]`
- **AND** keys exist for `/annotate/manual`, `/annotate/automated`, and `/annotate/import`

#### Scenario: unknown screen fallback

- **GIVEN** the active pathname does not match any `SCREEN_TITLES` key and is not in the nav tree
- **WHEN** the topbar resolves the title via `resolveScreenTitle`
- **THEN** it falls back to `["Dashboard", "/dashboard"]`

#### Scenario: breadcrumb for a nested workspace route

- **GIVEN** the active pathname is `/annotation` and the role is `tenant_admin`
- **WHEN** `crumbsFor(navFor("tenant_admin"), "/annotation")` is called
- **THEN** it returns a trail `["Annotate", "Manual", "Workspace"]`

#### Scenario: breadcrumb for an automated step route

- **GIVEN** the active pathname is `/annotate/automated/schema`
- **WHEN** the breadcrumb is derived for `tenant_admin`
- **THEN** the trail ends with the step's label under `Annotate › Automated`

#### Scenario: breadcrumb falls back to the title map for an off-tree route

- **GIVEN** the active pathname is `/settings`
- **WHEN** the breadcrumb is derived
- **THEN** it returns `["Settings"]`

### Requirement: Method Landing Routes and Legacy Redirects

The portal SHALL provide landing pages at `/annotate/manual`, `/annotate/automated`, and
`/annotate/import`, and step pages at `/annotate/automated/schema`,
`/annotate/automated/prelabel`, and `/annotate/automated/retrain` rendered under a
persistent stepper. `/annotate/automated/*` SHALL be gated to `tenant_admin`. The legacy
routes `/schema-proposals`, `/prelabel-batches`, and `/retraining` SHALL redirect to the
corresponding step route. No pre-existing route SHALL be removed.

#### Scenario: legacy schema-proposals route redirects

- **GIVEN** an authenticated Tenant Admin navigates to `/schema-proposals`
- **WHEN** the route resolves
- **THEN** the browser SHALL end at `/annotate/automated/schema`

#### Scenario: automated step routes are tenant-admin only

- **GIVEN** an authenticated `annotator` navigates to `/annotate/automated/prelabel`
- **WHEN** the route resolves
- **THEN** the annotator SHALL be redirected away from the automated workflow

#### Scenario: the annotation workspace route is unchanged

- **GIVEN** an authenticated user navigates to `/annotation`
- **WHEN** the route resolves
- **THEN** the three-pane annotation workspace SHALL render as before
