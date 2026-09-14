## ADDED Requirements

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
