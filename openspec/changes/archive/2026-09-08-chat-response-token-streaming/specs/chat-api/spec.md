## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`).

The system SHALL additionally expose a streaming sibling of this endpoint at `POST /api/v1/chat/stream`, which accepts the same request body and authentication and delivers the same answer incrementally as Server-Sent Events. Both endpoints SHALL run the same RAG pipeline, apply the same guardrails, and persist the same rows; they differ only in how the response is delivered. The event protocol, ordering guarantees, and error behaviour of the streaming endpoint are specified by the `chat-response-streaming` capability.

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

#### Scenario: Streaming and non-streaming endpoints answer identically

- **GIVEN** the same tenant, conversation state, question, and scripted LLM
- **WHEN** the question is sent to `POST /api/v1/chat` and to `POST /api/v1/chat/stream`
- **THEN** the non-streaming JSON body and the streaming `done` payload SHALL carry the same `reply`, `sources`, `answer_kind`, `model_version`, and `disclaimer`

### Requirement: Guardrail — source citation enforcement

Every chat response SHALL include a `sources` array with at least one citation referencing one or more of the three RAG sources. Responses without any source SHALL be rejected by the guardrail layer before being returned to the user.

On the streaming endpoint, this rejection SHALL be decided before any generated content is emitted to the client. Because the guardrail's only input is the turn's assembled sources — which are fully determined before generation begins — the system SHALL evaluate source presence at generation entry and SHALL NOT emit any `token` event for a turn whose sources are empty. A user SHALL never be shown generated text that the guardrail subsequently replaces.

#### Scenario: Response without sources is rejected

- **GIVEN** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with "I couldn't find relevant information to answer that question."
- **AND** the event SHALL be logged

#### Scenario: Empty-sources turn emits no tokens before the fallback

- **GIVEN** a streaming turn whose RAG pipeline produces no sources
- **WHEN** the client consumes the stream
- **THEN** no `token` event SHALL be emitted
- **AND** the `done` event's `reply` SHALL be the fallback reply
- **AND** the client SHALL never have displayed any generated text for that turn
