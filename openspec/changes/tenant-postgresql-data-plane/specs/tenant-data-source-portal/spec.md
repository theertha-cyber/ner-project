## MODIFIED Requirements

### Requirement: Safe connection lifecycle interface

The portal SHALL provide a connection detail route that presents, in order, connection details (provider-specific non-sensitive configuration and secret-reference selection), sync activity (schedule/aggregate sync status, and for Azure Blob connections the manual "Sync now" control), and a lifecycle panel containing a single sequential test/attestation/activation control plus confirmed pause, replacement, and retirement actions. The form SHALL enforce the closed provider schemas (Azure Blob: account, container, optional prefix, `connection_string_ref`; Azure PostgreSQL: host, database, username, port, `sslmode: verify-full`, `password_ref`; Azure PostgreSQL data plane: host, database, username, port, `sslmode: verify-full`, `password_ref`) with inline validation, and values SHALL be write-only and absent after save. The Azure PostgreSQL data-plane provider SHALL be offered in provider selection only to administrators of a `tenant_owned` tenant, and SHALL be labelled distinctly from the read-only Azure PostgreSQL source.

The lifecycle panel's test/attestation/activation control SHALL render as a single control whose contents reflect the connection's current test and attestation state: an untested or previously failed connection SHALL show a "Test connection" (or retry) action with no attestation inputs; a test in progress SHALL show a disabled pending state with no attestation inputs; a connection with a passed test that is not yet active SHALL show the passed result plus two explicit, individually labeled attestation checkboxes (`network_approved`, `governance_approved`) and an "Activate" action; an active connection SHALL show a disabled "Activated" state with both attestations shown as confirmed. The "Activate" action SHALL remain disabled until a passed secure test AND both attestation checkboxes are checked by the administrator in the current session; the portal SHALL NOT submit `activation_evidence` automatically or infer either attestation from a passed test alone. A subsequent failed test SHALL reset both attestation checkboxes to unchecked and hide them until the next passed test. Every mutation SHALL send an `Idempotency-Key` (1–128 printable ASCII); an idempotent replay SHALL render the returned safe result, and key/body mismatch or a missing key SHALL surface the finite safe error. Retirement SHALL require explicit confirmation and an active connection SHALL be paused first. The detail view SHALL never present configuration values, secret-reference values, endpoint details, connection strings, provider diagnostics, SQL, prompts, answers, or tenant content, and PostgreSQL connections of either kind SHALL omit schedule/`last_sync` per the safe shape. For a data-plane connection, the sync activity panel SHALL be replaced by a data-plane panel showing data-plane status, provisioning outcome class, recorded schema revision, and last store health outcome, with a "Retry provisioning" action when status is `provisioning_failed`; its failed test SHALL present each residency check (version, vector extension, schema privilege, query role, target schema) as a finite labelled outcome; and its retirement confirmation SHALL state that content in the tenant store is not deleted by the platform and that content access ends.

#### Scenario: Test, attestation, and activation render as one sequential control

- **GIVEN** an authenticated tenant administrator viewing a draft connection's lifecycle panel
- **WHEN** the administrator has not yet run a secure test
- **THEN** the panel SHALL show a single "Test connection" control, with no attestation checkboxes and no Activate action, replacing the previously separate Activation-evidence panel.

#### Scenario: A passed test surfaces the attestation checkboxes inline, Activate stays disabled until both are checked

- **GIVEN** a connection whose secure test has just passed
- **WHEN** the administrator views the lifecycle panel
- **THEN** the same control SHALL show the passed result plus the `network_approved` and `governance_approved` checkboxes, both unchecked, with "Activate" disabled
- **AND** "Activate" SHALL enable only once the administrator has checked both checkboxes, and activating SHALL submit `activation_evidence` containing exactly `network_approved` and `governance_approved`.

#### Scenario: A failed test hides the attestation checkboxes and returns the control to a retry state

- **GIVEN** a connection whose secure test fails, including a retest of a previously passed connection
- **WHEN** the administrator views the lifecycle panel
- **THEN** the control SHALL return to a "Test connection" (retry) state, SHALL hide and reset any previously checked attestation checkboxes, and SHALL NOT expose an Activate action.

#### Scenario: Activation is blocked safely

- **GIVEN** a connection whose test, secret resolution, or required evidence is absent or failed
- **WHEN** the backend reports unmet activation prerequisites
- **THEN** the lifecycle action SHALL be unavailable with a safe blocking notice and no secret, connection string, provider error, or remote content displayed.

#### Scenario: Destructive lifecycle actions require confirmation

- **GIVEN** an authenticated tenant administrator retiring or replacing a connection
- **WHEN** the administrator initiates the action
- **THEN** the portal SHALL require explicit confirmation before sending the mutation, and an active connection SHALL require pausing first.

#### Scenario: Idempotent mutation replay renders the safe result

- **GIVEN** a mutation already accepted under an `Idempotency-Key`
- **WHEN** the same key and body are submitted again
- **THEN** the portal SHALL render the returned safe result with a replay notice and SHALL NOT duplicate the lifecycle effect.

#### Scenario: Detail panels render in the fixed order

- **GIVEN** an authenticated tenant administrator viewing any connection's detail route
- **WHEN** the detail route renders
- **THEN** the portal SHALL present Connection details first, Sync activity (or Data plane, for a data-plane connection) second, and Lifecycle third, for Azure Blob, Azure PostgreSQL, and Azure PostgreSQL data-plane connections.

#### Scenario: Data-plane provider is hidden for platform tenants

- **GIVEN** an authenticated tenant administrator of a `platform` tenant
- **WHEN** the administrator opens "New connection"
- **THEN** provider selection SHALL NOT offer the Azure PostgreSQL data-plane provider

#### Scenario: Data-plane failed test shows residency checks

- **GIVEN** a data-plane connection whose test failed on `vector_extension_unavailable`
- **WHEN** the administrator views the lifecycle panel
- **THEN** the panel SHALL show the vector-extension check as failed with a safe prerequisite hint and no server or provider text

## ADDED Requirements

### Requirement: Tenant users see a safe data-plane readiness state

For a `tenant_owned` tenant whose data-plane status is not `ready`, or whose content requests return `TENANT_DATA_PLANE_UNAVAILABLE`, the portal SHALL replace content areas (documents, extraction, annotation, training, analytics, chat) with a safe state naming the status class — awaiting store, provisioning, provisioning failed, migration required, paused, unavailable, or retired — and SHALL direct tenant administrators to data-source settings. It SHALL NOT render cached tenant content, endpoints, or provider diagnostics in that state.

#### Scenario: Awaiting-store tenant administrator is guided to setup

- **GIVEN** a tenant administrator of a `tenant_owned` tenant in `awaiting_store`
- **WHEN** the administrator opens the documents page
- **THEN** the page SHALL show an awaiting-store state with a link to data-source settings
- **AND** no upload control SHALL be enabled

#### Scenario: Outage is shown without content

- **GIVEN** a tenant user of a `ready` residency tenant whose store becomes unreachable
- **WHEN** the chat page receives `TENANT_DATA_PLANE_UNAVAILABLE`
- **THEN** the page SHALL show an unavailable state
- **AND** it SHALL NOT display previously loaded conversation content after the error
