## MODIFIED Requirements

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

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from whichever downstream services are available. The response SHALL include a top-level `sources` object mapping each service name (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`) to `true` (data retrieved) or `false` (service unavailable or not applicable for this role).

For MVP, all data sources SHALL be wired according to the caller's role: system_admin queries tenants and training services; tenant_admin queries documents, annotation, training, and models services; annotator queries annotation and documents services; business_user queries extraction and models services. Each service call uses independent timeouts and error handling.

#### Scenario: system_admin summary returns real data from wired sources

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response includes the real tenant count in `stats[0].value`
- **AND** `sources.tenants` is `true`
- **AND** training-dependent fields (pending approvals count, avg F1) are fetched from the training service

#### Scenario: unauthenticated request rejected

- **GIVEN** the request carries no valid JWT
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response is `401 Unauthorized`

### Requirement: Hero Section

The dashboard page SHALL render a hero section at the top that displays the `kicker` (small caps label, JetBrains Mono 12px uppercase), `title` (large heading, Hanken Grotesk 800 38px), and `line` (supporting sentence, Inter 15px). In **Editorial** layout the hero SHALL use large typographic treatment on a transparent background. In **Command** layout the hero SHALL use a dark rounded container (`#161b24` background, 24px border radius) with animated mesh gradient orbs, white title text, and a compact layout that integrates the kicker, title, and line. The layout preference SHALL be toggled by a `SegmentControl` with options `["Editorial", "Command"]` and persisted to `localStorage` under the key `"portal-layout"`.

#### Scenario: editorial layout renders large hero on transparent background

- **GIVEN** the layout preference is "Editorial" (default)
- **WHEN** the dashboard page renders
- **THEN** the kicker, title, and line are displayed in large typographic layout with transparent background
- **AND** the SegmentControl shows "Editorial" as the active option

#### Scenario: command layout renders compact hero with dark container

- **GIVEN** the layout preference is "Command"
- **WHEN** the dashboard page renders
- **THEN** the hero uses a dark container with 24px border radius, animated gradient orbs, white title text
- **AND** all three hero elements (kicker, title, line) remain visible

#### Scenario: layout toggle persists across navigation

- **GIVEN** the user switches to "Command" layout
- **WHEN** they navigate away and return to the dashboard
- **THEN** "Command" layout is still active (read from `localStorage`)

#### Scenario: layout toggle does not re-fetch data

- **GIVEN** data has already loaded
- **WHEN** the user toggles the layout
- **THEN** no new network request is made
- **AND** the stat and panel data remain unchanged

### Requirement: Stat Card Strip

The dashboard page SHALL render exactly 4 `StatCard` components in a 4-column grid with 14px gap below the hero. Each card SHALL display: `value` + `unit` (Hanken Grotesk 800 30px), `label` (card title, Inter 12px), `sub` (context line, JetBrains Mono 10.5px), `delta` (change indicator pill with coloured background), and directional styling (`up` = green/*good* background/text, `warn` = amber/*warn* background/text, neutral = grey). Cards SHALL have 16px border radius, `var(--surface-2)` background, `var(--line)` border, and a hover transform of `translateY(-2px)`. While data is loading the stat cards SHALL display skeleton shimmer placeholders. A null `value` SHALL render as `—`.

#### Scenario: stat cards render with live values

- **GIVEN** the dashboard summary has loaded successfully
- **WHEN** the stat strip renders
- **THEN** 4 cards are visible, each showing the correct value, unit, label, sub, and delta for the user's role

#### Scenario: stat cards render skeleton while loading

- **GIVEN** the dashboard query is in-flight
- **WHEN** the stat strip renders
- **THEN** 4 skeleton placeholder cards are visible with shimmer animation (no spinner, no empty boxes)

#### Scenario: warn direction renders amber indicator

- **GIVEN** a stat item has `dir: "warn"` (e.g., "Pending approvals")
- **WHEN** the card renders
- **THEN** the delta indicator pill has amber/warn colour background and text

### Requirement: Activity Panel

The dashboard page SHALL render a primary activity panel (flex: 1.5fr in a two-column grid with 16px gap) displaying `pTitle` (Hanken Grotesk 700 15px) and `pMeta` (JetBrains Mono 11px) as the panel header with a bottom border, followed by a list of exactly 4 `ActivityRow` items. Each row SHALL show: a coloured status `dot` (9px diameter circle), `title` (primary text, Inter 600 13.5px), `sub` (secondary text, JetBrains Mono 11px), and a coloured status `tag` pill. Each row SHALL be clickable (full-width button, 12px border radius, hover background `var(--surface-3)`) and navigate to the screen identified by `row.go` (mapped route: `"training"` → `/training`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/models`). The panel SHALL have 18px border radius, `var(--surface-2)` background, `var(--line)` border, and `var(--shadow)`.

#### Scenario: activity row navigates on click

- **GIVEN** a `system_admin` activity row has `go: "training"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/training`

#### Scenario: status tag colours match mockup

- **GIVEN** a row has `tk: "pending_approval"`
- **WHEN** the row renders
- **THEN** the tag pill uses the amber/warn colour (`var(--warn-soft)` background, `var(--warn)` text)
- **AND** a row with `tk: "completed"` uses the green/good colour (`var(--good-soft)` background, `var(--good)` text)
- **AND** a row with `tk: "running"` shows a pulsing dot animation

### Requirement: Secondary Metrics Panel

The dashboard page SHALL render a secondary panel (flex: 1fr, column layout with 16px gap) to the right of the activity panel. It SHALL contain two stacked cards (18px border radius, `var(--surface-2)` background, `var(--line)` border, `var(--shadow)`). The top card SHALL display: `sideTop` + `sideMeta` as the header (Hanken Grotesk 700 15px + JetBrains Mono 11px), `big` + `bigUnit` as the primary metric (Hanken Grotesk 800 44px in primary colour), a horizontal progress bar (8px height, `var(--surface-3)` track, `var(--primary)-to-primary-2` gradient fill) filled to `bar` percent with `growBar` CSS animation on mount, three `sideMetrics` rows (`k` + `v` in JetBrains Mono 11px). The bottom card SHALL display: `sideBot` header, and a mini bar chart of `sideRows` where each row shows a colour-coded bar (6px height, 5px border radius) scaled to `pct` percent with `growBar` animation, with label and value in `12px` text.

#### Scenario: progress bar fills to correct percentage

- **GIVEN** `bar: 62` in the dashboard data
- **WHEN** the secondary panel renders
- **THEN** the progress bar is filled to 62% of its container width
- **AND** the `growBar` animation plays from width `0` to `62%` on mount

#### Scenario: sideRows mini bars render correct colours

- **GIVEN** `sideRows[0].c` is `"oklch(0.64 0.15 25)"` or a CSS variable
- **WHEN** the mini bar renders
- **THEN** the bar background colour matches the specified CSS colour

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
