## ADDED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL decode the JWT to extract `role` and `tenant_id`. It SHALL assemble a `DashboardData` JSON object by calling downstream services appropriate for the caller's role:

- `system_admin`: tenants service (tenant count), training service (pending approval jobs, running jobs, promoted model F1)
- `tenant_admin`: documents service (document count), annotation service (span count, completion %), training service (active model F1, running jobs), models service (promoted model version, eval metrics)
- `annotator`: annotation service (assigned task count, confirmed span count, suggestion count, completion %), documents service (document count)
- `business_user`: extraction service (extraction count, entity count, avg confidence, auto-cleared %), models service (active model F1, eval metrics)

Each downstream call SHALL use a short timeout (5s connect, 10s read). If a service is unavailable or returns an error, its data fields SHALL be `null` and the response SHALL include a top-level `sources` object mapping each service name to `true` (data retrieved) or `false` (unavailable/not applicable).

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
- **THEN** the response contains `kicker: "Platform control plane"`, `title` mentioning tenant count and pending approvals, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, `sideTop: "Platform health"` with SLA, p95 latency, error rate, and GPU metrics

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

### Requirement: DashboardData TypeScript Type

The portal SHALL define a `DashboardData` TypeScript interface in `src/portal/lib/types.ts` matching the mockup's `dashData(role)` shape. The type SHALL include optional fields (marked with `?`) for values that may be `null` when the upstream service is unavailable.

#### Scenario: type compiles with all fields

- **GIVEN** a `DashboardData` object matching the mockup's shape
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors

#### Scenario: null values are assignable

- **GIVEN** a `DashboardData` object where `stats[0].value` is `null`
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors
