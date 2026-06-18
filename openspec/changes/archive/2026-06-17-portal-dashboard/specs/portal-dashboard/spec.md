## ADDED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, and a side panel titled "Platform health"

#### Scenario: tenant_admin data shape

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training), `pTitle: "Pipeline activity"` with 4 activity rows, and a side panel titled "Active model"

#### Scenario: annotator data shape

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Assigned tasks, Spans confirmed, Suggestions, Completion %), `pTitle: "My tasks"` with 4 task rows, and a side panel titled "Dataset readiness"

#### Scenario: business_user data shape

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Docs extracted, Entities found, Avg confidence, Auto-cleared %), `pTitle: "Recent extractions"` with 4 extraction rows, and a side panel titled "Active model"

#### Scenario: partial service failure degrades gracefully

- **GIVEN** the training service is unavailable when the dashboard is fetched
- **WHEN** the dashboard renders
- **THEN** stat cards whose values depend on the training service show `—` instead of a number
- **AND** stat cards that depend only on available services show their real values
- **AND** no full-page error screen is shown

---

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from whichever downstream services are available. The response SHALL include a top-level `sources` object mapping each service name (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`) to `true` (data retrieved) or `false` (service unavailable or not applicable for this role).

For MVP, only the `tenants` source is wired for `system_admin` (using the existing admin DB query); all other sources return `null` values with `sources.<name>: false`. The endpoint structure SHALL be stable so that wiring additional sources in later SPs requires only adding query logic, not changing the response shape.

#### Scenario: system_admin summary returns tenant count from DB

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response includes the real tenant count in `stats[0].value`
- **AND** `sources.tenants` is `true`

#### Scenario: unauthenticated request rejected

- **GIVEN** the request carries no valid JWT
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Hero Section

The dashboard page SHALL render a hero section at the top that displays the `kicker` (small caps label), `title` (large heading), and `line` (supporting sentence). In **Editorial** layout the hero SHALL use large typographic treatment (title font-size ≥ 28px, Hanken Grotesk 700). In **Command** layout the hero SHALL use a compact single-line treatment (font-size ≤ 18px) that conserves vertical space. The layout preference SHALL be toggled by a `SegmentControl` with options `["Editorial", "Command"]` and persisted to `localStorage` under the key `"portal-layout"`.

#### Scenario: editorial layout renders large hero

- **GIVEN** the layout preference is "Editorial" (default)
- **WHEN** the dashboard page renders
- **THEN** the kicker, title, and line are displayed in large typographic layout
- **AND** the SegmentControl shows "Editorial" as the active option

#### Scenario: command layout renders compact hero

- **GIVEN** the layout preference is "Command"
- **WHEN** the dashboard page renders
- **THEN** the hero collapses to a single compact line with kicker + title inline
- **AND** the line description is hidden

#### Scenario: layout toggle persists across navigation

- **GIVEN** the user switches to "Command" layout
- **WHEN** they navigate away and return to the dashboard
- **THEN** "Command" layout is still active (read from `localStorage`)

#### Scenario: layout toggle does not re-fetch data

- **GIVEN** data has already loaded
- **WHEN** the user toggles the layout
- **THEN** no new network request is made
- **AND** the stat and panel data remain unchanged

---

### Requirement: Stat Card Strip

The dashboard page SHALL render exactly 4 `StatCard` components in a 4-column horizontal strip below the hero. Each card SHALL display: `value` + `unit` (primary figure), `label` (card title), `sub` (context line), `delta` (change indicator), and a directional icon (`up` = green arrow, `warn` = amber dot, neither = neutral). While data is loading the stat cards SHALL display skeleton shimmer placeholders. A null `value` SHALL render as `—`.

#### Scenario: stat cards render with live values

- **GIVEN** the dashboard summary has loaded successfully
- **WHEN** the stat strip renders
- **THEN** 4 cards are visible, each showing the correct value, unit, label, sub, and delta for the user's role

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

The dashboard page SHALL render a primary activity panel displaying `pTitle` and `pMeta` as the panel header, followed by a list of exactly 4 `ActivityRow` items. Each row SHALL show: a coloured status `tag` pill, `title` (primary text), `sub` (secondary text). Each row SHALL be clickable and navigate to the screen identified by `row.go` (mapped via `navFor` hrefs — `"training"` → `/training-jobs`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/models`).

#### Scenario: activity row navigates on click

- **GIVEN** a `system_admin` activity row has `go: "training"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/training-jobs`

#### Scenario: status tag colours match mockup

- **GIVEN** a row has `tk: "pending_approval"`
- **WHEN** the row renders
- **THEN** the tag pill uses the amber/warn colour
- **AND** a row with `tk: "completed"` uses the green/good colour

---

### Requirement: Secondary Metrics Panel

The dashboard page SHALL render a secondary panel to the right of the activity panel (two-column grid on desktop). The panel SHALL display: `sideTop` + `sideMeta` as the header, `big` + `bigUnit` as the primary metric, a horizontal progress bar filled to `bar` percent using the brand primary colour, three `sideMetrics` rows (`k` label + `v` value in JetBrains Mono), a `sideBot` sub-header, and a mini bar chart of `sideRows` where each row shows a colour-coded bar scaled to `pct` and a label + value.

#### Scenario: progress bar fills to correct percentage

- **GIVEN** `bar: 62` in the dashboard data
- **WHEN** the secondary panel renders
- **THEN** the progress bar is filled to 62% of its container width

#### Scenario: sideRows mini bars render correct colours

- **GIVEN** `sideRows[0].c` is `"oklch(0.64 0.15 25)"`
- **WHEN** the mini bar renders
- **THEN** the bar background colour matches the specified CSS colour string

---

### Requirement: Data Freshness

The dashboard SHALL use TanStack Query (`@tanstack/react-query`) to fetch from `GET /api/v1/dashboard/summary`. The query SHALL be configured with `refetchInterval: 30_000` (30 seconds) and `staleTime: 15_000` (15 seconds). `QueryClientProvider` SHALL be added to `app/layout.tsx` wrapping `AuthProvider` and `ToastProvider`.

#### Scenario: data refetches every 30 seconds

- **GIVEN** the dashboard is open and data has loaded
- **WHEN** 30 seconds elapse
- **THEN** the query is automatically re-executed in the background
- **AND** the UI does not flash or reset during the background refresh

#### Scenario: QueryClientProvider wraps the app

- **GIVEN** any page in the portal is rendered
- **WHEN** a component calls `useQueryClient()`
- **THEN** it receives the shared `QueryClient` instance without error
