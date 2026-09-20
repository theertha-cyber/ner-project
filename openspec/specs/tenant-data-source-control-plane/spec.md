# tenant-data-source-control-plane Specification

## Purpose
TBD - created by archiving change cap-2-tenant-scoped-connection-control-plane. Update Purpose after archive.
## Requirements
### Requirement: Tenant-admin-managed finite Azure connections

The system SHALL allow only an authenticated tenant administrator to create, read, update, test, activate, pause, replace, or retire a tenant-bound Azure Blob Storage, Azure Database for PostgreSQL (read-only source), or Azure Database for PostgreSQL data-plane connection. The server SHALL derive the owning tenant from authenticated context, SHALL accept only the three approved provider types (`azure_blob`, `azure_postgresql`, `azure_postgresql_data_plane`) and typed non-sensitive configuration with a secret reference, and SHALL return and record only finite safe lifecycle/test outcome classes and correlation metadata. The `azure_postgresql_data_plane` provider SHALL be accepted only for a tenant whose data-plane mode is `tenant_owned`.

#### Scenario: Tenant administrator tests a supported Azure Blob draft

- **GIVEN** an authenticated tenant administrator submits a valid Azure Blob draft for their tenant
- **WHEN** the administrator requests a connection test
- **THEN** the server SHALL bind the operation to the authenticated tenant and record a finite safe outcome with correlation metadata
- **AND** the response and evidence SHALL contain no credential, endpoint, provider-error payload, or tenant content

#### Scenario: Non-administrator is denied

- **GIVEN** an authenticated user without the tenant-administrator role
- **WHEN** the user requests any Azure connection lifecycle operation
- **THEN** the system SHALL deny the operation
- **AND** no connection state SHALL change

#### Scenario: Cross-tenant connection access is denied

- **GIVEN** a connection owned by tenant A and an authenticated tenant administrator for tenant B
- **WHEN** the tenant B administrator requests that connection
- **THEN** the system SHALL deny access
- **AND** it SHALL not disclose connection metadata or lifecycle evidence

#### Scenario: Platform-plane tenant cannot create a data-plane connection

- **GIVEN** an authenticated tenant administrator of a tenant with data-plane mode `platform`
- **WHEN** the administrator creates an `azure_postgresql_data_plane` draft
- **THEN** the system SHALL reject it with finite safe code `DATA_PLANE_NOT_TENANT_OWNED`
- **AND** no connection row SHALL be created

### Requirement: Safe activation and concurrent capability limits

The system SHALL activate an approved Azure connection only after finite typed configuration validation, resolvable secret reference, successful TLS-validated secure test, required customer network evidence, and applicable governance approval. The system SHALL permit at most one active Azure Blob document source, one active read-only Azure PostgreSQL connection, and one active Azure PostgreSQL data-plane connection per tenant concurrently; unmet prerequisites SHALL leave the connection inactive and expose only a finite safe blocking outcome class.

For `azure_postgresql_data_plane`, the secure test SHALL additionally verify, each as a finite outcome class: server major version 16 or later; the `vector` extension is installed or creatable; the connecting role can create a schema in the configured database; the chat query role can be created or already exists and can be granted; and the target `tenant_<id>` schema is absent, empty, or carries the store identity recorded for this tenant. A read-only `azure_postgresql` connection and an `azure_postgresql_data_plane` connection of the same tenant SHALL NOT share the same secret reference.

#### Scenario: Failed prerequisite blocks activation

- **GIVEN** a tenant Azure connection draft whose test, secret resolution, or required evidence is absent or failed
- **WHEN** a tenant administrator requests activation
- **THEN** the system SHALL keep the connection inactive
- **AND** the response SHALL expose only a safe blocking outcome class

#### Scenario: Independent approved connections activate concurrently

- **GIVEN** a `tenant_owned` tenant has activation-ready Azure Blob, read-only Azure PostgreSQL, and Azure PostgreSQL data-plane drafts
- **WHEN** the tenant administrator activates all three connections
- **THEN** the system SHALL permit one active connection of each approved provider class
- **AND** platform upload SHALL remain available once the data plane is `ready`

#### Scenario: Duplicate active provider is rejected

- **GIVEN** a tenant already has an active Azure Blob connection
- **WHEN** a tenant administrator activates another Azure Blob connection
- **THEN** the system SHALL reject the activation with a finite safe outcome class
- **AND** the existing active connection SHALL remain unchanged

#### Scenario: Data-plane test reports a missing vector extension

- **GIVEN** an `azure_postgresql_data_plane` draft for a server where `VECTOR` is not allow-listed
- **WHEN** the tenant administrator tests the connection
- **THEN** the outcome SHALL be failed with reason class `vector_extension_unavailable`
- **AND** activation SHALL be blocked

#### Scenario: Shared secret reference between source and data plane is rejected

- **GIVEN** an active read-only `azure_postgresql` connection using secret reference R
- **WHEN** a tenant administrator saves an `azure_postgresql_data_plane` draft using R
- **THEN** the system SHALL reject it with finite safe code `SECRET_REFERENCE_SHARED_ACROSS_PURPOSES`

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

### Requirement: Data-plane connection pause and retirement drive data-plane status

Pausing a tenant's active `azure_postgresql_data_plane` connection SHALL set the tenant's data-plane status to `paused`; resuming by re-activation SHALL restore `ready` when the store identity and revision checks pass. Retiring it without an activated same-store replacement SHALL set the tenant's data-plane status to `store_retired`, which is terminal for content access. Retirement SHALL NOT drop, truncate, or delete any object in the tenant store, and the response SHALL state that content remaining in the tenant store is the customer's to delete.

#### Scenario: Pausing the data-plane connection stops content access

- **GIVEN** a `ready` residency tenant
- **WHEN** the tenant administrator pauses its data-plane connection
- **THEN** the tenant's data-plane status SHALL be `paused`
- **AND** content routes SHALL return 409 `TENANT_DATA_PLANE_NOT_READY` with status class `paused`

#### Scenario: Retirement leaves the tenant store untouched

- **GIVEN** a paused data-plane connection with no replacement
- **WHEN** the tenant administrator retires it with confirmation
- **THEN** the tenant's data-plane status SHALL be `store_retired`
- **AND** no DDL or DML SHALL be executed against the tenant store
