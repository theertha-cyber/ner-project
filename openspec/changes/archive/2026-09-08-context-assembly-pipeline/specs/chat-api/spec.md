## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`). Document context supplied to the LLM SHALL be assembled under a token budget and labeled with each chunk's document filename and page number where available.

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

#### Scenario: Document context sent to the LLM is not character-truncated

- **GIVEN** a tenant with a retrieved document chunk of approximately 512 tokens
- **WHEN** a user asks a question that retrieves that chunk
- **THEN** the context supplied to the LLM SHALL contain the chunk's full text
- **AND** the chunk SHALL NOT be reduced to a fixed character-length fragment

#### Scenario: Document context sent to the LLM identifies its source document by name

- **GIVEN** a retrieved chunk from a document named `report.pdf` on page 3
- **WHEN** a user asks a question that retrieves that chunk
- **THEN** the context supplied to the LLM SHALL identify the chunk's source as `report.pdf`
- **AND** the response SHALL still contain a citation for that chunk
