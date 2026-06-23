## ADDED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`). The response SHALL include a `sources` array with at least one citation. Response modeling (tone, formatting, guardrails) SHALL be orchestrated by the system prompt and application logic, not delegated to an external LLM for final answer formatting. The citation requirement applies to the final response payload — the response SHALL include a `sources` array populated by the RAG pipeline, and the response text SHALL reference cited sources.

#### Scenario: Chat with simple entity count query

- **GIVEN** a tenant with extracted entities for ORG type
- **WHEN** a Tenant Admin sends `POST /api/v1/tenants/{tid}/chat` with `{"message": "How many organizations did we extract?", "conversation_id": null}`
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

#### Scenario: Chat with NER query

- **GIVEN** a tenant with a promoted NER model
- **WHEN** a user asks about entities in a specific text snippet
- **THEN** the response SHALL include NER results in `sources`
- **AND** the NER source SHALL include `entity_type`, `value`, `confidence`

#### Scenario: Chat with existing conversation

- **GIVEN** an existing conversation with ID `conv-abc`
- **WHEN** a user sends a message with `conversation_id: "conv-abc"`
- **THEN** the response SHALL have status 200
- **AND** the message SHALL be appended to the existing conversation
- **AND** the response SHALL include the message history context in the LLM prompt

#### Scenario: Chat without authentication

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/api/v1/tenants/{tid}/chat`
- **THEN** the response SHALL have status 401

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables.

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

### Requirement: pgvector semantic search

The system SHALL perform semantic search over pre-computed document chunk embeddings using pgvector similarity search. The embedding for the user's query SHALL be computed using the same embedding model used at chunk-ingestion time. Results SHALL be ranked by cosine similarity and limited to a configurable top-K (default: 5).

#### Scenario: Semantic search returns relevant chunks

- **GIVEN** document chunks with embeddings for a tenant
- **WHEN** the RAG pipeline performs semantic search with a user query
- **THEN** the result SHALL contain the top-K most similar chunks
- **AND** each result SHALL include `document_id`, `chunk_text`, `similarity_score`

#### Scenario: Semantic search with empty corpus

- **GIVEN** a tenant with no document chunks
- **WHEN** the RAG pipeline performs semantic search
- **THEN** the pipeline SHALL skip the pgvector source
- **AND** the response SHALL not include document chunk sources

### Requirement: NER inference for chat context

The system SHALL integrate with the model-serving internal endpoint to perform real-time NER inference on relevant text snippets (e.g., document chunks retrieved by pgvector search) to enrich the chat response with entity information.

#### Scenario: NER inference on retrieved chunks

- **GIVEN** retrieved document chunks from pgvector search
- **WHEN** the RAG pipeline sends chunk text to model-serving `/internal/v1/infer`
- **THEN** the response SHALL include extracted entities with `entity_type`, `value`, `confidence`
- **AND** the entities SHALL be included in the chat response sources

#### Scenario: NER inference with no promoted model

- **GIVEN** a tenant with no promoted model
- **WHEN** NER inference is called
- **THEN** the system SHALL use the base model (version 0) per ADR-008
- **AND** entities SHALL have CoNLL entity types

### Requirement: Conversation CRUD

The system SHALL expose endpoints to create, list, retrieve, and delete conversations. Each conversation SHALL be scoped to a single tenant and user. Messages SHALL be stored with `role` (user/assistant), `content`, and `sources` (JSON array).

#### Scenario: List conversations for a user

- **GIVEN** a user with 3 existing conversations
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/chat/conversations`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 3 conversations
- **AND** each conversation SHALL have `id`, `title`, `created_at`, `message_count`

#### Scenario: Get conversation messages

- **GIVEN** a conversation with 5 messages
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 5 messages
- **AND** each message SHALL have `role`, `content`, `sources`, `created_at`

#### Scenario: Delete conversation

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends DELETE `/api/v1/tenants/{tid}/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 204

#### Scenario: Delete another user's conversation returns 404

- **GIVEN** a conversation owned by user A
- **WHEN** user B sends DELETE to the same conversation
- **THEN** the response SHALL have status 404

### Requirement: Rate limiting

The system SHALL enforce per-tenant rate limits on the chat endpoint. The internal API rate limit SHALL be 60 requests/minute per tenant. The widget API rate limit SHALL be 20 requests/minute per tenant. Rate limit headers SHALL be returned in the response.

#### Scenario: Rate limit exceeded returns 429

- **GIVEN** a tenant that has exceeded 60 requests/minute
- **WHEN** a chat request is sent
- **THEN** the response SHALL have status 429
- **AND** the response SHALL include `Retry-After` header

#### Scenario: Rate limit headers on successful request

- **GIVEN** a tenant within rate limits
- **WHEN** a chat request succeeds
- **THEN** the response SHALL include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers

### Requirement: Guardrail — source citation enforcement

Every chat response SHALL include a `sources` array with at least one citation referencing one or more of the three RAG sources. Responses without any source SHALL be rejected by the guardrail layer before being returned to the user.

#### Scenario: Response without sources is rejected

- **GIVEN** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with "I couldn't find relevant information to answer that question."
- **AND** the event SHALL be logged

### Requirement: Guardrail — blocked question types

The system SHALL reject questions that fall outside the chatbot's defined capability list. Blocked types include: classification of non-extracted data, content generation (writing emails, essays, etc.), summarization of non-extracted data, questions about other tenants' data, and requests for PII not present in extracted entities.

#### Scenario: Blocked question returns graceful decline

- **GIVEN** a user asks "Write an email to the team"
- **WHEN** the chat endpoint processes the message
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a graceful decline message
- **AND** the response SHALL have an empty `sources` array

### Requirement: Guardrail — query complexity limits

The system SHALL reject questions that require more than 3 distinct source lookups. If a question requires 4 or more lookups, the system SHALL respond with a message asking the user to simplify the question.

#### Scenario: Overly complex question is simplified

- **GIVEN** a multi-hop question requiring 4 source lookups
- **WHEN** the complexity guardrail evaluates it
- **THEN** the response SHALL ask the user to simplify the question
- **AND** the complexity score SHALL be logged

### Requirement: Disclaimer in every response

Every chat response SHALL include a disclaimer string in the response body indicating that the answer was AI-generated and may contain errors. The disclaimer SHALL NOT be included in the `reply` text itself but as a separate `disclaimer` field in the response JSON.

#### Scenario: Response includes disclaimer field

- **GIVEN** a successful chat response
- **WHEN** the response is returned
- **THEN** the response SHALL contain a `disclaimer` field
- **AND** the disclaimer SHALL read "This answer was generated by AI and may contain errors. Verify important information against source documents."
