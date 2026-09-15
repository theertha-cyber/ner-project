## ADDED Requirements

### Requirement: Manual Blob sync trigger action

The system SHALL expose `POST /api/v1/data-sources/{connection_id}/sync` allowing only an authenticated tenant administrator to enqueue a manual Azure Blob synchronization for a connection owned by their tenant. The server SHALL derive the owning tenant from authenticated context, SHALL reject non-Blob providers and connections without an active lifecycle state with a finite safe outcome class, SHALL enqueue the durable `blob_sync_run` job with an identity-only payload (tenant, connection, `manual` trigger class) through the existing broker queue, and SHALL return and record only finite safe outcome classes, identifiers, and correlation timestamps. Every mutation SHALL require an `Idempotency-Key` (1–128 printable ASCII) following the existing control-plane replay convention.

#### Scenario: Administrator triggers a manual sync on an active Blob connection

- **GIVEN** an authenticated tenant administrator with an active Azure Blob connection owned by their tenant
- **WHEN** the administrator calls `POST /api/v1/data-sources/{connection_id}/sync` with a fresh `Idempotency-Key`
- **THEN** the server SHALL enqueue the durable `blob_sync_run` job with trigger class `manual`
- **AND** the response SHALL contain only the finite trigger outcome, identifiers, and correlation timestamps.

#### Scenario: Manual sync on an inactive connection is rejected safely

- **GIVEN** a tenant Blob connection without an active lifecycle state
- **WHEN** a tenant administrator calls the manual sync action for that connection
- **THEN** the system SHALL reject the request with a finite safe outcome class
- **AND** no sync job SHALL be enqueued.

#### Scenario: Manual sync on a PostgreSQL connection is rejected

- **GIVEN** a tenant Azure PostgreSQL connection
- **WHEN** a tenant administrator calls the manual sync action for that connection
- **THEN** the system SHALL reject the request with a finite safe outcome class
- **AND** no sync job SHALL be enqueued.

#### Scenario: Non-administrator is denied

- **GIVEN** an authenticated user without the tenant-administrator role
- **WHEN** the user calls the manual sync action
- **THEN** the system SHALL deny the operation
- **AND** no sync job SHALL be enqueued.

#### Scenario: Cross-tenant manual sync is denied

- **GIVEN** a connection owned by tenant A and an authenticated tenant administrator for tenant B
- **WHEN** the tenant B administrator calls the manual sync action for that connection
- **THEN** the system SHALL deny access with the connection-not-found outcome class
- **AND** it SHALL NOT disclose connection metadata or lifecycle evidence.

#### Scenario: Idempotent manual sync replay renders the safe result

- **GIVEN** a manual sync already accepted under an `Idempotency-Key`
- **WHEN** the same key and body are submitted again
- **THEN** the server SHALL replay the original safe result with a replay marker
- **AND** no duplicate sync job SHALL be enqueued for the replay.
