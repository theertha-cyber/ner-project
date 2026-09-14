## MODIFIED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL decode the JWT to extract `role` and `tenant_id`. It SHALL assemble a `DashboardData` JSON object by calling downstream services appropriate for the caller's role:

- `system_admin`: `public.tenants` (active tenant count), `public.tenant_users` (active user count), `public.audit_events` (recent platform activity, generic — see the Platform Activity scenario below), tenant Postgres schemas (pending-approval training job count, and running training job count — "Training Jobs Running"), and each backing service's `/health` endpoint (Gateway, Chat API, Extraction Service, Training Service, Model Serving — "Platform Health")
- `tenant_admin`: documents service (document count), annotation service (span count, completion %), training service (active model F1, running jobs), models service (promoted model version, eval metrics)
- `annotator`: annotation service (assigned task count, confirmed span count, suggestion count, completion %), documents service (document count)
- `business_user`: extraction service (extraction count, entity count, avg confidence, auto-cleared %), models service (active model F1, eval metrics)

Each downstream call SHALL use a short timeout (5s connect, 10s read), except the five per-service `/health` reachability checks issued for `system_admin`. Those five checks SHALL each use their own short timeout (3 seconds), SHALL be issued concurrently (not sequentially) so their combined added latency does not exceed roughly one timeout period, and a timeout or failed request on any one service SHALL mark only that service unavailable — it SHALL NOT raise an exception that fails the endpoint, and SHALL NOT block or delay the reporting of any other service's result. If a service is unavailable or returns an error, its data fields SHALL be `null` and the response SHALL include a top-level `sources` object mapping each service name to `true` (data retrieved) or `false` (unavailable/not applicable).

For `system_admin`, several stats are computed by iterating a raw SQL query across tenant Postgres schemas (e.g. pending-approval and running training job counts) on a single shared database session. The set of schemas iterated SHALL be derived from the schemas that actually exist in the database, not from `public.tenants` rows: a tenant row SHALL only contribute a schema to the iteration if a schema of the corresponding name exists. Tenant rows that have no backing schema — including the virtual `system` tenant and any test-fixture tenant rows — SHALL be excluded before any query is issued, and SHALL NOT produce an error, a logged exception, or a session rollback.

If a query against one tenant's schema fails, the system SHALL recover the session (e.g. via rollback) before issuing the next query, so that a single tenant schema's failure SHALL NOT prevent queries against other tenant schemas, or other metrics computed later in the same request, from succeeding. A schema-level failure SHALL be excluded from the aggregate (as if that tenant contributed no data) rather than aborting the whole computation.

When a tenant's schema exists but a query against it fails, the affected aggregate SHALL NOT be reported as a complete figure. The corresponding `sources` entry SHALL be `false` so the caller can distinguish a true total from a partial one.

The response SHALL conform to the `DashboardData` TypeScript type matching the mockup's `dashData(role)` shape:
- `kicker` (string) — small-caps hero kicker
- `title` (string) — hero heading
- `line` (string) — supporting hero sentence
- `stats` (array of 4 `StatItem`: `{label, value, unit, sub, delta, dir}`) — stat card data
- `pTitle` (string) — primary panel header
- `pMeta` (string) — primary panel metadata
- `pRows` (array of 4 `ActivityRow`: `{title, sub, tag, tk, go}`) — activity rows with status tag colour key (`tk`), route target (`go`)
- `sideTop` (string) — secondary panel top header
- `sideMeta` (string) — secondary panel metadata
- `big` (string) — large primary metric value
- `bigUnit` (string) — unit for the large metric
- `bar` (number 0–100) — progress bar fill percent
- `sideMetrics` (array of 3 `{k, v}`) — secondary metric rows
- `sideBot` (string) — secondary panel bottom header
- `sideRows` (array of `{label, val, pct, c}`) — mini bar chart rows with colour

Numeric values that cannot be fetched SHALL be `null` (not omitted).

#### Scenario: system_admin summary returns role-specific data

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker` and `title`/`line` framed around platform operations, tenant management, and approvals (not training pipelines or document processing)
- **AND** `stats` contains exactly 4 items: Active Tenants, Active Users, Pending Approvals, Training Jobs Running
- **AND** `pTitle: "Platform Activity"` with recent activity rows sourced from `public.audit_events` (not limited to pending-approval items)
- **AND** `sideTop: "Platform Health"` with a deterministic overall status in `big` (one of "Healthy", "Degraded", "Critical") and per-service Online/Offline reachability for Gateway, Chat API, Extraction Service, Training Service, and Model Serving
- **AND** no stat, activity row, or health metric references a tenant's model F1, precision, recall, or loss

#### Scenario: tenant_admin summary returns pipeline data

- **GIVEN** the caller has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training), `pTitle: "Pipeline activity"` with 4 activity rows, `sideTop: "Active model"` with eval F1, precision, recall, loss, and quota usage rows

#### Scenario: annotator summary returns task data

- **GIVEN** the caller has role `annotator`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Assigned tasks, Spans confirmed, Suggestions, Completion %), `pTitle: "My tasks"` with 4 task rows, `sideTop: "Dataset readiness"` with span count toward 500 threshold and span-by-entity breakdown

#### Scenario: business_user summary returns extraction data

- **GIVEN** the caller has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Docs extracted, Entities found, Avg confidence, Auto-cleared %), `pTitle: "Recent extractions"` with 4 extraction rows, `sideTop: "Active model"` with eval F1, precision, recall, loss, and top extracted fields

#### Scenario: unavailable training service returns null values

- **GIVEN** the training service returns a 5xx error or times out
- **WHEN** `GET /api/v1/dashboard/summary` is called by a `tenant_admin`
- **THEN** the response contains `null` for training-dependent stat values
- **AND** `sources.training` is `false`
- **AND** the HTTP status is 200 (not 502)

#### Scenario: unauthenticated request rejected

- **GIVEN** the request carries no valid JWT
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response is `401 Unauthorized`

#### Scenario: one tenant schema failure does not blank out other tenants' stats

- **GIVEN** the caller has role `system_admin`
- **AND** one active tenant's schema is missing an expected table or column while all other active tenants' schemas are healthy
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response SHALL have status 200
- **AND** the Pending Approvals and Training Jobs Running stats SHALL reflect the healthy tenants' data (not `null` and not silently zeroed solely because of the one failing tenant)
- **AND** subsequent per-tenant queries in the same request SHALL NOT fail with an aborted-transaction error caused by the earlier failure

#### Scenario: The virtual system tenant is excluded from schema iteration

- **GIVEN** the caller has role `system_admin`
- **AND** `public.tenants` contains the row `id = 'system'`, for which no `tenant_system` schema exists
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** no query SHALL be issued against `tenant_system`
- **AND** no exception SHALL be logged for `tenant_system`
- **AND** the response SHALL have status 200

#### Scenario: Tenant rows without a backing schema are excluded from aggregates

- **GIVEN** the caller has role `system_admin`
- **AND** `public.tenants` contains active rows for which no corresponding schema exists
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** those rows SHALL contribute nothing to the pending-approval count or the Training Jobs Running count
- **AND** the number of logged exceptions attributable to missing schemas SHALL be zero

#### Scenario: A partial aggregate is not reported as a complete total

- **GIVEN** the caller has role `system_admin`
- **AND** one tenant schema exists but its `training_jobs` query (used to compute Training Jobs Running) fails
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the "Training Jobs Running" stat SHALL NOT be presented as a complete platform total
- **AND** `sources.training` SHALL be `false`

#### Scenario: Platform Activity is a generic feed of recent audit events, not a fixed list of event types

- **GIVEN** the caller has role `system_admin`
- **AND** `public.audit_events` contains rows for multiple tenants with a variety of `action` values, including values with no special-cased display title
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `pRows` SHALL contain the most recent `audit_events` rows across all tenants, ordered most-recent-first by `created_at`, regardless of `action`/`kind` — no event type SHALL be filtered out by the endpoint
- **AND** each row's `title` SHALL be human-readable: rows for actions with a known display title (e.g. tenant creation, user onboarding, training approval/rejection, model promotion — illustrative examples, not an exhaustive list) SHALL show that title; rows for any other action SHALL still appear, with a humanized fallback title derived from the raw `action` string rather than being omitted
- **AND** the feed SHALL include events from more than one tenant when more than one tenant has recent activity

#### Scenario: Platform Health status is a deterministic function of per-service reachability

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the overall status in `big` SHALL be computed solely from the reachability of Gateway, Chat API, Extraction Service, Training Service, and Model Serving, using the following fixed rules — never a manually assigned or free-text value:
  - "Healthy" **WHEN** all five services are reachable
  - "Degraded" **WHEN** Gateway and Model Serving are both reachable, but at least one of Chat API, Extraction Service, or Training Service is unreachable
  - "Critical" **WHEN** Gateway or Model Serving is unreachable, regardless of the state of the other three services

#### Scenario: An unreachable non-critical service degrades status without failing the request

- **GIVEN** the caller has role `system_admin`
- **AND** the Training Service's `/health` endpoint is unreachable while Gateway, Chat API, Extraction Service, and Model Serving respond with HTTP 200
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `sideMetrics` and `sideRows` (combined) SHALL report the Training Service as `"Offline"` and the other four services as `"Online"`
- **AND** `big` SHALL be `"Degraded"` (not `"Healthy"` or `"Critical"`)
- **AND** the request SHALL still return HTTP 200 within a bounded time (no single unreachable service SHALL block the response beyond its own timeout, since health checks run concurrently)

#### Scenario: An unreachable critical service reports Critical status

- **GIVEN** the caller has role `system_admin`
- **AND** the Model Serving `/health` endpoint is unreachable while Gateway, Chat API, Extraction Service, and Training Service respond with HTTP 200
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `big` SHALL be `"Critical"` (not `"Degraded"`)
- **AND** the request SHALL still return HTTP 200

#### Scenario: Active Users count reflects tenant_users status

- **GIVEN** the caller has role `system_admin`
- **AND** `public.tenant_users` contains a mix of rows with `status = 'active'` and `status != 'active'`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the "Active Users" stat SHALL equal the count of `public.tenant_users` rows with `status = 'active'`, not the total row count
