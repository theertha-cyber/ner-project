## MODIFIED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of `ActivityRow`, each including `title`, `sub`, `tag`, `tk`, `go`, `icon`, and `time`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, and a side panel titled "Platform health" with SLA, latency, error rate, and GPU metrics
- **AND** the `sideRows` section contains storage usage by tenant (label, val, pct, colour)

#### Scenario: tenant_admin data shape

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `title: "Workspace overview."` and a workspace-framed `line`
- **AND** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training count)
- **AND** `pTitle: "Recent Activity"` with up to 4 curated operational activity rows (each with a non-empty `icon` and `time`), drawn from the event catalogue defined in the "Activity Panel" requirement — not raw per-record status rows
- **AND** a side panel titled "Active model" with eval F1, precision, recall, loss, and quota usage rows (Documents, Storage, Model versions)

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

### Requirement: Activity Panel

The dashboard page SHALL render a primary activity panel displaying `pTitle` and `pMeta` as the panel header, followed by a list of up to 4 `ActivityRow` items. Each row SHALL show: a coloured dot indicator (left side), an icon derived from `icon` (leftmost, before the dot's text column), `title` (primary text), an optional `sub` (secondary text, may be empty), a relative timestamp derived from `time` (e.g. `"2 hours ago"`, `"Yesterday"`, `"3 days ago"`), and a coloured status `tag` pill (right-aligned). The dot indicator SHALL be a small `<div>` with `border-radius: 50%` coloured according to the row's `tk` status key (same colour mapping as the existing tag colours).

Each row SHALL be clickable and navigate to the screen identified by `row.go` (mapped via `navFor` hrefs — `"training"` → `/training-jobs`, `"annotation"` → `/annotation`, `"documents"` → `/documents`, `"extractions"` → `/extractions`, `"models"` → `/models`, `"users"` → `/users`).

For `tenant_admin`, `pRows` (and the corresponding `GET /api/v1/dashboard/activity` full-history response) SHALL be limited to the following curated operational event kinds, and SHALL exclude routine per-record status changes (e.g. an individual document moving from `uploaded` to `processing`, or a single annotation task being claimed) that are not in this list:

- Model training requested
- Model training approved
- Model training completed
- Model training failure
- Model deployment
- Batch extraction completed
- Dataset reached training readiness
- Large document upload completed
- Business User added
- Annotator added

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

#### Scenario: row renders icon and relative timestamp

- **GIVEN** a row has `icon: "deploy"` and `time: "2 hours ago"`
- **WHEN** the row renders
- **THEN** the icon corresponding to `"deploy"` is visible to the left of the row's text content
- **AND** the text `"2 hours ago"` is visible in the row

#### Scenario: tenant_admin activity feed shows curated events, not raw row activity

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** the tenant's schema has 50 raw document uploads and one completed model training run in the last 24 hours
- **WHEN** the dashboard's activity panel renders
- **THEN** the panel SHALL NOT contain 50 separate "document uploaded" rows
- **AND** the panel SHALL contain a "Model training completed" row (or equivalent from the curated event list) if it is among the most recent events

#### Scenario: business user added event appears in tenant_admin activity feed

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** a new user with role `business_user` was added to the tenant within the last 24 hours
- **WHEN** the dashboard's activity panel renders
- **THEN** a row titled "Business User added" SHALL appear, with `go: "users"` and a `time` reflecting when the user was added

#### Scenario: annotator added event appears in tenant_admin activity feed

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** a new user with role `annotator` was added to the tenant within the last 24 hours
- **WHEN** the dashboard's activity panel renders
- **THEN** a row titled "Annotator added" SHALL appear, with `go: "users"` and a `time` reflecting when the user was added

#### Scenario: model deployment event appears in tenant_admin activity feed

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** a model version's status became `promoted` within the last 24 hours
- **WHEN** the dashboard's activity panel renders
- **THEN** a row titled "Model deployment" SHALL appear, with `go: "models"` and a `time` derived from the promotion timestamp

#### Scenario: training failure event appears in tenant_admin activity feed

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** a training job's status is `failed`
- **WHEN** the dashboard's activity panel renders
- **THEN** a row titled "Model training failure" SHALL appear, with `go: "training"` and `tk` mapped to the failed/error colour

#### Scenario: tenant_admin activity panel pads with placeholders when fewer than 4 events exist

- **GIVEN** the authenticated user has role `tenant_admin`
- **AND** fewer than 4 curated events exist in the tenant's history
- **WHEN** the dashboard's activity panel renders
- **THEN** the remaining rows SHALL render as placeholder rows (`title: "—"`) rather than falling back to raw per-record activity
