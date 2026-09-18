## MODIFIED Requirements

### Requirement: Only platform default adapters are executable in this change

The system SHALL permit a profile to *record* adapter selection from the declared supported set and SHALL treat platform defaults as executable for all providers except the approved Azure Blob Storage, Azure Database for PostgreSQL, and Azure Database for PostgreSQL data-plane tenant-bound connections governed by `tenant-data-source-control-plane`. An approved Azure connection SHALL be executable only after its tenant-admin lifecycle activation gate succeeds; any other non-default adapter selection SHALL be rejected as recorded but unsupported. The presence of a recordable value SHALL NOT be taken as a claim that its adapter exists.

The selections `relational_adapter = tenant_postgresql` and `index_adapter = tenant_pgvector` SHALL be executable only together, only for a tenant whose data-plane mode is `tenant_owned`, and only while that tenant holds an active `azure_postgresql_data_plane` connection and its data-plane status is `ready`. An active read-only `azure_postgresql` connection SHALL NOT make either selection executable. For a `tenant_owned` tenant these two selections SHALL be set automatically at tenant creation and SHALL NOT be changeable to the platform defaults.

#### Scenario: A non-default selection may be recorded

- **GIVEN** a profile in `draft`
- **WHEN** its index adapter is set to a recorded-but-unsupported value
- **THEN** the write SHALL succeed
- **AND** the profile SHALL remain in `draft`

#### Scenario: A non-default selection cannot be activated

- **GIVEN** a `draft` profile selecting a non-default relational or index adapter other than an activation-ready approved Azure connection
- **WHEN** activation is attempted
- **THEN** activation SHALL be rejected with a finite safe unsupported-selection reason
- **AND** the profile SHALL NOT enter `active`

#### Scenario: An approved Azure connection can execute after activation

- **GIVEN** a tenant-bound Azure Blob or Azure PostgreSQL connection has passed the control-plane activation gate
- **WHEN** its approved capability is resolved for the authenticated owning tenant
- **THEN** the connection SHALL be executable for its approved purpose
- **AND** no other recorded non-default selection SHALL become executable

#### Scenario: Ingestion always uses executable adapters

- **GIVEN** a tenant whose profile records a non-default source selection that is not an active approved Azure Blob connection
- **WHEN** a document is ingested for that tenant
- **THEN** the platform upload source and the platform content store SHALL serve it
- **AND** the recorded non-default selection SHALL have no effect

#### Scenario: A read-only PostgreSQL source does not relocate the tenant

- **GIVEN** a `platform` tenant with an active read-only `azure_postgresql` connection and a profile recording `relational_adapter = tenant_postgresql`
- **WHEN** the tenant's relational selection is resolved
- **THEN** it SHALL NOT be executable
- **AND** the tenant's schema SHALL continue to be served by the platform engine

#### Scenario: Residency selections execute only when the data plane is ready

- **GIVEN** a `tenant_owned` tenant with an active `azure_postgresql_data_plane` connection whose data-plane status is `provisioning`
- **WHEN** `relational_adapter` is resolved
- **THEN** it SHALL NOT be executable until the status is `ready`

## ADDED Requirements

### Requirement: Tenant-owned data plane forbids platform-retained originals

For a tenant whose data-plane mode is `tenant_owned`, the integration profile `retention_mode` SHALL be `ephemeral` or `source_only`. Setting `platform_blob` SHALL be rejected with finite safe code `RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE`, and tenant creation with `tenant_owned` SHALL default the profile to `ephemeral`. Activation of an `azure_postgresql_data_plane` connection SHALL be blocked with reason class `retention_mode_not_permitted` if the profile records `platform_blob`.

#### Scenario: Platform blob retention is rejected for a residency tenant

- **GIVEN** a `tenant_owned` tenant
- **WHEN** its profile `retention_mode` is set to `platform_blob`
- **THEN** the write SHALL be rejected with `RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE`

#### Scenario: Residency tenant defaults to ephemeral

- **GIVEN** a System Admin creates a tenant with data-plane mode `tenant_owned`
- **WHEN** its integration profile is read
- **THEN** `retention_mode` SHALL be `ephemeral`
