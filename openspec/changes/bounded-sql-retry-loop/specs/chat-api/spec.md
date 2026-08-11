## MODIFIED Requirements

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables.

Generation, validation, and execution SHALL be performed as a bounded attempt loop rather than a single pass: the system SHALL retry a failed attempt with feedback about the previous attempt, up to a configured maximum number of attempts, and SHALL stop immediately on the first successful attempt. Every attempt SHALL pass through the same validation layer and the same read-only execution path, against the schema bound from authenticated request context. The generation context SHALL include the tenant's entity types together with a bounded sample of representative values from that tenant's own data. When all attempts fail, the failure SHALL be reported to the retrieval pipeline as an error and SHALL NOT be presented as a successful empty result. The loop's behaviour is specified in full by the `sql-query-recovery` capability.

#### Scenario: Valid SQL query is executed

- **GIVEN** a natural language question about entity counts
- **WHEN** the SQL generation produces `SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type LIMIT 10`
- **THEN** the validation layer SHALL pass the query
- **AND** the query SHALL be executed in a read-only transaction
- **AND** the results SHALL be returned to the RAG pipeline
- **AND** no further SQL-generation call SHALL be made for that invocation

#### Scenario: Malicious SQL is rejected

- **GIVEN** an LLM-generated query attempting `DROP TABLE extracted_entities`
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query
- **AND** the system SHALL log the rejected query
- **AND** the system SHALL retry generation within the configured attempt budget
- **AND** if no attempt succeeds, the RAG pipeline SHALL skip the SQL source for this turn and record the failure as a structured-retrieval error
- **AND** the response SHALL indicate the SQL source was unavailable

#### Scenario: Query with non-whitelisted table is rejected

- **GIVEN** a generated query referencing `pg_authid`
- **WHEN** the validation layer inspects the table name
- **THEN** the validation SHALL reject the query
- **AND** the rejection SHALL apply identically to a first attempt and to any retry

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
