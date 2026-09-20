Baseline note: both requirements below are modified from their `tenant-postgresql-data-plane` versions, which must archive before this change.

## MODIFIED Requirements

### Requirement: Tenant-admin-managed finite Azure connections

The system SHALL allow only an authenticated tenant administrator to create, read, update, test, activate, pause, replace, or retire a tenant-bound Azure Blob Storage source, Azure Blob content-store, Azure Database for PostgreSQL (read-only source), or Azure Database for PostgreSQL data-plane connection. The server SHALL derive the owning tenant from authenticated context, SHALL accept only the four approved provider types (`azure_blob`, `azure_blob_content_store`, `azure_postgresql`, `azure_postgresql_data_plane`) and typed non-sensitive configuration with a secret reference, and SHALL return and record only finite safe lifecycle/test outcome classes and correlation metadata. The `azure_postgresql_data_plane` provider SHALL be accepted only for a tenant whose data-plane mode is `tenant_owned`. The `azure_blob_content_store` provider SHALL be accepted for a tenant of any data-plane mode.

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

#### Scenario: Platform-plane tenant may create a content-store connection

- **GIVEN** an authenticated tenant administrator of a tenant with data-plane mode `platform`
- **WHEN** the administrator creates an `azure_blob_content_store` draft
- **THEN** the system SHALL accept it
- **AND** the connection row SHALL be bound to the authenticated tenant

#### Scenario: An unapproved provider is rejected

- **GIVEN** an authenticated tenant administrator
- **WHEN** the administrator submits a draft naming a provider outside the four approved types
- **THEN** the system SHALL reject it with a finite safe validation error
- **AND** no connection row SHALL be created

### Requirement: Safe activation and concurrent capability limits

The system SHALL activate an approved Azure connection only after finite typed configuration validation, resolvable secret reference, successful TLS-validated secure test, required customer network evidence, and applicable governance approval. The system SHALL permit at most one active Azure Blob document source, one active Azure Blob content store, one active read-only Azure PostgreSQL connection, and one active Azure PostgreSQL data-plane connection per tenant concurrently; unmet prerequisites SHALL leave the connection inactive and expose only a finite safe blocking outcome class.

For `azure_postgresql_data_plane`, the secure test SHALL additionally verify, each as a finite outcome class: server major version 16 or later; the `vector` extension is installed or creatable; the connecting role can create a schema in the configured database; the chat query role can be created or already exists and can be granted; and the target `tenant_<id>` schema is absent, empty, or carries the store identity recorded for this tenant. A read-only `azure_postgresql` connection and an `azure_postgresql_data_plane` connection of the same tenant SHALL NOT share the same secret reference.

For `azure_blob_content_store`, the secure test SHALL additionally verify, each as a finite outcome class: the configured container exists and is reachable over a TLS-validated connection; the credential can write, read back, and delete an object under the platform's own prefix, verified as a round trip whose read returns the identical bytes written; the scratch object used for that round trip is removed on every terminal path; and a lifecycle expiry rule scoped to the working prefix is present with a lifetime no greater than the configured working-copy lifetime. An `azure_blob` source connection and an `azure_blob_content_store` connection of the same tenant SHALL NOT share the same secret reference and SHALL NOT name the same container.

#### Scenario: Failed prerequisite blocks activation

- **GIVEN** a tenant Azure connection draft whose test, secret resolution, or required evidence is absent or failed
- **WHEN** a tenant administrator requests activation
- **THEN** the system SHALL keep the connection inactive
- **AND** the response SHALL expose only a safe blocking outcome class

#### Scenario: Independent approved connections activate concurrently

- **GIVEN** a `tenant_owned` tenant has activation-ready Azure Blob source, Azure Blob content-store, read-only Azure PostgreSQL, and Azure PostgreSQL data-plane drafts
- **WHEN** the tenant administrator activates all four connections
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

#### Scenario: Content-store test reports a read-only credential

- **GIVEN** an `azure_blob_content_store` draft whose credential cannot write to the configured container
- **WHEN** the tenant administrator tests the connection
- **THEN** the outcome SHALL be failed with a finite safe reason class indicating the credential is not write-capable
- **AND** activation SHALL be blocked

#### Scenario: Content-store test leaves no scratch object behind

- **GIVEN** an `azure_blob_content_store` draft whose container is writable
- **WHEN** the tenant administrator tests the connection and the test completes by any terminal path
- **THEN** no scratch object from the round-trip check SHALL remain in the container

#### Scenario: Content-store test reports a missing expiry rule

- **GIVEN** an `azure_blob_content_store` draft whose container carries no lifecycle rule scoped to the working prefix
- **WHEN** the tenant administrator tests the connection
- **THEN** the outcome SHALL be failed with a finite safe reason class naming the missing expiry rule
- **AND** activation SHALL be blocked

#### Scenario: Shared secret reference between Blob source and content store is rejected

- **GIVEN** an active `azure_blob` source connection using secret reference R
- **WHEN** a tenant administrator saves an `azure_blob_content_store` draft using R
- **THEN** the system SHALL reject it with finite safe code `SECRET_REFERENCE_SHARED_ACROSS_PURPOSES`
