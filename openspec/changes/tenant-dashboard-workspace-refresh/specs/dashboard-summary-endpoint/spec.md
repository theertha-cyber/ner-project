## MODIFIED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL decode the JWT to extract `role` and `tenant_id`. It SHALL assemble a `DashboardData` JSON object by calling downstream services appropriate for the caller's role:

- `system_admin`: tenants service (tenant count), training service (pending approval jobs, running jobs, promoted model F1)
- `tenant_admin`: documents service (document count), annotation service (span count, completion %), training service (active model F1, running jobs), models service (promoted model version, eval metrics)
- `annotator`: annotation service (assigned task count, confirmed span count, suggestion count, completion %), documents service (document count)
- `business_user`: extraction service (extraction count, entity count, avg confidence, auto-cleared %), models service (active model F1, eval metrics)

Each downstream call SHALL use a short timeout (5s connect, 10s read). If a service is unavailable or returns an error, its data fields SHALL be `null` and the response SHALL include a top-level `sources` object mapping each service name to `true` (data retrieved) or `false` (unavailable/not applicable).

For `system_admin`, several stats are computed by iterating a raw SQL query across tenant Postgres schemas (e.g. pending-approval job counts, promoted model F1) on a single shared database session. The set of schemas iterated SHALL be derived from the schemas that actually exist in the database, not from `public.tenants` rows: a tenant row SHALL only contribute a schema to the iteration if a schema of the corresponding name exists. Tenant rows that have no backing schema — including the virtual `system` tenant and any test-fixture tenant rows — SHALL be excluded before any query is issued, and SHALL NOT produce an error, a logged exception, or a session rollback.

If a query against one tenant's schema fails, the system SHALL recover the session (e.g. via rollback) before issuing the next query, so that a single tenant schema's failure SHALL NOT prevent queries against other tenant schemas, or other metrics computed later in the same request, from succeeding. A schema-level failure SHALL be excluded from the aggregate (as if that tenant contributed no data) rather than aborting the whole computation.

When a tenant's schema exists but a query against it fails, the affected aggregate SHALL NOT be reported as a complete figure. The corresponding `sources` entry SHALL be `false` so the caller can distinguish a true total from a partial one.

The response SHALL conform to the `DashboardData` TypeScript type matching the mockup's `dashData(role)` shape:
- `kicker` (string) — small-caps hero kicker
- `title` (string) — hero heading
- `line` (string) — supporting hero sentence
- `stats` (array of 4 `StatItem`: `{label, value, unit, sub, delta, dir}`) — stat card data
- `pTitle` (string) — primary panel header
- `pMeta` (string) — primary panel metadata
- `pRows` (array of 4 `ActivityRow`: `{title, sub, tag, tk, go, icon, time}`) — activity rows with status tag colour key (`tk`), route target (`go`), icon key (`icon`), and a server-formatted relative timestamp (`time`, e.g. `"2 hours ago"`)
- `sideTop` (string) — secondary panel top header
- `sideMeta` (string) — secondary panel metadata
- `big` (string) — large primary metric value
- `bigUnit` (string) — unit for the large metric
- `bar` (number 0–100) — progress bar fill percent
- `sideMetrics` (array of 3 `{k, v}`) — secondary metric rows
- `sideBot` (string) — secondary panel bottom header
- `sideRows` (array of `{label, val, pct, c}`) — mini bar chart rows with colour

Numeric values that cannot be fetched SHALL be `null` (not omitted).

For `tenant_admin`, `kicker`/`title`/`line` SHALL describe the tenant's AI workspace (model performance, dataset readiness, operational status) rather than the underlying processing pipeline, and `pTitle` SHALL be `"Recent Activity"`. `pRows` for `tenant_admin` SHALL be sourced from the curated operational event catalogue defined in the `portal-dashboard` capability's "Activity Panel" requirement, not from raw per-record status changes.

#### Scenario: system_admin summary returns role-specific data

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, `title` mentioning tenant count and pending approvals, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, `sideTop: "Platform health"` with SLA, p95 latency, error rate, and GPU metrics

#### Scenario: tenant_admin summary returns workspace overview data

- **GIVEN** the caller has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `title: "Workspace overview."` and a `line` describing monitoring the AI workspace, model performance, and dataset readiness (not the words "pipeline" or "processing")
- **AND** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training)
- **AND** `pTitle` is `"Recent Activity"` with up to 4 curated operational activity rows, each including a non-empty `icon` and `time` field
- **AND** `sideTop: "Active model"` with eval F1, precision, recall, loss, and quota usage rows

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
- **AND** the pending-approvals and avg-model-F1 stats SHALL reflect the healthy tenants' data (not `null` and not silently zeroed solely because of the one failing tenant)
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
- **THEN** those rows SHALL contribute nothing to the document, pending-approval, and model-F1 aggregates
- **AND** the number of logged exceptions attributable to missing schemas SHALL be zero

#### Scenario: A partial aggregate is not reported as a complete total

- **GIVEN** the caller has role `system_admin`
- **AND** one tenant schema exists but its `documents` query fails
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the "Documents (all)" stat SHALL NOT be presented as a complete platform total
- **AND** `sources.documents` SHALL be `false`

---

### Requirement: DashboardData TypeScript Type

The portal SHALL define a `DashboardData` TypeScript interface in `src/portal/lib/types.ts` matching the mockup's `dashData(role)` shape. The type SHALL include optional fields (marked with `?`) for values that may be `null` when the upstream service is unavailable. The `ActivityRow` interface SHALL include `icon: string` and `time: string` fields alongside the existing `title`, `sub`, `tag`, `tk`, and `go` fields.

#### Scenario: type compiles with all fields

- **GIVEN** a `DashboardData` object matching the mockup's shape
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors

#### Scenario: null values are assignable

- **GIVEN** a `DashboardData` object where `stats[0].value` is `null`
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors

#### Scenario: ActivityRow icon and time fields are required strings

- **GIVEN** an `ActivityRow` object missing the `icon` or `time` field
- **WHEN** it is assigned to the `ActivityRow` TypeScript type
- **THEN** the TypeScript compiler produces an error
