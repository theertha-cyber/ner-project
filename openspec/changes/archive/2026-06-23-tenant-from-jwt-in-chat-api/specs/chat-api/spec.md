## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`).

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

### Requirement: Conversation CRUD

The system SHALL expose endpoints to create, list, retrieve, and delete conversations. Each conversation SHALL be scoped to a single tenant and user. Messages SHALL be stored with `role` (user/assistant), `content`, and `sources` (JSON array).

#### Scenario: List conversations for a user

- **GIVEN** a user with 3 existing conversations
- **WHEN** a Tenant Admin GETs `/api/v1/chat/conversations`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 3 conversations
- **AND** each conversation SHALL have `id`, `title`, `created_at`, `message_count`

#### Scenario: Get conversation messages

- **GIVEN** a conversation with 5 messages
- **WHEN** a Tenant Admin GETs `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 5 messages
- **AND** each message SHALL have `role`, `content`, `sources`, `created_at`

#### Scenario: Delete conversation

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends DELETE `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 204

#### Scenario: Delete another user's conversation returns 404

- **GIVEN** a conversation owned by user A
- **WHEN** user B sends DELETE to the same conversation
- **THEN** the response SHALL have status 404
