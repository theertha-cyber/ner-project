## Purpose

<!-- TBD: This spec covers the portal dashboard feature, including the summary endpoint, hero section, stat cards, activity panel, secondary metrics panel, and data freshness behaviour. -->

## Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, and a side panel titled "Platform health" with SLA, latency, error rate, and GPU metrics
- **AND** the `sideRows` section contains storage usage by tenant (label, val, pct, colour)

#### Scenario: tenant_admin data shape

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training count), `pTitle: "Pipeline activity"` with 4 activity rows (training run, dataset approval, document processing, model promotion), and a side panel titled "Active model" with eval F1, precision, recall, loss, and quota usage rows (Documents, Storage, Model versions)

#### Scenario: annotator data shape

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Assigned tasks, Spans confirmed, Suggestions, Completion %), `pTitle: "My tasks"` with 4 task rows (showing document name, status, span/suggestion count), and a side panel titled "Dataset readiness" with span progress bar toward 500-span threshold, doc/type/today metrics, and span-by-entity-type breakdown

#### Scenario: business_user data shape

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Docs extracted, Entities found, Avg confidence, Auto-cleared %), `pTitle: "Recent extractions"` with 4 extraction rows (document name, entity count, confidence, processing time), and a side panel titled "Active model" with eval F1, precision, recall, loss, and top extracted fields chart

#### Scenario: partial service failure degrades gracefully

- **GIVEN** the training service is unavailable when the dashboard is fetched
- **WHEN** the dashboard renders
- **THEN** stat cards whose values depend on the training service show `—` instead of a number
- **AND** stat cards that depend only on available services show their real values
- **AND** no full-page error screen is shown

---

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from the tenant's database tables directly (gateway queries tenant schema tables rather than calling downstream services for MVP). The response SHALL include a top-level `sources` object mapping each data domain (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`, `"extraction"`) to `true` (data retrieved) or `false` (query failed or not applicable for this role).

Each role handler SHALL accept the `db` session and `tenant_id` parameters and execute real SQL queries against the tenant's schema. Every query SHALL be wrapped in try/catch with independent error handling — a failed query SHALL set the affected fields to `null`, the corresponding `sources.*` flag to `false`, and SHALL NOT fail the entire request.

#### Scenario: system_admin summary returns real data from wired sources

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response includes the real tenant count in `stats[0].value`
- **AND** `sources.tenants` is `true`
- **AND** training-dependent fields (pending approvals count, avg F1) are fetched from the training service

#### Scenario: tenant_admin summary returns real data from wired sources

- **GIVEN** the caller has role `tenant_admin` and the tenant has documents, annotations, model versions, and training jobs
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the real document count from the tenant's `documents` table
- **AND** `stats[1].value` SHALL contain the annotation completion percentage
- **AND** `stats[2].value` SHALL contain the promoted model's F1 score
- **AND** `stats[3].value` SHALL contain the training job count

#### Scenario: annotator summary returns real task data

- **GIVEN** the caller has role `annotator` and has assigned annotation tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the count of assigned tasks
- **AND** `stats[1].value` SHALL contain the count of confirmed spans
- **AND** `stats[3].value` SHALL contain the task completion percentage

#### Scenario: business_user summary returns real extraction data

- **GIVEN** the caller has role `business_user` and the tenant has extraction data
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the extracted document count
- **AND** `stats[1].value` SHALL contain the total entity count
- **AND** `stats[2].value` SHALL contain the average confidence score
- **AND** `stats[3].value` SHALL contain the auto-cleared percentage

#### Scenario: sources map includes all data domains

- **GIVEN** the dashboard summary is generated for any role
- **WHEN** the response is inspected
- **THEN** the `sources` object SHALL contain keys for all data domains relevant to that role
- **AND** each key SHALL be `true` if the query succeeded, `false` otherwise

#### Scenario: unauthenticated request rejected

- **GIVEN** the request carries no valid JWT
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response is `401 Unauthorized`

---

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
- **THEN** the dot indicator and tag use the amber/warn colour (`var(--warn-soft)` background, `var(--warn)` text)
- **AND** the tag is positioned to the right of the title/sub text
- **AND** a row with `tk: "completed"` uses the green/good colour (`var(--good-soft)` background, `var(--good)` text)
- **AND** a row with `tk: "running"` shows a pulsing dot animation

---

### Requirement: Secondary Metrics Panel

The dashboard page SHALL render a secondary panel to the right of the activity panel (two-column grid on desktop, 16px gap). The top section SHALL display: `sideTop` title and `sideMeta` label stacked vertically (title above, meta below with 4px and 16px margins respectively), `big` + `bigUnit` as the primary metric, a horizontal progress bar (height 8px) filled to `bar` percent using the brand primary colour, and three `sideMetrics` displayed as an inline flex row (space-between) with each metric showing `k` label and `v` value in JetBrains Mono.

Below the top section, if `sideRows` is non-empty, a bottom section SHALL render showing `sideBot` as the sub-header followed by a mini bar chart where each row shows a colour-coded bar (height 6px) scaled to `pct` and a label + value.

#### Scenario: progress bar fills to correct percentage

- **GIVEN** `bar: 62` in the dashboard data
- **WHEN** the secondary panel renders
- **THEN** the progress bar is filled to 62% of its container width
- **AND** the progress bar height is 8px
- **AND** the `growBar` animation plays from width `0` to `62%` on mount

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

### Requirement: Data Freshness

The dashboard SHALL use TanStack Query (`@tanstack/react-query`) to fetch from `GET /api/v1/dashboard/summary`. The query SHALL be configured with `refetchInterval: 30_000` (30 seconds) and `staleTime: 15_000` (15 seconds). `QueryClientProvider` SHALL be added to `app/layout.tsx` wrapping `AuthProvider` and `ToastProvider`. The query SHALL use `enabled` to only fetch when the user is authenticated.

#### Scenario: data refetches every 30 seconds

- **GIVEN** the dashboard is open and data has loaded
- **WHEN** 30 seconds elapse
- **THEN** the query is automatically re-executed in the background
- **AND** the UI does not flash or reset during the background refresh

#### Scenario: QueryClientProvider wraps the app

- **GIVEN** any page in the portal is rendered
- **WHEN** a component calls `useQueryClient()`
- **THEN** it receives the shared `QueryClient` instance without error
