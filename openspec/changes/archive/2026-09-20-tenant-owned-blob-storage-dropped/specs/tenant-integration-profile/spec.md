Baseline note: the two requirements below are modified from their `tenant-postgresql-data-plane` versions, which must archive before this change.

## MODIFIED Requirements

### Requirement: Only platform default adapters are executable in this change

The system SHALL permit a profile to *record* adapter selection from the declared supported set and SHALL treat platform defaults as executable for all providers except the approved Azure Blob Storage, Azure Blob content-store, Azure Database for PostgreSQL, and Azure Database for PostgreSQL data-plane tenant-bound connections governed by `tenant-data-source-control-plane`. An approved Azure connection SHALL be executable only after its tenant-admin lifecycle activation gate succeeds; any other non-default adapter selection SHALL be rejected as recorded but unsupported. The presence of a recordable value SHALL NOT be taken as a claim that its adapter exists.

The selections `relational_adapter = tenant_postgresql` and `index_adapter = tenant_pgvector` SHALL be executable only together, only for a tenant whose data-plane mode is `tenant_owned`, and only while that tenant holds an active `azure_postgresql_data_plane` connection and its data-plane status is `ready`. An active read-only `azure_postgresql` connection SHALL NOT make either selection executable. For a `tenant_owned` tenant these two selections SHALL be set automatically at tenant creation and SHALL NOT be changeable to the platform defaults.

The selection `content_store_adapter = tenant_azure_blob` SHALL be executable while, and only while, the tenant holds an active `azure_blob_content_store` connection. It SHALL be independent of the tenant's data-plane mode: a tenant whose data-plane mode is `platform` SHALL be permitted to select and execute it. An active read-only `azure_blob` source connection SHALL NOT make it executable. The selection `content_store_adapter = tenant_s3` SHALL remain recorded but unsupported.

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

#### Scenario: Ingestion uses executable adapters

- **GIVEN** a tenant whose profile records a non-default source selection that is not an active approved Azure Blob connection
- **WHEN** a document is ingested for that tenant
- **THEN** the platform upload source SHALL serve it
- **AND** the recorded non-default source selection SHALL have no effect

#### Scenario: A read-only PostgreSQL source does not relocate the tenant

- **GIVEN** a `platform` tenant with an active read-only `azure_postgresql` connection and a profile recording `relational_adapter = tenant_postgresql`
- **WHEN** the tenant's relational selection is resolved
- **THEN** it SHALL NOT be executable
- **AND** the tenant's schema SHALL continue to be served by the platform engine

#### Scenario: Residency selections execute only when the data plane is ready

- **GIVEN** a `tenant_owned` tenant with an active `azure_postgresql_data_plane` connection whose data-plane status is `provisioning`
- **WHEN** `relational_adapter` is resolved
- **THEN** it SHALL NOT be executable until the status is `ready`

#### Scenario: A content-store selection executes with an active content-store connection

- **GIVEN** a tenant with an active `azure_blob_content_store` connection and a profile recording `content_store_adapter = tenant_azure_blob`
- **WHEN** the content-store selection is resolved
- **THEN** it SHALL be executable

#### Scenario: A read-only Blob source does not make the content store executable

- **GIVEN** a tenant with an active `azure_blob` source connection and no `azure_blob_content_store` connection, recording `content_store_adapter = tenant_azure_blob`
- **WHEN** the content-store selection is resolved
- **THEN** it SHALL NOT be executable
- **AND** the platform content store SHALL serve that tenant's bytes

#### Scenario: A platform-plane tenant may execute a tenant content store

- **GIVEN** a tenant whose data-plane mode is `platform` with an active `azure_blob_content_store` connection and `content_store_adapter = tenant_azure_blob`
- **WHEN** the content-store selection is resolved
- **THEN** it SHALL be executable
- **AND** the tenant's relational data SHALL continue to be served by the platform engine

#### Scenario: A tenant S3 content store remains unsupported

- **GIVEN** a profile recording `content_store_adapter = tenant_s3`
- **WHEN** the selection is resolved
- **THEN** it SHALL NOT be executable whatever connections the tenant holds

### Requirement: Tenant-owned data plane forbids platform-retained originals

For a tenant whose data-plane mode is `tenant_owned` and which holds no active `azure_blob_content_store` connection, the integration profile `retention_mode` SHALL be `ephemeral` or `source_only`. Setting `platform_blob` SHALL be rejected with finite safe code `RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE`, and tenant creation with `tenant_owned` SHALL default the profile to `ephemeral`. Activation of an `azure_postgresql_data_plane` connection SHALL be blocked with reason class `retention_mode_not_permitted` if the profile records `platform_blob` and no content-store connection is active.

The prohibition exists because such a tenant has no tenant-side store in which to retain an original. Where that condition no longer holds — the tenant holds an active `azure_blob_content_store` connection and records `content_store_adapter = tenant_azure_blob`, so a retained original resides in the tenant's own container — `platform_blob` retention SHALL be permitted and SHALL NOT block data-plane activation.

Retiring or pausing the content-store connection of a `tenant_owned` tenant recording `platform_blob` SHALL be rejected with a finite safe reason class until its `retention_mode` is changed to `ephemeral` or `source_only`, so that the tenant cannot be left recording a retention mode its configuration can no longer honour.

#### Scenario: Platform blob retention is rejected for a residency tenant without a content store

- **GIVEN** a `tenant_owned` tenant with no active `azure_blob_content_store` connection
- **WHEN** its profile `retention_mode` is set to `platform_blob`
- **THEN** the write SHALL be rejected with `RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE`

#### Scenario: Residency tenant defaults to ephemeral

- **GIVEN** a System Admin creates a tenant with data-plane mode `tenant_owned`
- **WHEN** its integration profile is read
- **THEN** `retention_mode` SHALL be `ephemeral`

#### Scenario: Platform blob retention is permitted once a tenant content store is active

- **GIVEN** a `tenant_owned` tenant with an active `azure_blob_content_store` connection and `content_store_adapter = tenant_azure_blob`
- **WHEN** its profile `retention_mode` is set to `platform_blob`
- **THEN** the write SHALL succeed
- **AND** a document ingested afterwards SHALL have its original retained in the tenant's container

#### Scenario: Data-plane activation is not blocked by permitted platform blob retention

- **GIVEN** a `tenant_owned` tenant recording `platform_blob` with an active content-store connection
- **WHEN** an `azure_postgresql_data_plane` connection is activated
- **THEN** activation SHALL NOT be blocked with reason class `retention_mode_not_permitted`

#### Scenario: Retiring the content store is refused while platform blob retention is recorded

- **GIVEN** a `tenant_owned` tenant recording `platform_blob` with an active content-store connection
- **WHEN** the tenant administrator attempts to retire that connection
- **THEN** the system SHALL reject the retirement with a finite safe reason class
- **AND** the connection SHALL remain active
