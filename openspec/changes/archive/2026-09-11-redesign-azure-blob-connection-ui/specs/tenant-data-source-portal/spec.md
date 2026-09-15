## MODIFIED Requirements

### Requirement: Data source collection and navigation

The portal SHALL provide a tenant-admin-only `/settings/data-sources` route with server-backed, URL-backed search, provider/status filters, last-activity sort, and numbered pagination at 20 items per page. The collection SHALL query `GET /api/v1/data-sources` using only the allowlisted parameters (`q` 1–100 chars, `provider`, `status`, `sort` of `last_activity|created_at|provider|status`, `order` of `asc|desc`, `page` >= 1, `page_size` 1–100), defaulting to `last_activity` descending with ascending `id` tie-breaker, page 1, and 20 items. Search or filter changes SHALL reset to page 1; an out-of-range valid page SHALL render an empty list. The screen SHALL present loading, empty, filtered-empty, and safe error states, and SHALL label the `draft|validated|active|paused|error|retired` statuses without sensitive details. A "New connection" control SHALL open a modal dialog presenting provider selection and the provider configuration form; the collection list and filters SHALL remain unchanged and visible behind the modal, and closing the modal (via explicit cancel, `Escape`, or a successful create) SHALL leave the collection in its prior scroll and filter state.

#### Scenario: Administrator filters data sources

- **GIVEN** an authenticated tenant administrator on the data-sources collection
- **WHEN** the administrator changes the provider or status filter
- **THEN** the collection SHALL reset to page 1, retain query state in the URL, and show loading, empty, filtered-empty, or safe error state as applicable.

#### Scenario: Collection uses server-backed paging defaults

- **GIVEN** an authenticated tenant administrator opening `/settings/data-sources` with no query parameters
- **WHEN** the collection loads
- **THEN** the portal SHALL request page 1 with 20 items sorted by last activity descending with ascending `id` tie-breaker.

#### Scenario: Non-administrator cannot enter administration routes

- **GIVEN** an authenticated user without the tenant-administrator role
- **WHEN** the user navigates to a data-source administration route
- **THEN** the portal SHALL present the existing safe authorization state and SHALL NOT render collection or detail content.

#### Scenario: Administrator creates a connection from the modal

- **GIVEN** an authenticated tenant administrator on the data-sources collection
- **WHEN** the administrator opens "New connection", selects a provider, completes the configuration form, and submits
- **THEN** the portal SHALL open a modal dialog (not an inline expanding panel), send the create mutation with a fresh `Idempotency-Key`, and on success SHALL navigate to the new connection's detail route.

#### Scenario: Administrator dismisses the new-connection modal without creating a draft

- **GIVEN** an authenticated tenant administrator with the new-connection modal open
- **WHEN** the administrator presses `Escape` or activates the modal's cancel control
- **THEN** the portal SHALL close the modal, send no create request, discard the in-progress form values, and return focus to the "New connection" control.

### Requirement: Safe connection lifecycle interface

The portal SHALL provide a connection detail route that presents, in order, connection details (provider-specific non-sensitive configuration and secret-reference selection), sync activity (schedule/aggregate sync status, and for Azure Blob connections the manual "Sync now" control), and a lifecycle panel containing a single sequential test/attestation/activation control plus confirmed pause, replacement, and retirement actions. The form SHALL enforce the closed provider schemas (Azure Blob: account, container, optional prefix, `connection_string_ref`; Azure PostgreSQL: host, database, username, port, `sslmode: verify-full`, `password_ref`) with inline validation, and values SHALL be write-only and absent after save.

The lifecycle panel's test/attestation/activation control SHALL render as a single control whose contents reflect the connection's current test and attestation state: an untested or previously failed connection SHALL show a "Test connection" (or retry) action with no attestation inputs; a test in progress SHALL show a disabled pending state with no attestation inputs; a connection with a passed test that is not yet active SHALL show the passed result plus two explicit, individually labeled attestation checkboxes (`network_approved`, `governance_approved`) and an "Activate" action; an active connection SHALL show a disabled "Activated" state with both attestations shown as confirmed. The "Activate" action SHALL remain disabled until a passed secure test AND both attestation checkboxes are checked by the administrator in the current session; the portal SHALL NOT submit `activation_evidence` automatically or infer either attestation from a passed test alone. A subsequent failed test SHALL reset both attestation checkboxes to unchecked and hide them until the next passed test. Every mutation SHALL send an `Idempotency-Key` (1–128 printable ASCII); an idempotent replay SHALL render the returned safe result, and key/body mismatch or a missing key SHALL surface the finite safe error. Retirement SHALL require explicit confirmation and an active connection SHALL be paused first. The detail view SHALL never present configuration values, secret-reference values, endpoint details, connection strings, provider diagnostics, SQL, prompts, answers, or tenant content, and PostgreSQL connections SHALL omit schedule/`last_sync` per the safe shape.

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
- **THEN** the portal SHALL present Connection details first, Sync activity second, and Lifecycle third, for both Azure Blob and Azure PostgreSQL connections.
