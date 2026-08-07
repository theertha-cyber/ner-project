## MODIFIED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of `StatItem`, length role-dependent), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`), and `continueWork` (`ContinueWork` or `null`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`.

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
- **THEN** the response contains 2 stats (Assigned tasks as a completed/total fraction, Completion %) plus a `continueWork` payload
- **AND** `pTitle` is `"My tasks"` with 4 task rows showing document name and status
- **AND** a side panel titled "Dataset readiness" shows a progress bar toward 200 spans per active entity type, doc/type/today metrics, and a per-entity-type breakdown including types with zero spans

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

#### Scenario: annotator summary returns real task data

- **GIVEN** the caller has role `annotator` and has assigned annotation tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `stats[0].value` SHALL contain the completed-over-total assigned-task fraction
- **AND** `stats[1].value` SHALL contain the task completion percentage
- **AND** `continueWork` SHALL identify the task the annotator should return to

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

### Requirement: Stat Card Strip

The dashboard page SHALL render a stat strip in a CSS grid whose column count matches the number of cards for the caller's role, with 14px gap below the hero. For `system_admin`, `tenant_admin`, and `business_user` the strip SHALL contain `StatCard` components only. For `annotator` the strip SHALL contain a `ContinueWorkCard` in the first cell followed by the role's `StatCard` components, for three columns total.

Each `StatCard` SHALL display: `label` (card title) with `delta` pill inline at the top-right, `value` + `unit` below as the primary figure, `sub` (context line, rendered only when non-empty), and a directional delta indicator (`up` = green `#16a34a`, `warn` = amber `#d97706`, neither = neutral). The delta pill SHALL be positioned on the same row as the label, right-aligned. A `value` containing `/` SHALL render as a fraction with the numerator emphasised over the denominator.

Cards SHALL have a hover effect that translates the card up by 2px and changes the border-color to `var(--primary-line)`. While data is loading the stat strip SHALL display skeleton shimmer placeholders. A null `value` SHALL render as `—`.

#### Scenario: stat cards render with inline delta

- **GIVEN** the dashboard summary has loaded successfully for a `tenant_admin`
- **WHEN** the stat strip renders
- **THEN** the cards are visible in a grid whose column count equals the number of cards
- **AND** each card shows the label and delta pill on the same row (delta right-aligned)
- **AND** the value, unit, and sub appear below

#### Scenario: annotator strip renders three cards including the continue card

- **GIVEN** the dashboard summary has loaded successfully for an `annotator`
- **WHEN** the stat strip renders
- **THEN** three cards are visible in a three-column grid
- **AND** the first card is the continue-work card
- **AND** the remaining two are the Assigned tasks and Completion % stat cards

#### Scenario: empty sub renders no context line

- **GIVEN** a stat item has `sub` equal to the empty string
- **WHEN** the card renders
- **THEN** no context line is rendered below the value

#### Scenario: fraction value renders as a fraction

- **GIVEN** a stat item has `value` of `"3/5"`
- **WHEN** the card renders
- **THEN** the numerator `3` is rendered emphasised and the denominator `5` de-emphasised, separated by a slash

#### Scenario: stat cards render skeleton while loading

- **GIVEN** the dashboard query is in-flight
- **WHEN** the stat strip renders
- **THEN** skeleton placeholder cards are visible (no spinner, no empty boxes)

#### Scenario: warn direction renders amber indicator

- **GIVEN** a stat item has `dir: "warn"` (e.g., "Pending approvals")
- **WHEN** the card renders
- **THEN** the delta indicator is amber, not green

### Requirement: Secondary Metrics Panel

The dashboard page SHALL render a secondary panel to the right of the activity panel (two-column grid on desktop, 16px gap). The top section SHALL display: `sideTop` title and `sideMeta` label stacked vertically (title above, meta below with 4px and 16px margins respectively), `big` + `bigUnit` as the primary metric, a horizontal progress bar (height 8px) filled to `bar` percent using the brand primary colour, and three `sideMetrics` displayed as an inline flex row (space-between) with each metric showing `k` label and `v` value in JetBrains Mono.

Below the top section, if `sideRows` is non-empty, a bottom section SHALL render showing `sideBot` as the sub-header followed by a mini bar chart where each row shows a colour-coded bar (height 6px) scaled to `pct` and a label + value.

For the annotator dataset-readiness panel, each `sideRows` entry SHALL represent one active entity type's progress toward the per-type threshold: `pct` SHALL be that type's progress toward the threshold rather than its share of the tenant-wide total, and `val` SHALL show the type's count against the threshold. Row colour SHALL reflect progress rather than being uniform, so a starved entity type is visually distinguishable from a satisfied one. The panel SHALL cap the number of rendered rows and, when types are omitted, SHALL indicate how many remain.

When types are omitted the panel SHALL offer a control to reveal them. Activating that control SHALL expand the panel in place to render every entity type, and the control SHALL then offer to collapse back to the capped list. The expanded state SHALL be local to the panel — it SHALL NOT persist across reloads and SHALL NOT affect any other card. When no types are omitted the control SHALL NOT be rendered.

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

#### Scenario: readiness rows show progress toward the per-type threshold

- **GIVEN** the annotator readiness panel receives an entity type with 100 spans against a threshold of 200
- **WHEN** the mini bar renders
- **THEN** the bar is filled to 50%
- **AND** the row value conveys 100 against the threshold of 200

#### Scenario: starved and satisfied entity types are visually distinct

- **GIVEN** the readiness panel receives one entity type at 0% progress and another at 100%
- **WHEN** the rows render
- **THEN** the two bars do not share the same colour

#### Scenario: overflow of entity types is indicated

- **GIVEN** the tenant has more active entity types than the panel renders
- **WHEN** the readiness panel renders
- **THEN** the rendered rows are the least-progressed types
- **AND** the panel indicates how many further types are not shown
- **AND** a control to view all entity types is offered

#### Scenario: viewing all expands the panel in place

- **GIVEN** the readiness panel is showing 6 of 8 entity types
- **WHEN** the user activates the view-all control
- **THEN** all 8 entity types are rendered
- **AND** the control now offers to collapse back

#### Scenario: collapsing returns the panel to the capped list

- **GIVEN** the readiness panel has been expanded to show all entity types
- **WHEN** the user activates the collapse control
- **THEN** only the capped set of least-progressed types is rendered
- **AND** the count of hidden types is indicated again

#### Scenario: no view-all control when nothing is hidden

- **GIVEN** the tenant has fewer entity types than the panel's row cap
- **WHEN** the readiness panel renders
- **THEN** every entity type is rendered
- **AND** no view-all control is present

#### Scenario: sideRows mini bars render correct colours

- **GIVEN** `sideRows[0].c` is `"oklch(0.64 0.15 25)"`
- **WHEN** the mini bar renders
- **THEN** the bar background colour matches the specified CSS colour string
