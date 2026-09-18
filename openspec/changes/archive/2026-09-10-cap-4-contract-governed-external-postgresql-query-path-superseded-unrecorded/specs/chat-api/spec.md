# chat-api (delta)

## Purpose

Correct the rejected-SQL logging rule so the external query path complies with the telemetry invariant: rejected statements are recorded as finite reason classes, never as SQL text. All other scenarios in the touched requirement are carried unchanged so the archive merges without dropping baseline behavior.

## MODIFIED Requirements

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables. Structured entity questions SHALL be answered against the normalized `document_entities` table, which holds one row per complete logical entity; `extracted_entities` (raw per-token BIO predictions) SHALL NOT be exposed to SQL generation, so generated SQL never reconstructs BIO sequences at query time.

Generation, validation, and execution SHALL be performed as a bounded attempt loop rather than a single pass: the system SHALL retry a failed attempt with feedback about the previous attempt, up to a configured maximum number of attempts, and SHALL stop immediately on the first successful attempt. Every attempt SHALL pass through the same validation layer and the same read-only execution path, against the schema bound from authenticated request context. The generation context SHALL include the tenant's entity types together with a bounded sample of representative values from that tenant's own data. When all attempts fail, the failure SHALL be reported to the retrieval pipeline as an error and SHALL NOT be presented as a successful empty result.

The validation layer SHALL resolve **every** table reference in the statement, not only the first identifier following each `FROM` or `JOIN` keyword. Comma-separated table lists, `CROSS JOIN`, schema-qualified names, and table references inside subqueries SHALL each be resolved and checked against the whitelist. A statement containing any reference that does not resolve to an unqualified whitelisted table name SHALL be rejected. The validation layer SHALL additionally reject any statement containing `SET ROLE` or `SET SESSION AUTHORIZATION`.

The query model presented to the generator SHALL be the tenant's generated relational surface — `subject` and the active `e_<slug>` child tables — and not the EAV entity store. `document_entities` SHALL remain whitelisted and granted so that static-table questions and the generator's grounding and defect probes continue to work, but the generator SHALL NOT be instructed to query it, to filter on `entity_type`, or to self-join it to assemble a subject.

The whitelisted table set SHALL include the generated relational entity tables for the querying tenant, resolved per schema from `entity_definitions` rather than from a static constant. The execution role's `SELECT` grants SHALL be resolved from the **same** resolver, so the granted set and the validated set cannot drift apart. Tables belonging to definitions whose `is_active` is false SHALL be excluded from both, even though the tables themselves are retained. Tables belonging to definitions whose current cardinality is `single` SHALL likewise be excluded from both: a `single` definition's values are a column on `subject`, so its identifier names no relation the reconciler maintains. Such a table may nonetheless exist, retained from a period when the definition was `multi`, and the projection stops writing to it at the moment of the flip — granting or validating it would place a permanently empty relation on the query surface, where a query returns zero rows rather than an error. Because grants are otherwise append-only, provisioning SHALL revoke the execution role's table privileges in a tenant schema before re-granting the current surface, so a table that leaves the surface does not keep the `SELECT` it held while it was on it. Because the query surface consists of physical tables, the existing `pg_tables`-based `IF EXISTS` guard on each grant SHALL continue to apply unchanged.

The whitelisted **column** set SHALL be resolved from that same surface rather than restated: the static tables keep their declared columns, `subject` contributes its identity columns and one column per active `single` definition, and each active child table contributes the fixed child column shape. A column reference the validation layer cannot attribute to a specific relation SHALL be accepted rather than rejected, so a parser gap degrades into a database error rather than a false rejection of a correct query.

Rejected statements — platform or external — SHALL be recorded as a finite safe rejection reason class with correlation metadata only; the system SHALL NOT log, metric-label, trace, or audit SQL text, literals, or row values.

#### Scenario: Valid SQL query is executed

- **GIVEN** a natural language question about entity counts
- **WHEN** the SQL generation produces `SELECT entity_type, COUNT(*) FROM document_entities GROUP BY entity_type LIMIT 10`
- **THEN** the validation layer SHALL pass the query
- **AND** the query SHALL be executed in a read-only transaction
- **AND** the results SHALL be returned to the RAG pipeline

#### Scenario: Entity lookup matches on the canonical value

- **GIVEN** the question "which documents mention AWS?"
- **WHEN** the SQL generation produces a query filtering `document_entities` on `normalized_value = 'aws'`
- **THEN** the validation layer SHALL pass the query
- **AND** documents whose extracted text was `Amazon Web Services` SHALL be returned

#### Scenario: Raw BIO token table is not reachable from chat SQL

- **GIVEN** a generated query referencing `extracted_entities`
- **WHEN** the validation layer inspects the table name
- **THEN** the validation SHALL reject the query
- **AND** the RAG pipeline SHALL skip the SQL source for this turn

#### Scenario: Malicious SQL is rejected

- **GIVEN** an LLM-generated query attempting `DROP TABLE document_entities`
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query
- **AND** the system SHALL record only a finite rejection reason class and correlation metadata, never the SQL text
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

#### Scenario: Failed query is recovered within the attempt budget

- **GIVEN** a first generated query that fails to execute
- **WHEN** the system generates a revised query informed by that failure
- **AND** the revised query validates and executes successfully
- **THEN** the revised query's results SHALL be returned to the RAG pipeline
- **AND** the turn SHALL proceed through the unchanged answer-generation pipeline

#### Scenario: Generation context carries bounded tenant entity values

- **GIVEN** a tenant whose extracted entities include a `SKILL` type with values such as `python`
- **WHEN** the SQL-generation prompt is constructed for that tenant
- **THEN** the prompt SHALL include `SKILL` together with a bounded sample of its actual values
- **AND** the sampled values SHALL be drawn only from the schema bound from authenticated request context

#### Scenario: Comma-joined non-whitelisted table is rejected

- **GIVEN** a generated query `SELECT d.filename FROM documents d, public.users u WHERE u.tenant_id <> d.tenant_id LIMIT 10`
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query
- **AND** the rejection reason SHALL name the offending reference
- **AND** the statement SHALL NOT reach the database

#### Scenario: Non-whitelisted table in a subquery FROM clause is rejected

- **GIVEN** a generated query whose subquery selects from a relation outside the whitelist
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query

#### Scenario: Multi-table whitelisted comma join is accepted

- **GIVEN** a generated query `SELECT e.entity_value, d.filename FROM document_entities e, documents d WHERE d.id = e.document_id LIMIT 100`
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL pass the query
- **AND** the query SHALL be executed

#### Scenario: Role-switching statement is rejected

- **GIVEN** a generated statement containing `SET ROLE postgres`
- **WHEN** the validation layer inspects the statement
- **THEN** the validation SHALL reject the statement

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

#### Scenario: Grants, whitelist, and generation context resolve from one source

- **GIVEN** any tenant schema
- **WHEN** the granted table set, the whitelisted table set, and the set of relations described to the generator are computed
- **THEN** all three SHALL be produced by the same resolver
- **AND** the three sets SHALL be equal for the generated entity tables

#### Scenario: An inactive definition's table is excluded from the query surface

- **GIVEN** a definition that has been deactivated while its generated table is retained
- **WHEN** the grants and whitelist are resolved
- **THEN** neither SHALL include that table
- **AND** the generation context SHALL NOT describe it
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

#### Scenario: Query with a column no relation declares is rejected

- **GIVEN** a generated query selecting a column that neither the static tables nor the tenant's resolved relational surface declares
- **WHEN** the validation layer inspects the column reference
- **THEN** the validation SHALL reject the query
- **AND** the rejection SHALL name the offending column
