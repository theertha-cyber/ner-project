## ADDED Requirements

### Requirement: Tenant-admin-managed finite Azure connections

The system SHALL allow only an authenticated tenant administrator to create, read, update, test, activate, pause, replace, or retire a tenant-bound Azure Blob Storage or Azure Database for PostgreSQL connection. The server SHALL derive the owning tenant from authenticated context, SHALL accept only the two approved provider types and typed non-sensitive configuration with a secret reference, and SHALL return and record only finite safe lifecycle/test outcome classes and correlation metadata.

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

### Requirement: Safe activation and concurrent capability limits

The system SHALL activate an approved Azure connection only after finite typed configuration validation, resolvable secret reference, successful TLS-validated secure test, required customer network evidence, and applicable governance approval. The system SHALL permit at most one active Azure Blob document source and one active Azure PostgreSQL connection per tenant concurrently; unmet prerequisites SHALL leave the connection inactive and expose only a finite safe blocking outcome class.

#### Scenario: Failed prerequisite blocks activation

- **GIVEN** a tenant Azure connection draft whose test, secret resolution, or required evidence is absent or failed
- **WHEN** a tenant administrator requests activation
- **THEN** the system SHALL keep the connection inactive
- **AND** the response SHALL expose only a safe blocking outcome class

#### Scenario: Independent approved connections activate concurrently

- **GIVEN** a tenant has activation-ready Azure Blob and Azure PostgreSQL drafts
- **WHEN** the tenant administrator activates both connections
- **THEN** the system SHALL permit one active connection of each approved provider class
- **AND** platform upload SHALL remain available

#### Scenario: Duplicate active provider is rejected

- **GIVEN** a tenant already has an active Azure Blob connection
- **WHEN** a tenant administrator activates another Azure Blob connection
- **THEN** the system SHALL reject the activation with a finite safe outcome class
- **AND** the existing active connection SHALL remain unchanged
