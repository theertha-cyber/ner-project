# tenant-data-source-portal Specification

## Purpose
TBD - created by archiving change cap-5-tenant-data-source-administration-portal. Update Purpose after archive.
## Requirements
### Requirement: Data source collection and navigation

The portal SHALL provide a tenant-admin-only `/settings/data-sources` route with server-backed, URL-backed search, provider/status filters, last-activity sort, and numbered pagination at 20 items per page. The collection SHALL query `GET /api/v1/data-sources` using only the allowlisted parameters (`q` 1–100 chars, `provider`, `status`, `sort` of `last_activity|created_at|provider|status`, `order` of `asc|desc`, `page` >= 1, `page_size` 1–100), defaulting to `last_activity` descending with ascending `id` tie-breaker, page 1, and 20 items. Search or filter changes SHALL reset to page 1; an out-of-range valid page SHALL render an empty list. The screen SHALL present loading, empty, filtered-empty, and safe error states, and SHALL label the `draft|validated|active|paused|error|retired` statuses without sensitive details.

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

### Requirement: Safe connection lifecycle interface

The portal SHALL provide a connection detail route that presents provider-specific non-sensitive configuration, secret-reference selection, safe test/activation state, schedule/sync aggregate status, and confirmed pause, replacement, and retirement actions. The form SHALL enforce the closed provider schemas (Azure Blob: account, container, optional prefix, `connection_string_ref`; Azure PostgreSQL: host, database, username, port, `sslmode: verify-full`, `password_ref`) with inline validation, and values SHALL be write-only and absent after save. Activation SHALL be unavailable until a passed secure test and both `network_approved` and `governance_approved` attestations are recorded. Every mutation SHALL send an `Idempotency-Key` (1–128 printable ASCII); an idempotent replay SHALL render the returned safe result, and key/body mismatch or a missing key SHALL surface the finite safe error. Retirement SHALL require explicit confirmation and an active connection SHALL be paused first. The detail view SHALL never present configuration values, secret-reference values, endpoint details, connection strings, provider diagnostics, SQL, prompts, answers, or tenant content, and PostgreSQL connections SHALL omit schedule/`last_sync` per the safe shape.

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

### Requirement: Schema-contract administration interface

The portal SHALL provide contract upload, validation, publish, safe drift state, and URL-backed paginated contract-history management for PostgreSQL connections. Contract history SHALL use numbered pagination at 20 per page defaulting to published-at descending, with version search resetting to page 1. The screen SHALL present loading, no-published-contract, validation-in-progress, valid draft, invalid contract with linked field-level safe errors, published, drift-blocked, and request-error states, and SHALL preserve recoverable form state on failure. The screen SHALL display only version metadata, validation outcomes, published state, and safe drift status, and SHALL never show database rows or SQL text.

#### Scenario: Invalid contract is recoverable

- **GIVEN** a tenant administrator uploading a schema contract on the schema-contracts route
- **WHEN** the administrator uploads invalid JSON or a semantically invalid contract
- **THEN** the screen SHALL present linked field-level safe validation errors and preserve a recoverable form state without showing database rows or SQL text.

#### Scenario: Drift blocks direct chat safely

- **GIVEN** a published contract whose drift status is drift-blocked
- **WHEN** the administrator views the schema-contracts route
- **THEN** the screen SHALL present the drift-blocked state with a link between the connection detail and contract views and SHALL NOT expose row data or diagnostics.

