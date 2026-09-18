# external-postgresql-chat

## Purpose

Contract-governed, tenant-scoped direct read-only chat over a tenant's Azure Database for PostgreSQL: versioned canonical schema contracts with an explicit join graph, tenant-isolated schema index for context only, live fingerprint drift gating before every query, and AST-restricted parameterized SELECT execution with a server row cap and ten-second timeout. External rows are response-only and never persisted as platform data.

## MODIFIED Requirements

### Requirement: Versioned tenant-isolated schema contracts

The system SHALL accept only valid published-version JSON schema contracts that declare approved relations, columns, and an explicit join graph with join keys for the authenticated tenant's active PostgreSQL connection. It SHALL preserve canonical versions with a deterministic fingerprint and create a tenant-isolated schema-index representation used for context only. No contract or index entry SHALL be visible to another tenant, and the index SHALL NOT authorize access.

#### Scenario: Valid contract is published

- **GIVEN** an authenticated tenant administrator with an active PostgreSQL connection
- **WHEN** the administrator submits a valid contract and publishes the validated version
- **THEN** the canonical version and safe validation state SHALL be retained
- **AND** its tenant-isolated index representation SHALL be created
- **AND** no contract or index entry SHALL be visible to another tenant.

#### Scenario: Invalid contract is rejected safely

- **GIVEN** an authenticated tenant administrator with an active PostgreSQL connection
- **WHEN** the administrator uploads invalid JSON or a semantically invalid contract (unknown shape, undeclared join key, duplicate version)
- **THEN** the version SHALL NOT be accepted
- **AND** the response SHALL carry only a finite validation reason class and field-level safe errors
- **AND** no index entry SHALL be created.

#### Scenario: Cross-tenant contract access is denied

- **GIVEN** a canonical contract owned by tenant A
- **WHEN** tenant B names that contract, connection, or version
- **THEN** the lookup SHALL resolve to not found with no metadata disclosure
- **AND** no index entry of tenant A SHALL be retrievable by tenant B.

### Requirement: Drift-gated external read-only query

The system SHALL introspect live contract-relevant metadata and compare a deterministic canonical fingerprint before every external query. It SHALL block execution on fingerprint mismatch, unavailable metadata, or fingerprint failure until a replacement contract is accepted. The drift check SHALL precede every direct-query attempt (NFR-RELY-002), and blocked callers SHALL receive only a safe drift-blocked outcome with a finite reason class.

#### Scenario: Drift blocks execution

- **GIVEN** an accepted contract whose live metadata fingerprint differs from the accepted fingerprint
- **WHEN** an authorized chat request attempts an external query
- **THEN** no external SQL SHALL execute
- **AND** the caller SHALL receive a safe drift-blocked outcome naming only the finite reason class.

#### Scenario: Unavailable metadata blocks execution distinctly

- **GIVEN** an accepted contract whose live metadata cannot be introspected
- **WHEN** an authorized chat request attempts an external query
- **THEN** no external SQL SHALL execute
- **AND** the outcome SHALL carry the `metadata_unavailable` reason class, distinct from drift mismatch.

#### Scenario: Replacement contract restores execution

- **GIVEN** a drift-blocked connection
- **WHEN** the administrator publishes a replacement contract matching live metadata
- **THEN** subsequent authorized queries SHALL execute again.

### Requirement: Contract-authorized SQL execution

The system SHALL execute only one AST-validated, parameterized SELECT per request through a tenant-scoped read-only credential, enforcing contract-authorized relations, columns, and join paths, a server row cap of 100 rows, and a ten-second statement timeout. Permitted constructs are contract-approved tables, columns, joins, aggregations (COUNT/SUM/AVG/MIN/MAX), GROUP BY, HAVING, WHERE, ORDER BY, DISTINCT, column aliases, and basic date/time functions. Results SHALL be response-only without persisting tenant database rows. The LLM SHALL have no database credential or direct connector access. Telemetry SHALL record only finite rejection/execution reason classes and correlation metadata, never SQL text or row values.

#### Scenario: Approved join and aggregation executes

- **GIVEN** an accepted contract authorizing a join path and an authorized chat request producing a single contract-approved SELECT with a permitted aggregation
- **WHEN** the query executes
- **THEN** it SHALL complete within the row cap and timeout
- **AND** response-only results SHALL be returned without persisting tenant database rows.

#### Scenario: Disallowed statement is rejected safely

- **GIVEN** a proposed external statement containing a write, DDL, multiple statements, a subquery, a CTE, a UNION, a window function, or an unapproved relation, column, or join path
- **WHEN** the validator inspects the statement
- **THEN** it SHALL NOT reach the tenant database
- **AND** telemetry SHALL record only a finite rejection reason and correlation metadata.

#### Scenario: Unparameterized literal never reaches the database

- **GIVEN** a proposed statement carrying an inline literal in a filter position
- **WHEN** the execution path handles it
- **THEN** the literal SHALL be bound as a parameter or the statement SHALL be rejected
- **AND** no interpolated value SHALL appear in the executed SQL text.

#### Scenario: Row cap and timeout are enforced by the server

- **GIVEN** an approved SELECT that would return more than 100 rows or run longer than ten seconds
- **WHEN** it executes
- **THEN** at most 100 rows SHALL be returned and execution SHALL be cancelled at ten seconds
- **AND** both bounds SHALL be enforced by the database server, not only the application.

#### Scenario: External rows are never retained

- **GIVEN** a completed external query with result rows
- **WHEN** platform storage is inspected afterwards
- **THEN** no tenant database row SHALL exist in any platform table.

#### Scenario: Capability resolves server-side per authenticated tenant

- **GIVEN** tenants A and B each with an active PostgreSQL connection and accepted contract
- **WHEN** tenant A issues an external chat request
- **THEN** only tenant A's connection, contract, and credential SHALL be used
- **AND** tenant B's metadata SHALL be unreachable.
