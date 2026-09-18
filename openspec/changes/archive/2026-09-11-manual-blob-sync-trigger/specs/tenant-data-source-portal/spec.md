## ADDED Requirements

### Requirement: Manual sync-now control

The portal SHALL provide a "Sync now" control on the connection detail Sync activity panel for Azure Blob connections that calls `POST /api/v1/data-sources/{connection_id}/sync` with a fresh `Idempotency-Key` per click. The control SHALL be enabled only for connections with `active` status, SHALL present pending, enqueued-success, lease-held (sync already running), blocked (inactive), and safe-error states without exposing configuration values, secret references, endpoints, provider diagnostics, SQL, or tenant content, and SHALL refresh the displayed last-run status after a successful trigger. PostgreSQL connections SHALL NOT present the control, consistent with the existing schedule exemption.

#### Scenario: Administrator triggers a manual sync from the detail view

- **GIVEN** an authenticated tenant administrator viewing an active Azure Blob connection detail
- **WHEN** the administrator clicks "Sync now"
- **THEN** the portal SHALL call the manual sync action with a fresh `Idempotency-Key`
- **AND** it SHALL present the pending state followed by the safe enqueued-success state and a refreshed last-run status.

#### Scenario: Sync-now is unavailable for inactive connections

- **GIVEN** a Blob connection without an active lifecycle state
- **WHEN** the administrator views the Sync activity panel
- **THEN** the "Sync now" control SHALL be disabled with a safe blocked notice
- **AND** no sync request SHALL be sent.

#### Scenario: Sync-now is absent for PostgreSQL connections

- **GIVEN** a tenant Azure PostgreSQL connection detail view
- **WHEN** the administrator views the Sync activity panel
- **THEN** the portal SHALL NOT present the "Sync now" control
- **AND** it SHALL retain the existing schedule-exemption notice.

#### Scenario: Lease-held manual sync surfaces a safe retry notice

- **GIVEN** a Blob connection with a sync run already in progress
- **WHEN** the administrator clicks "Sync now" and the backend reports the lease-held outcome
- **THEN** the portal SHALL present a safe "sync already running" notice
- **AND** it SHALL NOT expose provider diagnostics or raw errors.
