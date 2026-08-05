## MODIFIED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL decode the JWT to extract `role` and `tenant_id`. It SHALL assemble a `DashboardData` JSON object by calling downstream services appropriate for the caller's role:

- `system_admin`: tenants service (tenant count), training service (pending approval jobs, running jobs, promoted model F1)
- `tenant_admin`: documents service (document count), annotation service (span count, completion %), training service (active model F1, running jobs), models service (promoted model version, eval metrics), chat feedback data (total eligible assistant messages, total rated messages, positive/negative counts, satisfaction ratio, satisfaction trend)
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
- `pRows` (array of 4 `ActivityRow`: `{title, sub, tag, tk, go}`) — activity rows with status tag colour key (`tk`), route target (`go`)
- `sideTop` (string) — secondary panel top header
- `sideMeta` (string) — secondary panel metadata
- `big` (string) — large primary metric value
- `bigUnit` (string) — unit for the large metric
- `bar` (number 0–100) — progress bar fill percent
- `sideMetrics` (array of 3 `{k, v}`) — secondary metric rows
- `sideBot` (string) — secondary panel bottom header
- `sideRows` (array of `{label, val, pct, c}`) — mini bar chart rows with colour
- `responseQuality` (`ResponseQualityCard | null`, `tenant_admin` only — see below)

Numeric values that cannot be fetched SHALL be `null` (not omitted).

For `tenant_admin`, `sideTop`/`sideMeta`/`big`/`bigUnit`/`bar`/`sideMetrics` continue to report the active model's eval F1/precision/recall/loss exactly as before this change (unaffected by feedback data). `sideBot`/`sideRows` SHALL be `""`/`[]` for `tenant_admin` — they are no longer used to carry feedback data.

Instead, the response SHALL include a `responseQuality` object (`null` only if the underlying query fails) shaped as:
- `status` (`"healthy" | "monitor" | "needs_attention" | "no_data"`) — an interpreted health signal, not a raw number, so a Tenant Admin does not have to derive it themselves
- `satisfactionPct` (number 0–100, or `null` when `rated = 0`)
- `positive` (integer) — count of `rating = "up"` among rated eligible answer messages
- `negative` (integer) — count of `rating = "down"` among rated eligible answer messages
- `rated` (integer) — count of eligible (`answer_kind = "answer"`) assistant messages that have been reviewed by a Business User
- `total` (integer) — count of all eligible assistant messages, reviewed or not
- `recommendation` (string) — a plain-language sentence telling the Tenant Admin whether retraining should be considered, derived from `status`

The satisfaction percentage and status SHALL be computed as **positive ratings ÷ total rated messages** — where "rated messages" counts only assistant messages (`answer_kind = "answer"`) that have a `chat_message_feedback` row, and "positive ratings" counts the subset of those with `rating = "up"`. Assistant answer messages with no feedback row SHALL NOT be counted in either the numerator or the denominator, and SHALL NOT be treated as implicitly negative or implicitly positive.

`status` SHALL be derived as: `"no_data"` when `rated = 0`; otherwise `"healthy"` when the percentage is ≥ 80; `"monitor"` when 60–79; `"needs_attention"` when < 60. `satisfactionPct` SHALL be `null` (not `0` or `100`) when `rated = 0`, since the ratio is undefined. `recommendation` SHALL be a fixed sentence per `status`: `healthy` → advises no retraining is needed; `monitor` → advises watching performance and gathering more feedback; `needs_attention` → advises considering retraining; `no_data` → states there isn't enough feedback yet to assess performance.

#### Scenario: system_admin summary returns role-specific data

- **GIVEN** the caller has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, `title` mentioning tenant count and pending approvals, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, `sideTop: "Platform health"` with SLA, p95 latency, error rate, and GPU metrics

#### Scenario: tenant_admin summary returns pipeline data and a healthy response-quality card

- **GIVEN** the caller has role `tenant_admin`, with 61 eligible assistant answer messages of which 42 are rated (35 up, 7 down)
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training), `pTitle: "Pipeline activity"` with 4 activity rows, `sideTop: "Active model"` with `big`/`bigUnit`/`sideMetrics` reporting eval F1, precision, recall, loss exactly as before this change
- **AND** `sideBot` SHALL equal `""` and `sideRows` SHALL equal `[]`
- **AND** `responseQuality` SHALL equal `{status:"healthy", satisfactionPct:83.3, positive:35, negative:7, rated:42, total:61, recommendation:<a no-retraining-needed sentence>}` (83.3 = 35/42, rounded to one decimal — not 35/61)

#### Scenario: tenant_admin summary returns a needs_attention response-quality card

- **GIVEN** the caller has role `tenant_admin`, with 70 eligible assistant answer messages of which 3 are rated (1 up, 2 down)
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `responseQuality.status` SHALL equal `"needs_attention"` (1/3 ≈ 33%, below the 60% threshold)
- **AND** `responseQuality.recommendation` SHALL advise considering retraining

#### Scenario: tenant_admin summary returns a monitor response-quality card

- **GIVEN** the caller has role `tenant_admin`, with a rated subset whose satisfaction percentage is between 60 and 79 inclusive
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `responseQuality.status` SHALL equal `"monitor"`
- **AND** `responseQuality.recommendation` SHALL advise monitoring performance and gathering more feedback, not immediate retraining

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

#### Scenario: tenant_admin summary with no rated feedback yet

- **GIVEN** the caller has role `tenant_admin`, with some eligible assistant answer messages but none rated (`rated = 0`)
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `responseQuality.status` SHALL equal `"no_data"` and `responseQuality.satisfactionPct` SHALL be `null` (not a misleading `0` or `100`)
- **AND** `responseQuality.total` SHALL equal the real total, and `rated`/`positive`/`negative` SHALL all equal `0`
- **AND** `responseQuality.recommendation` SHALL state there isn't enough feedback yet to assess performance
- **AND** the response SHALL still have status 200

#### Scenario: Unrated eligible answer messages do not affect the ratio

- **GIVEN** the caller has role `tenant_admin`, with 20 eligible assistant answer messages of which 5 are rated (4 up, 1 down) and 15 are unrated
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `responseQuality.satisfactionPct` SHALL equal `80` (4 / 5, the rated subset only)
- **AND** `responseQuality.total` SHALL equal `20` while `responseQuality.rated` SHALL equal `5`
- **AND** the 15 unrated messages SHALL NOT appear in either the numerator or the denominator of the percentage

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

The portal SHALL define a `DashboardData` TypeScript interface in `src/portal/lib/types.ts` matching the mockup's `dashData(role)` shape. The type SHALL include optional fields (marked with `?`) for values that may be `null` when the upstream service is unavailable.

#### Scenario: type compiles with all fields

- **GIVEN** a `DashboardData` object matching the mockup's shape
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors

#### Scenario: null values are assignable

- **GIVEN** a `DashboardData` object where `stats[0].value` is `null`
- **WHEN** it is assigned to the TypeScript type
- **THEN** the TypeScript compiler produces no errors
