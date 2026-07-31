## MODIFIED Requirements

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables. Structured entity questions SHALL be answered against the normalized `document_entities` table, which holds one row per complete logical entity; `extracted_entities` (raw per-token BIO predictions) SHALL NOT be exposed to SQL generation, so generated SQL never reconstructs BIO sequences at query time.

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

## ADDED Requirements

### Requirement: Structured retrieval returns candidate document IDs

The `structured_retrieval` capability SHALL, in addition to its result rows, expose the distinct set of `document_id` values present in those rows as candidate document IDs. Candidate IDs SHALL be derived only from rows the query actually returned, and SHALL be an empty set when the query returned no rows or returned no `document_id` column. Exposing candidate IDs SHALL NOT change the rows returned to the RAG pipeline.

#### Scenario: Candidate IDs are the distinct document IDs of the result rows

- **GIVEN** a structured retrieval query returning rows for documents `docA`, `docA`, and `docB`
- **WHEN** the tool result is inspected
- **THEN** the candidate document IDs SHALL be exactly `{docA, docB}`
- **AND** the returned rows SHALL be unchanged

#### Scenario: No document_id column yields no candidates

- **GIVEN** a structured retrieval query returning only `entity_type` and a count
- **WHEN** the tool result is inspected
- **THEN** the candidate document IDs SHALL be empty

#### Scenario: Failed structured retrieval yields no candidates

- **GIVEN** a structured retrieval invocation whose SQL was rejected by validation
- **WHEN** the tool result is inspected
- **THEN** the candidate document IDs SHALL be empty
- **AND** the RAG pipeline SHALL proceed with the semantic source unfiltered

### Requirement: Candidate document filtering of semantic retrieval

When candidate document filtering is enabled and a plan contains both a structured and a semantic capability invocation, the orchestrator SHALL execute the structured invocation first and pass its non-empty candidate document IDs to the semantic invocation as a `document_ids` metadata filter, so vector search runs over the candidate set only. When the feature is disabled, when candidate IDs are empty, or when the semantic invocation already carries an explicit document scope, semantic retrieval SHALL run exactly as it does today. This requirement SHALL NOT change the graph node topology.

#### Scenario: Semantic search is scoped to structured candidates

- **GIVEN** candidate document filtering is enabled
- **AND** a plan invoking both `structured_retrieval` and `semantic_retrieval`
- **WHEN** structured retrieval returns candidate document IDs `{docA, docB}`
- **THEN** the semantic invocation SHALL receive a `document_ids` filter of `{docA, docB}`
- **AND** the returned chunks SHALL all belong to `docA` or `docB`

#### Scenario: Empty candidate set leaves semantic retrieval unfiltered

- **GIVEN** candidate document filtering is enabled
- **WHEN** structured retrieval returns no candidate document IDs
- **THEN** semantic retrieval SHALL run with no `document_ids` filter
- **AND** its results SHALL match the results it would have produced with the feature disabled

#### Scenario: Explicit document scope from the planner wins

- **GIVEN** candidate document filtering is enabled
- **AND** the planner scoped `semantic_retrieval` to `docC`
- **WHEN** structured retrieval returns candidate document IDs `{docA}`
- **THEN** semantic retrieval SHALL remain scoped to `docC`

#### Scenario: Feature disabled preserves concurrent execution

- **GIVEN** candidate document filtering is disabled
- **WHEN** a plan invoking both capabilities is executed
- **THEN** both invocations SHALL be dispatched concurrently as before
- **AND** the orchestration result SHALL be unchanged from current behaviour
