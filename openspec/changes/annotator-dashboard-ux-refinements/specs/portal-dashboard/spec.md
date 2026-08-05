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
- **THEN** the response contains 3 stats (Assigned tasks, Entities Annotated, Completion %), `pTitle: "My tasks"` with 4 task rows (showing document name, status, span/suggestion count), and a side panel titled "Dataset readiness" with a progress bar reflecting actual percent complete toward the 500-entity training threshold, copy conveying how many entities are still needed (or that the threshold is met), copy conveying that 500 annotated entities unlocks training, doc/type/today metrics, and a span-by-entity-type breakdown

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

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from the tenant's database tables directly (gateway queries tenant schema tables rather than calling downstream services for MVP). The response SHALL include a top-level `sources` object mapping each data domain (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`, `"extraction"`) to `true` (data retrieved) or `false` (query failed or not applicable for this role).

Each role handler SHALL accept the `db` session and `tenant_id` parameters and execute real SQL queries against the tenant's schema. Every query SHALL be wrapped in try/catch with independent error handling — a failed query SHALL set the affected fields to `null`, the corresponding `sources.*` flag to `false`, and SHALL NOT fail the entire request.

For the `annotator` role, the Dataset Readiness panel's `bar` field SHALL be computed from the annotator's actual annotated-entity count against the 500-entity threshold (`min(count / 500 * 100, 100)`), not a fixed placeholder value.

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

#### Scenario: annotator summary returns real task data and a live progress bar

- **GIVEN** the caller has role `annotator` and has assigned annotation tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the count of assigned tasks
- **AND** `stats[1].value` SHALL contain the count of annotated entities, under the label `"Entities Annotated"`
- **AND** `stats[2].value` SHALL contain the task completion percentage
- **AND** `bar` SHALL reflect the actual percent of the 500-entity threshold reached, not `0`

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
