# audit-log Specification

## Purpose
TBD - created by archiving change audit-log-page. Update Purpose after archive.
## Requirements
### Requirement: Persist Audit Events

The system SHALL persist an audit event record for each tracked business action. Each record SHALL contain: a unique ID, the actor's email, the actor's role, the action name, the target resource identifier, a kind classifier, and a non-nullable timestamp.

The following kinds SHALL be recognized: `create`, `approve`, `promote`, `complete`, `run`, `reject`, `update`.

#### Scenario: Audit event recorded on training job submission

- **GIVEN** a tenant_admin submits a training job
- **WHEN** the job submission is persisted
- **THEN** an audit event with kind `create` and action `training_job.submit` SHALL be recorded

#### Scenario: Audit event recorded on training job approval

- **GIVEN** a system_admin approves a pending training job
- **WHEN** the approval action completes
- **THEN** an audit event with kind `approve` and action `training_job.approve` SHALL be recorded

#### Scenario: Audit event recorded on model promotion

- **GIVEN** a tenant_admin promotes a model version to production
- **WHEN** the promotion action completes
- **THEN** an audit event with kind `promote` and action `model_version.promote` SHALL be recorded

#### Scenario: Audit event recorded on tenant deactivation

- **GIVEN** a system_admin deactivates a tenant
- **WHEN** the deactivation action completes
- **THEN** an audit event with kind `reject` and action `tenant.deactivate` SHALL be recorded

#### Scenario: Audit event recorded on entity type update

- **GIVEN** a tenant_admin updates an entity definition
- **WHEN** the update action completes
- **THEN** an audit event with kind `update` and action `entity_type.update` SHALL be recorded

### Requirement: List Audit Events via API

The system SHALL expose `GET /api/v1/admin/audit-log` returning a paginated, reverse-chronological list of audit events. The endpoint SHALL require `system_admin` role. The response SHALL include `events`, `total`, `page`, and `per_page` fields.

#### Scenario: System admin fetches audit log

- **GIVEN** audit events exist in the database
- **WHEN** a system_admin requests `GET /api/v1/admin/audit-log`
- **THEN** the response SHALL contain a paginated list of events ordered by `created_at` DESC
- **AND** each event SHALL include `id`, `actor`, `role`, `action`, `target`, `kind`, and `created_at` fields

#### Scenario: Tenant admin is denied access

- **GIVEN** a tenant_admin is authenticated
- **WHEN** they request `GET /api/v1/admin/audit-log`
- **THEN** the response SHALL be `403 Forbidden`

### Requirement: Render Audit Log Page

The system SHALL render an audit log page at `/audit` when the authenticated user has the `system_admin` role. The page SHALL display a timeline list matching the mockup in `docs/NER Platform.html` exactly.

#### Scenario: Timeline row content

- **GIVEN** audit events exist
- **WHEN** the audit log page renders
- **THEN** each event SHALL display: a colored dot, the action name, a kind badge (color-coded pill), the target resource, the actor email, the actor role, and a relative or formatted timestamp

#### Scenario: Kind badge colors

- **GIVEN** the audit log page is displayed
- **WHEN** viewing events of different kinds
- **THEN** each kind SHALL have a distinct badge color matching the mockup:
  - `create` → blue (info)
  - `approve` → green (good)
  - `promote` → orange (primary)
  - `complete` → green (good)
  - `run` → blue (info)
  - `reject` → red (bad)
  - `update` → yellow (warn)

#### Scenario: Empty state

- **GIVEN** no audit events exist
- **WHEN** the audit log page renders
- **THEN** the page SHALL display a `0 events` count and an empty timeline

### Requirement: Audit Log Endpoint Tenant Filtering

The `GET /api/v1/admin/audit-log` endpoint SHALL accept an optional `tenant_id` query parameter. When `tenant_id` is omitted or empty, the endpoint SHALL return events for all tenants exactly as it does today (no behavior change). When `tenant_id` is supplied, the endpoint SHALL return only audit events whose `tenant_id` column equals the supplied value, with `total` reflecting the filtered count and results still ordered by `created_at` descending, paginated by the existing `page`/`per_page` parameters.

#### Scenario: No tenant filter supplied

- **GIVEN** an authenticated System Admin and audit events across multiple tenants
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?page=1&per_page=50` with no `tenant_id`
- **THEN** the response SHALL include events from all tenants
- **AND** `total` SHALL equal the total count of all audit events

#### Scenario: Tenant filter supplied

- **GIVEN** an authenticated System Admin, tenant `tid-123` with 5 audit events, and other tenants with additional events
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?tenant_id=tid-123&page=1&per_page=50`
- **THEN** the response SHALL include only the 5 events belonging to `tid-123`
- **AND** `total` SHALL equal `5`
- **AND** events SHALL be ordered by `created_at` descending

#### Scenario: Tenant filter with no matching events

- **GIVEN** an authenticated System Admin and tenant `tid-456` with zero audit events
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?tenant_id=tid-456`
- **THEN** the response SHALL include an empty `events` array
- **AND** `total` SHALL equal `0`

### Requirement: Audit Log Page Tenant Filter UI

The System Admin `/audit` page SHALL display a searchable tenant filter above the audit event list, near the page title/metadata. The filter's default and first option SHALL be "All Tenants". Every existing tenant returned by `GET /api/v1/admin/tenants` SHALL appear as an option below it. Selecting a tenant SHALL refresh the displayed audit events to that tenant's events only, using the tenant-filtered endpoint request, and SHALL reset pagination to page 1. Selecting "All Tenants" after a tenant was selected SHALL restore the full, unfiltered chronological audit history. The selected tenant SHALL be retained in page state for the duration of the page visit (no persistence across reload/navigation is required).

#### Scenario: Default view shows all tenants

- **GIVEN** an authenticated System Admin navigating to `/audit` for the first time in this session
- **WHEN** the page loads
- **THEN** the tenant filter SHALL show "All Tenants" as the selected value
- **AND** the event list SHALL show events from all tenants, most recent first

#### Scenario: Filtering to a specific tenant

- **GIVEN** an authenticated System Admin on `/audit` with the filter set to "All Tenants", and tenant "Acme Corp" exists with audit events
- **WHEN** the System Admin selects "Acme Corp" from the tenant filter
- **THEN** the event list SHALL refresh to show only "Acme Corp" events
- **AND** pagination SHALL reset to page 1
- **AND** chronological ordering (most recent first) SHALL be preserved

#### Scenario: Returning to All Tenants

- **GIVEN** an authenticated System Admin on `/audit` with the filter set to "Acme Corp"
- **WHEN** the System Admin selects "All Tenants" from the filter
- **THEN** the event list SHALL refresh to show the complete, unfiltered audit history
- **AND** pagination SHALL reset to page 1

#### Scenario: Empty state for a tenant with no audit events

- **GIVEN** an authenticated System Admin on `/audit`, and tenant "New Co" exists with zero audit events
- **WHEN** the System Admin selects "New Co" from the tenant filter
- **THEN** the page SHALL display an empty-state message indicating no audit events exist for the selected tenant
- **AND** SHALL NOT display pagination controls

#### Scenario: Tenant filter is searchable

- **GIVEN** an authenticated System Admin on `/audit` with more than one tenant available in the filter
- **WHEN** the System Admin types a partial tenant name into the filter
- **THEN** the dropdown SHALL narrow its visible options to tenants matching the typed text

