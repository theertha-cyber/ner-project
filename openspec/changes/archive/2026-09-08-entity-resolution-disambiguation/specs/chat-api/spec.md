## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`).

A chat turn SHALL have one of two terminal outcomes: an answer produced from retrieved evidence, or — when entity resolution is enabled and the message's entity reference is ambiguous — a clarification request produced without retrieval. A clarification response SHALL have status 200, an empty `sources` array, the standard disclaimer, and an additive `pending_clarification` field carrying the ordered candidate list. The `pending_clarification` field SHALL be absent for every non-clarification response, so existing clients are unaffected. Both user message and clarification reply SHALL be persisted to the conversation as ordinary chat messages.

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
- **WHEN** a POST request is sent to `/api/v1/chat`
- **THEN** the response SHALL have status 401

#### Scenario: Ambiguous reference returns a clarification response

- **GIVEN** entity resolution is enabled and three documents contain a person matching the message's reference
- **WHEN** a user sends that message
- **THEN** the response SHALL have status 200
- **AND** `reply` SHALL contain the clarification question and the candidate list
- **AND** `sources` SHALL be empty
- **AND** `pending_clarification` SHALL contain the ordered candidates

#### Scenario: Non-clarification responses omit the new field

- **GIVEN** entity resolution is enabled and an unambiguous message
- **WHEN** the turn completes
- **THEN** `pending_clarification` SHALL be absent from the response

#### Scenario: Clarification turn is persisted to the conversation

- **GIVEN** a clarification response for conversation `conv-abc`
- **WHEN** the conversation is later fetched
- **THEN** the user message and the clarification reply SHALL both appear in its message history

### Requirement: Guardrail — source citation enforcement

Every chat response that answers a question SHALL include a `sources` array with at least one citation referencing one or more of the three RAG sources. Answers without any source SHALL be rejected by the guardrail layer before being returned to the user.

Two response classes are exempt because they answer no question and assert no fact about tenant data: blocked-question and out-of-domain declines, and entity-resolution clarification requests. Exempt responses SHALL carry an empty `sources` array and SHALL NOT be replaced by the guardrail layer. A clarification request SHALL be exempt only when it was produced by the resolver without any generation model call; a model-generated reply SHALL always be subject to citation enforcement.

#### Scenario: Response without sources is rejected

- **GIVEN** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with "I couldn't find relevant information to answer that question."
- **AND** the event SHALL be logged

#### Scenario: Clarification request is not replaced by the guardrail

- **GIVEN** a clarification reply assembled by the resolver with no generation call
- **WHEN** the response is returned
- **THEN** the clarification text SHALL be preserved verbatim
- **AND** `sources` SHALL be empty

#### Scenario: Generated answer after selection still requires citations

- **GIVEN** a resumed turn after a successful candidate selection
- **WHEN** generation produces a reply with no sources
- **THEN** citation enforcement SHALL apply as it does for any other answer
