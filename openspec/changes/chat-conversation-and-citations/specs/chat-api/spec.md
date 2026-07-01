## ADDED Requirements

### Requirement: Conversation creation endpoint

The system SHALL expose a `POST /api/v1/chat/conversations` endpoint that creates an empty conversation for the authenticated tenant user and returns the new conversation's `id`, `title`, and `created_at`. The title SHALL default to `NULL` for empty conversations.

#### Scenario: Create new empty conversation

- **GIVEN** an authenticated tenant user
- **WHEN** the user sends `POST /api/v1/chat/conversations`
- **THEN** the response SHALL have status 201
- **AND** the response SHALL contain `id` (UUID string)
- **AND** the response SHALL contain `title` (null)
- **AND** the response SHALL contain `created_at` (ISO timestamp)
- **AND** a conversation row SHALL exist in the database for this user

#### Scenario: Create conversation without authentication

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/api/v1/chat/conversations`
- **THEN** the response SHALL have status 401

### Requirement: Citation model with document names

The system SHALL include a `Citation` model in chat responses with fields: `document_name`, `document_id`, `entity_type`, `entity_value`, `confidence`, `context_snippet`, `page_number`. Every citation SHALL have at minimum a `document_name` when the source references a specific document. The existing `Source` model SHALL be retained for widget API compatibility, but the internal chat API (`ChatResponse`) SHALL return `Citation[]` as the `sources` field.

#### Scenario: Chat response includes citations with document names

- **GIVEN** a tenant with extracted entities from documents "report.pdf" and "data.xlsx"
- **WHEN** a user asks "What organizations were found?"
- **THEN** the response SHALL contain `sources` array
- **AND** each source SHALL have `document_name` set to the source document filename
- **AND** each source SHALL have `entity_type` (human-readable name, e.g. "organization")
- **AND** each source SHALL have `entity_value` (the extracted text)
- **AND** each source SHALL have `confidence` (float 0-1)

#### Scenario: SQL aggregate query still returns citations

- **GIVEN** a tenant with extracted ORG entities across 5 documents
- **WHEN** a user asks "How many organizations were found?"
- **THEN** the response `reply` SHALL include the count
- **AND** the response SHALL include citations referencing each document (or top-K if many)

## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations from three RAG sources: structured entity data (via controlled SQL generation), document context (via pgvector semantic search), and live NER inference (via model-serving). The underlying LLM for SQL generation and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`). All citations SHALL be enriched with `document_name` before being returned.

#### Scenario: Chat with simple entity count query

- **GIVEN** a tenant with extracted entities for ORG type
- **WHEN** a Tenant Admin sends `POST /api/v1/chat` with `{"message": "How many organizations did we extract?", "conversation_id": null}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `reply` with a natural language answer
- **AND** the response SHALL contain `sources` array with at least one citation
- **AND** each citation SHALL include `document_name`
- **AND** the response SHALL contain `conversation_id`

#### Scenario: Chat with document context query

- **GIVEN** a tenant with document chunks containing embeddings
- **WHEN** a Tenant Admin sends a question about document content
- **THEN** the response SHALL have status 200
- **AND** the response SHALL reference relevant document chunks in `sources`
- **AND** each source SHALL include `document_id`, `document_name`, `chunk_index`, `relevance_score`

#### Scenario: Chat with NER query

- **GIVEN** a tenant with a promoted NER model
- **WHEN** a user asks about entities in a specific text snippet
- **THEN** the response SHALL include NER results in `sources`
- **AND** the NER source SHALL include `entity_type`, `entity_value`, `confidence`, `document_name`

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables. When generating queries against `extracted_entities`, the system SHOULD include a JOIN with `documents` to return `d.filename` as `document_name`.

#### Scenario: Valid SQL query includes document name

- **GIVEN** a natural language question about organization entities
- **WHEN** the SQL generation produces a query
- **THEN** the query SHOULD join `extracted_entities` with `documents`
- **AND** the query SHOULD include `d.filename` as `document_name` in the SELECT clause
