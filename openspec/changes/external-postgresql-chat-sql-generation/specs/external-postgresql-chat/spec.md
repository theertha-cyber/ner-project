## MODIFIED Requirements

### Requirement: Versioned tenant-isolated schema contracts

The system SHALL accept only valid published-version JSON schema contracts that declare approved relations, columns, and an explicit join graph with join keys for the authenticated tenant's active PostgreSQL connection. A contract MAY additionally declare, per relation, an optional `description` string and an optional `column_descriptions` object that maps declared column names to description strings. A description SHALL be a string of at most 2,000 characters. A `column_descriptions` key that is not a declared column of that relation SHALL be rejected with a field-level safe error. Descriptions SHALL be retained in the canonical version but SHALL NOT contribute to the fingerprint. The system SHALL preserve canonical versions with a deterministic fingerprint and create a tenant-isolated schema-index representation used for context only, whose entry text includes relation and column descriptions where present. No contract or index entry SHALL be visible to another tenant, and the index SHALL NOT authorize access.

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

#### Scenario: Descriptions are retained and indexed

- **GIVEN** a contract whose relation `fisc_user_profile` has `description` "User profiles" and `column_descriptions` `{"claim_ind": "'0'=Unclaimed, '1'=Claimed"}`
- **WHEN** the version is validated and published
- **THEN** the canonical version SHALL retain both descriptions
- **AND** the index entry text for `fisc_user_profile` SHALL contain both descriptions.

#### Scenario: Descriptions do not change the fingerprint

- **GIVEN** two contracts identical in relations, columns, and joins but with different descriptions
- **WHEN** their fingerprints are computed
- **THEN** the fingerprints SHALL be equal.

#### Scenario: Description for an undeclared column is rejected

- **GIVEN** a contract whose relation `orders` declares columns `id` and `total` and whose `column_descriptions` names `discount`
- **WHEN** the administrator uploads it
- **THEN** the version SHALL NOT be accepted
- **AND** the field errors SHALL name `relations.orders.column_descriptions.discount` without echoing the description value.

#### Scenario: Overlong description is rejected

- **GIVEN** a contract with a relation description longer than 2,000 characters
- **WHEN** the administrator uploads it
- **THEN** the version SHALL NOT be accepted with reason `invalid_shape`.

#### Scenario: Contract without descriptions remains valid

- **GIVEN** a contract that declares only relations, columns, primary keys, and joins
- **WHEN** the administrator uploads and publishes it
- **THEN** it SHALL be accepted and indexed exactly as before this change.

### Requirement: Contract-authorized SQL execution

The system SHALL execute only one AST-validated, parameterized SELECT per request through a tenant-scoped read-only credential, enforcing contract-authorized relations, columns, and join paths, a server row cap of 100 rows, and a ten-second statement timeout. Permitted constructs are contract-approved tables, columns, joins, aggregations (COUNT/SUM/AVG/MIN/MAX), GROUP BY, HAVING, WHERE, ORDER BY, DISTINCT, column aliases, and basic date/time functions. Result rows SHALL be response-only. They MAY be placed in the generation prompt for the current turn, but SHALL NOT be written to any platform table, including as serialized citation values in persisted chat messages. The natural-language reply generated from those rows MAY be persisted as the conversation's assistant message. A citation for an external answer SHALL carry only the source type `external_postgresql` and the names of the contract relations used. The LLM SHALL have no database credential or direct connector access. Telemetry SHALL record only finite rejection/execution reason classes and correlation metadata, never SQL text or row values.

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

#### Scenario: External citation carries no row values

- **GIVEN** a chat turn answered from an external query returning a row `{"person_firstname": "Arjun"}`
- **WHEN** the turn's persisted chat message sources are inspected
- **THEN** a source with `source_type` `external_postgresql` SHALL list only relation names
- **AND** no persisted source SHALL contain the value `Arjun` or any serialized result row.

#### Scenario: Capability resolves server-side per authenticated tenant

- **GIVEN** tenants A and B each with an active PostgreSQL connection and accepted contract
- **WHEN** tenant A issues an external chat request
- **THEN** only tenant A's connection, contract, and credential SHALL be used
- **AND** tenant B's metadata SHALL be unreachable.

## ADDED Requirements

### Requirement: Safe external chat outcomes

The system SHALL turn every non-success external chat outcome into a fixed, non-sensitive message available to answer generation, keyed by finite reason class: `drift_mismatch`, `metadata_unavailable`, `fingerprint_failure`, `not_active_connection`, `no_published_contract`, `generation_exhausted`, `schema_context_too_large`, and `execution_failed`. The message SHALL NOT include SQL text, parameter values, database error text, host names, or live metadata.

#### Scenario: Drift produces an administrator-action message

- **GIVEN** an external query blocked with `drift_mismatch`
- **WHEN** the chat turn completes
- **THEN** the answer SHALL state that the connected database's schema changed and an administrator must publish an updated contract
- **AND** no SQL SHALL have executed.

#### Scenario: Database failure text is not surfaced

- **GIVEN** an external execution that fails with a database error whose message names a column value
- **WHEN** the chat turn completes
- **THEN** the answer SHALL carry only the fixed `execution_failed` message
- **AND** the database error text SHALL NOT appear in the response, persisted message, or logs.
