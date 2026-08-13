# chat-api

## MODIFIED Requirements

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables.

The validation layer SHALL resolve **every** table reference in the statement, not only the first identifier following each `FROM` or `JOIN` keyword. Comma-separated table lists, `CROSS JOIN`, schema-qualified names, and table references inside subqueries SHALL each be resolved and checked against the whitelist. A statement containing any reference that does not resolve to an unqualified whitelisted table name SHALL be rejected. The validation layer SHALL additionally reject any statement containing `SET ROLE` or `SET SESSION AUTHORIZATION`.

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

#### Scenario: Query exceeds timeout

- **GIVEN** a valid SQL query that executes for more than 10 seconds
- **WHEN** the query is executed
- **THEN** the execution SHALL be cancelled
- **AND** the RAG pipeline SHALL skip the SQL source for this turn

### Requirement: Guardrail — source citation enforcement

Every chat response that presents an answer SHALL include a `sources` array with at least one citation referencing a retrieval source. Responses without any source SHALL be rejected by the guardrail layer before being returned to the user.

The guardrail SHALL distinguish an empty-sources turn in which every attempted retrieval **succeeded and legitimately found nothing** from one in which any attempted retrieval **failed**, and SHALL return a different reply for each. It SHALL NOT return the same message for both. The distinction SHALL be derived from the turn's retrieval status, not re-inferred from message content.

#### Scenario: Response with no sources after successful empty retrieval

- **GIVEN** every attempted retrieval capability reported status `empty` with no error
- **AND** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with a message stating that no matching information was found in the tenant's data
- **AND** the event SHALL be logged

#### Scenario: Response with no sources after a retrieval failure

- **GIVEN** at least one attempted retrieval capability reported status `failed`
- **AND** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with a message stating that a retrieval source failed and the result is therefore incomplete
- **AND** the reply SHALL NOT assert that the data does not exist
- **AND** the event SHALL be logged with the failing capability name

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from the pipeline's retrieval sources: structured entity data (via controlled SQL generation) and document context (via pgvector semantic search). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`).

The response SHALL additionally carry an optional `retrieval_status` object reporting, per attempted retrieval capability, whether it was `not_attempted`, `ok`, `empty`, or `failed`. The field is additive: clients that ignore it SHALL observe no change in any other field.

#### Scenario: Chat with simple entity count query

- **GIVEN** a tenant with extracted entities for ORG type
- **WHEN** a Tenant Admin sends `POST /api/v1/chat` with `{"message": "How many organizations did we extract?", "conversation_id": null}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `reply` with a natural language answer
- **AND** the response SHALL contain `sources` array with at least one citation
- **AND** the response SHALL contain `conversation_id`

#### Scenario: Chat with document context query

- **GIVEN** a tenant with document chunks containing embeddings
- **WHEN** a Tenant Admin sends a question about document content
- **THEN** the response SHALL have status 200
- **AND** the response SHALL reference relevant document chunks in `sources`
- **AND** each source SHALL include `document_id`, `chunk_index`, `relevance_score`

#### Scenario: Response reports per-capability retrieval status

- **GIVEN** a turn in which structured retrieval failed and semantic retrieval returned chunks
- **WHEN** the chat endpoint returns its response
- **THEN** the response SHALL have status 200
- **AND** `retrieval_status` SHALL report `failed` for the structured capability
- **AND** `retrieval_status` SHALL report `ok` for the semantic capability

#### Scenario: retrieval_status is additive for existing clients

- **GIVEN** a client that deserializes only the previously specified `ChatResponse` fields
- **WHEN** the client receives a response carrying `retrieval_status`
- **THEN** every previously specified field SHALL retain its prior shape and meaning
- **AND** the client SHALL continue to function without modification

#### Scenario: Chat with existing conversation

- **GIVEN** an existing conversation with ID `conv-abc`
- **WHEN** a user sends a message with `conversation_id: "conv-abc"`
- **THEN** the response SHALL have status 200
- **AND** the message SHALL be appended to the existing conversation
- **AND** the response SHALL include the message history context in the LLM prompt

#### Scenario: Chat without authentication

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/api/v1/chat`
- **THEN** the response SHALL have status 401
