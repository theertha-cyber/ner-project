## ADDED Requirements

### Requirement: Per-Entity-Type Dataset Readiness

The annotator dataset-readiness panel SHALL measure readiness as labeled spans **per active entity type**, against a threshold of **200 spans per type**, replacing the previous tenant-wide total of 500 spans.

The set of entity types evaluated SHALL be the **union** of the tenant's active entity definitions (`public.entity_definitions` filtered by the caller's `tenant_id` with `is_active = true`) and the distinct `entity_type` values present in `{schema}.spans`. An active entity definition with zero recorded spans SHALL appear in the breakdown at zero and SHALL NOT be omitted; equally, an entity type that has spans SHALL appear even when no matching active definition exists.

Per-type progress SHALL be `min(count / 200, 1)`. The panel's overall readiness percentage (`bar`) SHALL be the mean of per-type progress across all evaluated types, expressed as a percentage — so an over-annotated type cannot compensate for a starved one. The panel SHALL additionally convey how many types have met the threshold out of the total evaluated.

When the union is empty — the tenant has neither active entity definitions nor any spans — readiness SHALL be reported as unavailable rather than as `0%` or `100%`.

Breakdown rows SHALL be ordered by least progress first, so the entity type most in need of annotation appears at the top.

The readiness query SHALL be scoped to the caller's tenant. Span counts SHALL be read from the caller's tenant schema and entity definitions SHALL be filtered by the caller's `tenant_id`; no other tenant's counts or definitions SHALL contribute to the result.

#### Scenario: readiness reflects the weakest entity type

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has active entity types with span counts `PROGRAMMING_LANGUAGE: 400`, `JOB_TITLE: 100`, `CONTACT_DETAILS: 0`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `bar` is `50.0` — the mean of capped progress `1.0`, `0.5`, `0.0`
- **AND** the panel conveys that 1 of 3 entity types has met the threshold

#### Scenario: over-annotated type cannot mask a starved one

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has active entity types with span counts `SKILL: 2000`, `EDUCATION: 0`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `bar` is `50.0`, not `100.0`
- **AND** the panel conveys that 1 of 2 entity types has met the threshold

#### Scenario: entity type with zero spans appears in the breakdown

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has an active entity definition `EDUCATION` with no spans recorded
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `sideRows` contains a row labelled `EDUCATION` with a value of `0` and a percentage of `0`

#### Scenario: breakdown is ordered least-progress-first

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has active entity types with span counts `SKILL: 180`, `EDUCATION: 20`, `JOB_TITLE: 90`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `sideRows` are ordered `EDUCATION`, `JOB_TITLE`, `SKILL`

#### Scenario: inactive entity types with no spans are excluded

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has an entity definition `LEGACY_FIELD` with `is_active = false` and no spans
- **AND** all active entity types have at least 200 spans
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `bar` is `100.0`
- **AND** `sideRows` contains no row labelled `LEGACY_FIELD`

#### Scenario: entity types with spans but no definition are included

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has no active entity definitions at all
- **AND** `{schema}.spans` holds 105 spans each for `DATE`, `MONEY`, `ORG`, `LOC`, and `PER`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `sideRows` contains a row for each of the five types
- **AND** readiness is not reported as unavailable
- **AND** `bar` reflects those five types' progress toward 200 each

#### Scenario: all types at or above threshold reports fully ready

- **GIVEN** the caller has role `annotator`
- **AND** every active entity type has at least 200 spans
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `bar` is `100.0`
- **AND** the panel conveys that the training threshold has been reached

#### Scenario: neither definitions nor spans reports unavailable

- **GIVEN** the caller has role `annotator`
- **AND** the tenant has no active entity definitions and no spans
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the readiness panel conveys that readiness is unavailable
- **AND** `bar` is not reported as `100`

#### Scenario: readiness does not read another tenant's data

- **GIVEN** two tenants each have active entity definitions and spans
- **WHEN** `GET /api/v1/dashboard/summary` is called by an annotator of the first tenant
- **THEN** only the first tenant's span counts and entity definitions contribute to `bar` and `sideRows`

### Requirement: Annotator Assigned-Task Fraction

The annotator `Assigned tasks` stat SHALL report completed tasks over total assigned tasks as a fraction string (for example `"3/5"`), where the numerator counts tasks assigned to the caller with status `completed` and the denominator counts all tasks assigned to the caller regardless of status.

The stat's sub-label SHALL convey how many tasks remain. When the annotator has no assigned tasks the value SHALL be `"0/0"` and the sub-label SHALL convey that no tasks are assigned.

#### Scenario: fraction reflects completed over total

- **GIVEN** the caller has role `annotator` with 5 assigned tasks of which 3 have status `completed`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the `Assigned tasks` stat value is `"3/5"`
- **AND** its sub-label conveys 2 remaining

#### Scenario: every not-started vocabulary counts toward the denominator

- **GIVEN** the caller has role `annotator` with 2 tasks of status `completed` and 1 task whose status is `pending`, `unannotated`, or `open`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the `Assigned tasks` stat value is `"2/3"`

#### Scenario: no assigned tasks

- **GIVEN** the caller has role `annotator` with no assigned tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the `Assigned tasks` stat value is `"0/0"`
- **AND** its sub-label conveys that no tasks are assigned

### Requirement: Stat Sub-Labels Carry Information

Stat card `sub` values SHALL convey information about the figure above them. The literal placeholder string `"active"` SHALL NOT be emitted as a stat `sub` for any role. Where no informative sub-label exists for a stat, `sub` SHALL be the empty string so the card renders without a context line.

Diagnostic sub-labels that report a degraded state (for example `"service unavailable"`) SHALL be retained, as SHALL informative sub-labels such as remaining counts or quota percentages.

This requirement governs the `sub` field of `StatItem` only. It SHALL NOT apply to `ActiveModelInfo.status`, where `"active"` denotes a deployment state, nor to `ActivityRow.tk`, where `"active"` is a tag colour key.

#### Scenario: annotator stats emit no placeholder sub

- **GIVEN** the caller has role `annotator` with data available for every stat
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** no entry in `stats` has `sub` equal to `"active"`

#### Scenario: system_admin stats emit no placeholder sub

- **GIVEN** the caller has role `system_admin` with data available for every stat
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** no entry in `stats` has `sub` equal to `"active"`

#### Scenario: tenant_admin documents fallback emits no placeholder sub

- **GIVEN** the caller has role `tenant_admin` and the tenant has no configured `max_documents` quota
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the `Documents` stat `sub` is not `"active"`

#### Scenario: degraded-state sub-labels are retained

- **GIVEN** the caller has role `annotator` and the assigned-task query fails
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the affected stat's `sub` conveys that the service is unavailable

#### Scenario: active model deployment status is unaffected

- **GIVEN** the caller has role `tenant_admin` and a promoted model is serving
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `activeModel.status` is `"active"`

### Requirement: Tenant Admin Readiness Activity Event

The tenant_admin activity feed's "Dataset reached training readiness" event SHALL be derived from the per-entity-type threshold. The event SHALL be dated at the moment the **last** active entity type crossed 200 spans, and SHALL NOT appear while any active entity type remains below the threshold.

#### Scenario: event appears once every type has crossed

- **GIVEN** the tenant has three active entity types, the last of which crossed 200 spans yesterday
- **WHEN** a tenant admin requests the dashboard summary
- **THEN** the activity feed contains a "Dataset reached training readiness" event dated yesterday

#### Scenario: event is absent while a type is short

- **GIVEN** the tenant has three active entity types and one holds 40 spans
- **WHEN** a tenant admin requests the dashboard summary
- **THEN** the activity feed contains no "Dataset reached training readiness" event

## MODIFIED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL decode the JWT to extract `role` and `tenant_id`. It SHALL assemble a `DashboardData` JSON object by calling downstream services appropriate for the caller's role:

- `system_admin`: tenants service (tenant count), training service (pending approval jobs, running jobs, promoted model F1)
- `tenant_admin`: documents service (document count), annotation service (span count, completion %), training service (active model F1, running jobs), models service (promoted model version, eval metrics)
- `annotator`: annotation service (assigned-task completed/total fraction, task completion %, continue-work task), entity config (active entity definitions), documents service (document count)
- `business_user`: extraction service (extraction count, entity count, avg confidence, auto-cleared %), models service (active model F1, eval metrics)

Each downstream call SHALL use a short timeout (5s connect, 10s read). If a service is unavailable or returns an error, its data fields SHALL be `null` and the response SHALL include a top-level `sources` object mapping each service name to `true` (data retrieved) or `false` (unavailable/not applicable).

For `system_admin`, several stats are computed by iterating a raw SQL query across tenant Postgres schemas (e.g. pending-approval job counts, promoted model F1) on a single shared database session. The set of schemas iterated SHALL be derived from the schemas that actually exist in the database, not from `public.tenants` rows: a tenant row SHALL only contribute a schema to the iteration if a schema of the corresponding name exists. Tenant rows that have no backing schema — including the virtual `system` tenant and any test-fixture tenant rows — SHALL be excluded before any query is issued, and SHALL NOT produce an error, a logged exception, or a session rollback.

If a query against one tenant's schema fails, the system SHALL recover the session (e.g. via rollback) before issuing the next query, so that a single tenant schema's failure SHALL NOT prevent queries against other tenant schemas, or other metrics computed later in the same request, from succeeding. A schema-level failure SHALL be excluded from the aggregate (as if that tenant contributed no data) rather than aborting the whole computation.

When a tenant's schema exists but a query against it fails, the affected aggregate SHALL NOT be reported as a complete figure. The corresponding `sources` entry SHALL be `false` so the caller can distinguish a true total from a partial one.

The response SHALL conform to the `DashboardData` TypeScript type matching the mockup's `dashData(role)` shape:
- `kicker` (string) — small-caps hero kicker
- `title` (string) — hero heading
- `line` (string) — supporting hero sentence
- `stats` (array of `StatItem`: `{label, value, unit, sub, delta, dir}`) — stat card data; the array length is role-dependent
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
- `continueWork` (`ContinueWork` or `null`) — annotator continue-work card payload; `null` for other roles

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
- **THEN** the response contains 2 stats (Assigned tasks as a completed/total fraction, Completion %) and a non-null `continueWork` payload when the annotator has an outstanding task
- **AND** `pTitle` is `"My tasks"` with 4 task rows
- **AND** `sideTop` is `"Dataset readiness"` reporting progress toward 200 spans per active entity type, with a per-entity-type breakdown
- **AND** no stat reports a tenant-wide span count

#### Scenario: business_user summary returns extraction data

- **GIVEN** the caller has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Docs extracted, Entities found, Avg confidence, Auto-cleared %), `pTitle: "Recent extractions"` with 4 extraction rows, `sideTop: "Active model"` with eval F1, precision, recall, loss, and top extracted fields

## REMOVED Requirements

### Requirement: Annotator Tenant-Wide Entities Annotated Stat

**Reason**: The `Entities Annotated` stat was `SELECT COUNT(*) FROM {schema}.spans` with no annotator filter, so it reported a tenant-wide total under a personal label on a personal dashboard. The identical query also drove the dataset-readiness panel, placing the same number on screen twice under two different names.

**Migration**: The tenant-wide span total remains visible in the dataset-readiness panel, now broken down per entity type. No per-annotator replacement is provided: `spans` carries no annotator attribution column, so a genuine per-annotator count requires a schema change that is deliberately out of scope for this change. The stat slot is taken by the continue-work card.
