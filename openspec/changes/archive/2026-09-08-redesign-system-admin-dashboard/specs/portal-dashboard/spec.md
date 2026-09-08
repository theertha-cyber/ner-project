## MODIFIED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`. Role-specific differences (including the `system_admin` differences below) are differences in the *data* populating this shape only — no role introduces a new component, prop, or layout structure beyond what this shape and the existing `StatCard`/`ActivityPanel`/`MetricsPanel` components already render.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains a `kicker`/`title`/`line` framed around platform operations, tenant management, and approvals
- **AND** `stats` contains exactly 4 items: Active Tenants, Active Users, Pending Approvals, Training Jobs Running — none of which reference a tenant's model F1, precision, recall, or loss
- **AND** `pTitle: "Platform Activity"` with the most recent cross-tenant `audit_events` rows ordered chronologically — a generic feed of recent platform audit events (examples include tenant created/deactivated, user onboarded, training approved/rejected, model promoted, but the response is not limited to these), not limited to pending-approval items
- **AND** a side panel titled "Platform Health" reports a deterministic overall status ("Healthy", "Degraded", or "Critical" — computed from service reachability, never a hand-picked string) plus per-service Online/Offline reachability for Gateway, Chat API, Extraction Service, Training Service, and Model Serving
- **AND** the side panel contains no SLA, p95 latency, error-rate, or GPU metrics

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
- **THEN** the response includes the real active-tenant count in `stats[0].value`
- **AND** `sources.tenants` is `true`
- **AND** the Active Users stat is fetched from `public.tenant_users`
- **AND** the Pending Approvals and Training Jobs Running stats are fetched by iterating tenant Postgres schemas
- **AND** the Platform Activity feed is fetched from `public.audit_events`, generically (no `action`/`kind` allowlist applied)
- **AND** the Platform Health panel reflects live, concurrently-issued `/health` checks against Gateway, Chat API, Extraction Service, Training Service, and Model Serving, with the overall status derived deterministically from their results

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

### Requirement: Activity Panel

The dashboard page SHALL render a primary activity panel displaying `pTitle` and `pMeta` as the panel header, followed by a list of exactly 4 `ActivityRow` items. Each row SHALL show: a coloured dot indicator (left side), `title` (primary text), `sub` (secondary text), and a coloured status `tag` pill (right-aligned). The dot indicator SHALL be a small `<div>` with `border-radius: 50%` coloured according to the row's `tk` status key (same colour mapping as the existing tag colours).

Each row SHALL be clickable and navigate to the screen identified by `row.go` (mapped via `navFor` hrefs — `"training"` → `/training-jobs`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/training-jobs`, `"users"` → `/users`, `"tenants"` → `/admin/tenants`).

#### Scenario: activity row navigates on click

- **GIVEN** a `system_admin` activity row has `go: "training"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/training-jobs`

#### Scenario: tenant lifecycle activity row navigates to tenant admin console

- **GIVEN** a `system_admin` Platform Activity row represents a `tenant.create` or `tenant.deactivate` event and has `go: "tenants"`
- **WHEN** the user clicks the row
- **THEN** the router navigates to `/admin/tenants`

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

For `system_admin`, `sideMetrics` and `sideRows` values of literal `"Online"`/`"Offline"` SHALL render using a status colour treatment (green for `"Online"`, red for `"Offline"`) rather than the default text colour. The `big` value SHALL likewise render with a status colour when it is one of the deterministic Platform Health statuses: green for `"Healthy"`, amber for `"Degraded"`, red for `"Critical"`. This extends the existing colour-mapping function used elsewhere in this panel; it does not introduce a new component or layout.

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

#### Scenario: system_admin service status renders with status colour

- **GIVEN** the authenticated user has role `system_admin`
- **AND** a `sideMetrics` entry has `v: "Offline"`
- **WHEN** the secondary panel renders
- **THEN** that metric's value SHALL render in the red/bad status colour, not the default secondary text colour

#### Scenario: system_admin overall Platform Health status renders with severity colour

- **GIVEN** the authenticated user has role `system_admin`
- **AND** `big` is `"Critical"`
- **WHEN** the secondary panel renders
- **THEN** `big` SHALL render in the red/bad status colour
- **AND** if `big` were `"Degraded"` instead, it SHALL render in the amber/warn status colour
- **AND** if `big` were `"Healthy"` instead, it SHALL render in the green/good status colour
