# Tenant Integration Profile

## Purpose

Defines control-plane storage of per-tenant adapter selection: the typed
allowlisted configuration shape, the status model including an explicit `error`
state, the rule that only platform default adapters are executable, secret
references only (never values), and observability of which adapters served an
ingestion.

---
## Requirements
### Requirement: Per-tenant integration profile in control-plane storage

The system SHALL store, for each tenant, an integration profile recording which document-source, content-store, derived-relational, and index adapters that tenant uses, together with typed non-secret configuration and typed secret references. The profile SHALL be stored in platform control-plane storage (`public`), never in a tenant schema, so that it remains readable when a tenant's own infrastructure is unreachable. The profile is developer-managed platform configuration and is not tenant content.

#### Scenario: Every tenant has a profile

- **GIVEN** a provisioned tenant
- **WHEN** its integration profile is read
- **THEN** a profile SHALL exist
- **AND** its selected adapters SHALL be the platform defaults

#### Scenario: Profiles live in the control plane

- **GIVEN** the migration that creates the profile table
- **WHEN** its target schema is inspected
- **THEN** the table SHALL be created in `public`
- **AND** it SHALL NOT be created in `tenant_template` or any `tenant_%` schema

#### Scenario: A profile is readable when the tenant schema is unavailable

- **GIVEN** a tenant whose schema is renamed or otherwise unreadable
- **WHEN** its integration profile is read
- **THEN** the profile SHALL be returned
- **AND** no error SHALL be raised

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

### Requirement: Typed profile configuration with an allowlisted shape

The system SHALL define, per adapter kind, a closed set of permitted configuration keys and their types, and SHALL define secret material as a distinct typed field whose value SHALL match a secret-reference grammar of the form `<scheme>://<path>`. A profile write SHALL be rejected when it carries a key outside that adapter's declared set, when a value has the wrong type, or when a field declared as a secret reference does not match the reference grammar. The system SHALL NOT attempt to detect credentials by inspecting whether a value looks like a secret.

#### Scenario: An unknown configuration key is rejected

- **GIVEN** a profile write carrying a configuration key not in the declared set for that adapter kind
- **WHEN** the write is performed
- **THEN** it SHALL be rejected with a message naming the unknown key
- **AND** no row SHALL be persisted

#### Scenario: A secret field must hold a reference, not a value

- **GIVEN** a profile write whose secret-reference field carries a literal that does not match the `<scheme>://<path>` grammar
- **WHEN** the write is performed
- **THEN** it SHALL be rejected
- **AND** no row SHALL be persisted

#### Scenario: A valid reference is accepted and stored verbatim

- **GIVEN** a profile write whose secret-reference field matches the grammar
- **WHEN** the write is performed
- **THEN** it SHALL succeed
- **AND** the stored value SHALL be the reference exactly as supplied

#### Scenario: Validation does not depend on value inspection

- **GIVEN** a non-secret configuration field whose declared type is a string
- **WHEN** its value happens to resemble a credential
- **THEN** the write SHALL be accepted on the basis of the declared schema
- **AND** no heuristic rejection SHALL occur

### Requirement: Profile status model

The system SHALL give each profile a status of `draft`, `validated`, `active`, `paused`, `error`, or `retired`, with these permitted transitions: `draft → validated` on a successful validation of the recorded selections and their configuration; `validated → active` on activation; `active → paused` and `paused → active` on operator action; `active → error` and `validated → error` when a required secret reference cannot be resolved or an executable adapter fails its readiness check; `error → validated` on successful revalidation; and any status `→ retired`. A profile SHALL NOT enter `active` from `draft` without passing through `validated`. A `retired` profile SHALL NOT return to any other status.

#### Scenario: A draft profile is not used to serve requests

- **GIVEN** a tenant whose profile is in `draft`
- **WHEN** a document is ingested for that tenant
- **THEN** the platform default adapters SHALL be used
- **AND** the draft selections SHALL have no effect

#### Scenario: Activation from draft is refused

- **GIVEN** a profile in `draft`
- **WHEN** activation is attempted without validation
- **THEN** the transition SHALL be rejected
- **AND** the profile SHALL remain in `draft`

#### Scenario: An unresolvable reference moves the profile to error

- **GIVEN** an `active` profile whose secret reference cannot be resolved
- **WHEN** resolution is attempted
- **THEN** the profile SHALL transition to `error` with a recorded reason
- **AND** the reason SHALL name the reference and its failure class
- **AND** the reason SHALL NOT contain any credential material

#### Scenario: An errored profile recovers only through revalidation

- **GIVEN** a profile in `error`
- **WHEN** activation is attempted directly
- **THEN** the transition SHALL be rejected
- **AND** a successful revalidation SHALL move it to `validated`

#### Scenario: A retired profile is terminal

- **GIVEN** a profile in `retired`
- **WHEN** any transition to another status is attempted
- **THEN** it SHALL be rejected

### Requirement: Profiles hold secret references, never secret values

The integration profile SHALL store only references to secrets. Secret resolution SHALL take both the tenant identity and the reference, and the reference SHALL be read only from that tenant's own profile.

#### Scenario: Administrative reads never return secrets

- **GIVEN** a tenant integration profile containing secret references
- **WHEN** it is returned through any administrative API
- **THEN** the response SHALL contain the references
- **AND** it SHALL NOT contain any resolved credential value

#### Scenario: Resolution is scoped to the owning tenant

- **GIVEN** a secret reference belonging to tenant A
- **WHEN** resolution is attempted with tenant B's identity and that reference
- **THEN** resolution SHALL fail
- **AND** no credential SHALL be returned

#### Scenario: Resolved credentials are never persisted or logged

- **GIVEN** a resolution of any secret reference
- **WHEN** the operation completes
- **THEN** no resolved value SHALL be written to any database row
- **AND** no log record, span attribute, or metric label SHALL contain a resolved value

### Requirement: Profiles are developer-managed

The system SHALL NOT expose profile creation, editing, activation, or retirement to tenant users through any tenant-facing interface, except that an authenticated tenant administrator MAY manage the tenant-bound Azure Blob Storage and Azure Database for PostgreSQL connections through the `tenant-data-source-control-plane` lifecycle. The exception SHALL not grant access to platform-default profile configuration or any other adapter selection.

#### Scenario: Tenant users cannot modify profiles

- **GIVEN** an authenticated user whose role is `tenant_admin`
- **WHEN** they attempt to modify their tenant's platform-default integration profile or an unsupported adapter through any tenant-facing API
- **THEN** the request SHALL be rejected

#### Scenario: Tenant administrators manage only approved Azure connections

- **GIVEN** an authenticated user whose role is `tenant_admin`
- **WHEN** they submit a lifecycle operation for their tenant's approved Azure Blob or Azure PostgreSQL connection
- **THEN** the request SHALL be evaluated by the tenant-data-source control-plane authorization and lifecycle rules
- **AND** it SHALL not grant access to any other tenant's profile or connection

### Requirement: Adapter selection is observable

The system SHALL record which adapter kinds served an ingestion, using values drawn from the declared finite set. Recorded adapter identity SHALL NOT include tenant-supplied configuration, endpoints, or credentials.

#### Scenario: Ingestion records the adapters that served it

- **GIVEN** a document ingested for a tenant
- **WHEN** the ingestion's observability output is inspected
- **THEN** it SHALL record the source type, the content-store kind, and the retention mode
- **AND** every recorded value SHALL come from the declared supported set

#### Scenario: No tenant configuration appears in observability output

- **GIVEN** a tenant whose profile contains non-secret configuration such as a host name
- **WHEN** any ingestion log record, span attribute, or metric label for that tenant is inspected
- **THEN** it SHALL NOT contain that configuration

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
