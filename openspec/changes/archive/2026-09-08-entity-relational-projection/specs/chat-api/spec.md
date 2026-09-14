## MODIFIED Requirements

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables.

The whitelisted table set SHALL include the generated relational entity tables for the querying tenant, resolved per schema from `entity_definitions` rather than from a static constant. The execution role's `SELECT` grants SHALL be resolved from the **same** resolver, so the granted set and the validated set cannot drift apart. Tables belonging to definitions whose `is_active` is false SHALL be excluded from both, even though the tables themselves are retained. Tables belonging to definitions whose current cardinality is `single` SHALL likewise be excluded from both: a `single` definition's values are a column on `subject`, so its identifier names no relation the reconciler maintains. Such a table may nonetheless exist, retained from a period when the definition was `multi`, and the projection stops writing to it at the moment of the flip — granting or validating it would place a permanently empty relation on the query surface, where a query returns zero rows rather than an error. Because grants are otherwise append-only, provisioning SHALL revoke the execution role's table privileges in a tenant schema before re-granting the current surface, so a table that leaves the surface does not keep the `SELECT` it held while it was on it. Because the query surface consists of physical tables, the existing `pg_tables`-based `IF EXISTS` guard on each grant SHALL continue to apply unchanged.

#### Scenario: Valid SQL query is executed

- **GIVEN** a natural language question about entity counts
- **WHEN** the SQL generation produces `SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type LIMIT 10`
- **THEN** the validation layer SHALL pass the query
- **AND** the query SHALL be executed in a read-only transaction
- **AND** the results SHALL be returned to the RAG pipeline

#### Scenario: Malicious SQL is rejected

- **GIVEN** an LLM-generated query attempting `DROP TABLE extracted_entities`
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query
- **AND** the system SHALL log the rejected query
- **AND** the RAG pipeline SHALL skip the SQL source for this turn
- **AND** the response SHALL indicate the SQL source was unavailable

#### Scenario: Query with non-whitelisted table is rejected

- **GIVEN** a generated query referencing `pg_authid`
- **WHEN** the validation layer inspects the table name
- **THEN** the validation SHALL reject the query

#### Scenario: Query exceeds timeout

- **GIVEN** a valid SQL query that executes for more than 10 seconds
- **WHEN** the query is executed
- **THEN** the execution SHALL be cancelled
- **AND** the RAG pipeline SHALL skip the SQL source for this turn

#### Scenario: A generated entity table is both granted and whitelisted

- **GIVEN** a tenant with an active `multi` definition whose generated table exists
- **WHEN** the execution role is provisioned and the whitelist is resolved
- **THEN** the role SHALL hold `SELECT` on that table
- **AND** the validation layer SHALL accept a query referencing it

#### Scenario: Grants and whitelist resolve from one source

- **GIVEN** any tenant schema
- **WHEN** the granted table set and the whitelisted table set are computed
- **THEN** both SHALL be produced by the same resolver
- **AND** the two sets SHALL be equal for the generated entity tables

#### Scenario: An inactive definition's table is excluded from the query surface

- **GIVEN** a definition that has been deactivated while its generated table is retained
- **WHEN** the grants and whitelist are resolved
- **THEN** neither SHALL include that table
- **AND** a query referencing it SHALL be rejected by the validation layer

#### Scenario: A child table retained from a `multi` era is excluded from the query surface

- **GIVEN** a definition whose cardinality is now `single`, whose child table was retained from when it was `multi`
- **WHEN** the grants and whitelist are resolved
- **THEN** neither SHALL include that table
- **AND** a query referencing it SHALL be rejected by the validation layer
- **AND** the definition's values SHALL remain reachable as a `subject` column

#### Scenario: A table that leaves the query surface loses its grant

- **GIVEN** a generated table the execution role holds `SELECT` on
- **WHEN** its definition leaves the query surface and the role is provisioned again
- **THEN** provisioning SHALL revoke the role's table privileges in that schema before re-granting
- **AND** the role SHALL NOT retain `SELECT` on that table

#### Scenario: Reactivation restores access without recreating data

- **GIVEN** a previously deactivated definition whose table retained its rows
- **WHEN** the definition is reactivated and the role and whitelist are resolved again
- **THEN** the role SHALL hold `SELECT` on that table
- **AND** a query referencing it SHALL be accepted

#### Scenario: A grant for a table that does not yet exist is skipped safely

- **GIVEN** an active definition whose generated table has not yet been created
- **WHEN** the execution role is provisioned
- **THEN** the grant SHALL be skipped by the existing `pg_tables` guard
- **AND** provisioning SHALL NOT raise
