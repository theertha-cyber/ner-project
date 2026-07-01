## MODIFIED Requirements

### Requirement: Dashboard Summary Endpoint

The gateway SHALL expose `GET /api/v1/dashboard/summary` (requires authentication). The endpoint SHALL return a role-appropriate `DashboardData` JSON object assembled from the tenant's database tables directly (gateway queries tenant schema tables rather than calling downstream services for MVP). The response SHALL include a top-level `sources` object mapping each data domain (`"tenants"`, `"training"`, `"documents"`, `"annotations"`, `"models"`, `"extraction"`) to `true` (data retrieved) or `false` (query failed or not applicable for this role).

Each role handler SHALL accept the `db` session and `tenant_id` parameters and execute real SQL queries against the tenant's schema. Every query SHALL be wrapped in try/catch with independent error handling — a failed query SHALL set the affected fields to `null`, the corresponding `sources.*` flag to `false`, and SHALL NOT fail the entire request.

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
