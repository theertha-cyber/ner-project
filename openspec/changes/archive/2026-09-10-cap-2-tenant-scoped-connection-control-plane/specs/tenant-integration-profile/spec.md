## MODIFIED Requirements

### Requirement: Only platform default adapters are executable in this change

The system SHALL permit a profile to *record* adapter selection from the declared supported set and SHALL treat platform defaults as executable for all providers except the approved Azure Blob Storage and Azure Database for PostgreSQL tenant-bound connections governed by `tenant-data-source-control-plane`. An approved Azure connection SHALL be executable only after its tenant-admin lifecycle activation gate succeeds; any other non-default adapter selection SHALL be rejected as recorded but unsupported. The presence of a recordable value SHALL NOT be taken as a claim that its adapter exists.

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
