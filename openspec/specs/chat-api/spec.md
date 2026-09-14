## Purpose

Provide a RAG chatbot API that allows tenant users to query extracted entities, document content, and perform live NER inference through a natural language chat interface, with controlled SQL generation and guardrails.
## Requirements
### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations drawn from the pipeline's retrieval sources: structured entity data (via controlled SQL generation) and document context (via pgvector semantic search). Every non-declined turn SHALL run the fixed pipeline guardrail → intent orchestrator → planned retrieval → source assembly → prompt assembly → generation, with no alternative execution path selectable at runtime. The underlying LLM for guardrail classification, orchestration planning, SQL generation, and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`). Document context supplied to the LLM SHALL be assembled under a token budget and labeled with each chunk's document filename and page number where available.

A chat turn SHALL have one of two terminal outcomes: an answer produced from retrieved evidence, or — when entity resolution is enabled and the message's entity reference is ambiguous — a clarification request produced without retrieval. A clarification response SHALL have status 200, an empty `sources` array, the standard disclaimer, and an additive `pending_clarification` field carrying the ordered candidate list. The `pending_clarification` field SHALL be absent for every non-clarification response, so existing clients are unaffected. Both user message and clarification reply SHALL be persisted to the conversation as ordinary chat messages.

The system SHALL additionally expose a streaming sibling of this endpoint at `POST /api/v1/chat/stream`, which accepts the same request body and authentication and delivers the same answer incrementally as Server-Sent Events. Both endpoints SHALL run the same RAG pipeline, apply the same guardrails, and persist the same rows; they differ only in how the response is delivered.

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

#### Scenario: Responses carry no live-NER sources

- **GIVEN** any successful chat turn
- **WHEN** the response `sources` array is inspected
- **THEN** no entry SHALL have `source_type` of `ner`
- **AND** entity information SHALL be present only where it came from structured retrieval over persisted extraction results

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

#### Scenario: Streaming and non-streaming endpoints answer identically

- **GIVEN** the same tenant, conversation state, question, and scripted LLM
- **WHEN** the question is sent to `POST /api/v1/chat` and to `POST /api/v1/chat/stream`
- **THEN** the non-streaming JSON body and the streaming `done` payload SHALL carry the same `reply`, `sources`, `answer_kind`, `model_version`, and `disclaimer`

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

### Requirement: SQL query generation and validation

The system SHALL generate SQL queries from natural language questions, validate them against a whitelist-based SQL validation layer, and execute them in read-only transactions with a 10-second timeout. The SQL validation layer SHALL restrict queries to SELECT only, limit to whitelisted table names and column names, enforce a LIMIT clause, and reject UNION, subqueries on non-whitelisted relations, and JOINs on non-whitelisted tables. Structured entity questions SHALL be answered against the normalized `document_entities` table, which holds one row per complete logical entity; `extracted_entities` (raw per-token BIO predictions) SHALL NOT be exposed to SQL generation, so generated SQL never reconstructs BIO sequences at query time.

Generation, validation, and execution SHALL be performed as a bounded attempt loop rather than a single pass: the system SHALL retry a failed attempt with feedback about the previous attempt, up to a configured maximum number of attempts, and SHALL stop immediately on the first successful attempt. Every attempt SHALL pass through the same validation layer and the same read-only execution path, against the schema bound from authenticated request context. The generation context SHALL include the tenant's entity types together with a bounded sample of representative values from that tenant's own data. When all attempts fail, the failure SHALL be reported to the retrieval pipeline as an error and SHALL NOT be presented as a successful empty result.

The validation layer SHALL resolve **every** table reference in the statement, not only the first identifier following each `FROM` or `JOIN` keyword. Comma-separated table lists, `CROSS JOIN`, schema-qualified names, and table references inside subqueries SHALL each be resolved and checked against the whitelist. A statement containing any reference that does not resolve to an unqualified whitelisted table name SHALL be rejected. The validation layer SHALL additionally reject any statement containing `SET ROLE` or `SET SESSION AUTHORIZATION`.

The query model presented to the generator SHALL be the tenant's generated relational surface — `subject` and the active `e_<slug>` child tables — and not the EAV entity store. `document_entities` SHALL remain whitelisted and granted so that static-table questions and the generator's grounding and defect probes continue to work, but the generator SHALL NOT be instructed to query it, to filter on `entity_type`, or to self-join it to assemble a subject.

The whitelisted table set SHALL include the generated relational entity tables for the querying tenant, resolved per schema from `entity_definitions` rather than from a static constant. The execution role's `SELECT` grants SHALL be resolved from the **same** resolver, so the granted set and the validated set cannot drift apart. Tables belonging to definitions whose `is_active` is false SHALL be excluded from both, even though the tables themselves are retained. Tables belonging to definitions whose current cardinality is `single` SHALL likewise be excluded from both: a `single` definition's values are a column on `subject`, so its identifier names no relation the reconciler maintains. Such a table may nonetheless exist, retained from a period when the definition was `multi`, and the projection stops writing to it at the moment of the flip — granting or validating it would place a permanently empty relation on the query surface, where a query returns zero rows rather than an error. Because grants are otherwise append-only, provisioning SHALL revoke the execution role's table privileges in a tenant schema before re-granting the current surface, so a table that leaves the surface does not keep the `SELECT` it held while it was on it. Because the query surface consists of physical tables, the existing `pg_tables`-based `IF EXISTS` guard on each grant SHALL continue to apply unchanged.

The whitelisted **column** set SHALL be resolved from that same surface rather than restated: the static tables keep their declared columns, `subject` contributes its identity columns and one column per active `single` definition, and each active child table contributes the fixed child column shape. A column reference the validation layer cannot attribute to a specific relation SHALL be accepted rather than rejected, so a parser gap degrades into a database error rather than a false rejection of a correct query.

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

### Requirement: pgvector semantic search

The system SHALL perform hybrid search over pre-computed document chunk embeddings and full-text search over chunk text, fusing dense (pgvector cosine similarity) and sparse (PostgreSQL full-text `ts_rank`) rankings via Reciprocal Rank Fusion. The embedding for the user's query SHALL be computed using the same embedding model used at chunk-ingestion time. Fused results SHALL be limited to a configurable top-K (default: 5). When a retrieved chunk has page/location metadata, the resulting citation SHALL include the page number. Semantic search SHALL be reachable only through the `semantic_retrieval` capability, whose scope argument selects tenant-wide or document-restricted search.

#### Scenario: Semantic search returns relevant chunks

- **GIVEN** document chunks with embeddings for a tenant
- **WHEN** the RAG pipeline performs hybrid search with a user query
- **THEN** the result SHALL contain the top-K fused-ranked chunks
- **AND** each result SHALL include `document_id`, `chunk_text`, `similarity_score`

#### Scenario: Semantic search with empty corpus

- **GIVEN** a tenant with no document chunks
- **WHEN** the RAG pipeline performs hybrid search
- **THEN** the pipeline SHALL skip the document-context source
- **AND** the response SHALL not include document chunk sources

#### Scenario: Citation includes page number when the chunk has one

- **GIVEN** a retrieved document chunk with `page_number=3`
- **WHEN** `RAGOrchestrator._enrich_citations` builds the citation for that chunk's source
- **THEN** the resulting `Citation.page_number` SHALL equal `3`

#### Scenario: Citation page number is null for chunks without metadata

- **GIVEN** a retrieved document chunk with no `page_number` (ingested before this change)
- **WHEN** `RAGOrchestrator._enrich_citations` builds the citation for that chunk's source
- **THEN** the resulting `Citation.page_number` SHALL be `None`
- **AND** citation enrichment SHALL NOT raise an exception

#### Scenario: Chat retrieves relevant document context for a lexical (exact-term) query

- **GIVEN** a tenant with a document chunk containing a specific identifier or exact term
- **WHEN** a user asks a question containing that exact term
- **THEN** the response SHALL cite the document chunk containing that term, even if it has low semantic/embedding similarity to the query

### Requirement: Citation model with document names and entity type names

The system SHALL include a `Citation` model in chat responses with fields: `document_name`, `document_id`, `entity_type`, `entity_value`, `confidence`, `context_snippet`, `page_number`. Every citation SHALL have at minimum a `document_name` when the source references a specific document. The `entity_type` field SHALL contain a human-readable name (e.g. "organization" not "ORG") resolved from the `entity_definitions` table during enrichment. The existing `Source` model SHALL be retained for widget API compatibility, but the internal chat API (`ChatResponse`) SHALL return `Citation[]` as the `sources` field.

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

### Requirement: Citation enrichment with entity type resolution

The citation enrichment layer SHALL resolve both `document_id → document_name` and `entity_id → entity_type_name` via batch queries before returning citations. Document names SHALL be resolved from `{tenant_schema}.documents`. Entity type names SHALL be resolved from `public.entity_definitions` via schema-qualified JOIN. If a source has a null `document_id` or `entity_id`, the corresponding enrichment step SHALL be skipped for that source and the field SHALL remain null on the Citation.

#### Scenario: Citation enrichment resolves entity type names

- **GIVEN** a source with `entity_id` referencing `entity_definitions.id`
- **WHEN** the enrichment layer processes the source
- **THEN** the resulting Citation SHALL have `entity_type` set to the human-readable name from `entity_definitions.name`
- **AND** the enrichment query SHALL use schema-qualified `public.entity_definitions` for cross-schema access

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

Every chat response that answers a question SHALL include a `sources` array with at least one citation referencing one or more of the retrieval sources. Answers without any source SHALL be rejected by the guardrail layer before being returned to the user.

Two response classes are exempt because they answer no question and assert no fact about tenant data: blocked-question and out-of-domain declines, and entity-resolution clarification requests. Exempt responses SHALL carry an empty `sources` array and SHALL NOT be replaced by the guardrail layer. A clarification request SHALL be exempt only when it was produced by the resolver without any generation model call; a model-generated reply SHALL always be subject to citation enforcement.

The guardrail SHALL distinguish an empty-sources turn in which every attempted retrieval **succeeded and legitimately found nothing** from one in which any attempted retrieval **failed**, and SHALL return a different reply for each. It SHALL NOT return the same message for both. The distinction SHALL be derived from the turn's retrieval status, not re-inferred from message content.

On the streaming endpoint, this rejection SHALL be decided before any generated content is emitted to the client. Because the guardrail's only input is the turn's assembled sources — which are fully determined before generation begins — the system SHALL evaluate source presence at generation entry and SHALL NOT emit any `token` event for a turn whose sources are empty. A user SHALL never be shown generated text that the guardrail subsequently replaces.

#### Scenario: Response without sources is rejected

- **GIVEN** the RAG pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with "I couldn't find relevant information to answer that question."
- **AND** the event SHALL be logged

#### Scenario: Domain decline keeps its message

- **GIVEN** a query declined as out-of-domain
- **WHEN** the response is returned
- **THEN** the `reply` SHALL be the domain decline message, not the no-sources fallback

#### Scenario: Clarification request is not replaced by the guardrail

- **GIVEN** a clarification reply assembled by the resolver with no generation call
- **WHEN** the response is returned
- **THEN** the clarification text SHALL be preserved verbatim
- **AND** `sources` SHALL be empty

#### Scenario: Generated answer after selection still requires citations

- **GIVEN** a resumed turn after a successful candidate selection
- **WHEN** generation produces a reply with no sources
- **THEN** citation enforcement SHALL apply as it does for any other answer

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

#### Scenario: Empty-sources turn emits no tokens before the fallback

- **GIVEN** a streaming turn whose RAG pipeline produces no sources
- **WHEN** the client consumes the stream
- **THEN** no `token` event SHALL be emitted
- **AND** the `done` event's `reply` SHALL be the fallback reply
- **AND** the client SHALL never have displayed any generated text for that turn

### Requirement: Guardrail — blocked question types

The guardrail SHALL act solely as a domain filter on the incoming query, deciding whether the query belongs to the platform's supported domain — the tenant's documents and their extracted entities. Out-of-domain queries SHALL be declined with a graceful message and an empty `sources` array, before the intent orchestrator or any retrieval runs. The decision SHALL be made by an LLM classifier, preceded by deterministic short-circuit checks that decline cross-tenant references and requests for PII not present in extracted entities. The guardrail SHALL NOT assess query complexity, select retrieval capabilities, or influence routing in any way.

#### Scenario: Blocked question returns graceful decline

- **GIVEN** a user asks "Write an email to the team"
- **WHEN** the chat endpoint processes the message
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a graceful decline message
- **AND** the response SHALL have an empty `sources` array

#### Scenario: Out-of-domain question returns graceful decline

- **GIVEN** a user asks "Who is the American president?"
- **WHEN** the chat endpoint processes the message
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a graceful decline message stating the assistant answers questions about the tenant's documents and extracted entities
- **AND** the response SHALL have an empty `sources` array
- **AND** neither the orchestrator nor any retrieval capability SHALL be invoked

#### Scenario: Chit-chat and general-knowledge prompts are declined

- **GIVEN** the queries "Tell me a joke." and "What's the weather today?"
- **WHEN** each is processed
- **THEN** each SHALL be declined with the domain decline message
- **AND** no retrieval SHALL occur for either

#### Scenario: In-domain question proceeds to orchestration

- **GIVEN** a user asks "Which contracts mention Acme Corp?"
- **WHEN** the guardrail classifies the query
- **THEN** the query SHALL be admitted
- **AND** the intent orchestrator SHALL run

#### Scenario: Cross-tenant reference is short-circuited without an LLM call

- **GIVEN** a user query naming a tenant schema other than the requesting tenant's
- **WHEN** the guardrail processes it
- **THEN** the query SHALL be declined
- **AND** no classifier LLM call SHALL be made

#### Scenario: Classifier failure fails open

- **GIVEN** a classifier LLM call that raises
- **WHEN** the guardrail processes an admitted-format query
- **THEN** the query SHALL proceed to the orchestrator
- **AND** the classifier failure SHALL be logged
- **AND** the turn SHALL still refuse to answer without sources per the source-citation guardrail

#### Scenario: Multi-lookup questions are no longer refused

- **GIVEN** a question requiring several distinct lookups
- **WHEN** the chat endpoint processes it
- **THEN** the query SHALL NOT be declined for complexity
- **AND** the orchestrator SHALL decide how many retrieval operations to plan

### Requirement: Configurable chat API service URL

The chat API service URL SHALL be configurable via a `chat_api_url` setting that defaults to `http://localhost:8006`. The gateway proxy SHALL use this setting to route chat API requests, allowing Docker compose to override it with a service-specific URL.

#### Scenario: Gateway proxies to configured URL

- **GIVEN** a running gateway with `chat_api_url` set to `http://chat_api:8000`
- **WHEN** a chat request is proxied
- **THEN** the request SHALL be sent to `http://chat_api:8000/api/v1/chat/...`

#### Scenario: Default URL works for local development

- **GIVEN** a running gateway with default settings
- **WHEN** a chat request is proxied
- **THEN** the request SHALL be sent to `http://localhost:8006/api/v1/chat/...`

### Requirement: Disclaimer in every response

Every chat response SHALL include a disclaimer string in the response body indicating that the answer was AI-generated and may contain errors. The disclaimer SHALL NOT be included in the `reply` text itself but as a separate `disclaimer` field in the response JSON.

#### Scenario: Response includes disclaimer field

- **GIVEN** a successful chat response
- **WHEN** the response is returned
- **THEN** the response SHALL contain a `disclaimer` field
- **AND** the disclaimer SHALL read "This answer was generated by AI and may contain errors. Verify important information against source documents."

### Requirement: Per-request authorization context isolation

The chat API SHALL NOT carry per-request authorization context on shared service instances. The `RAGOrchestrator` and every collaborator it holds (`SQLGenerator`, `EmbeddingService`, `NERClient`, `RerankingRetriever`, `CrossEncoderReranker`, `GuardrailService`) SHALL be free of request-scoped mutable attributes. Request-scoped values SHALL be passed as call arguments or carried in execution state.

#### Scenario: Orchestrator singleton holds no request-scoped state

- **GIVEN** the module-level `orchestrator` instances in `src/chat_api/api/v1/chat.py` and `src/chat_api/api/v1/public.py`
- **WHEN** a chat request completes
- **THEN** no attribute of the orchestrator or of any object it holds has been assigned a value derived from that request
- **AND** the tenant id, JWT token, schema name, and database session are visible only in the per-request execution state

#### Scenario: Interleaved tenant requests do not leak tokens

- **GIVEN** requests for tenant A and tenant B executing concurrently in one process
- **WHEN** tenant B's flow reaches the reranking stage between tenant A's retrieval and tenant A's reranking
- **THEN** tenant A's rerank request carries tenant A's Authorization header
- **AND** tenant B's rerank request carries tenant B's Authorization header

### Requirement: Reranked document context

The chat pipeline SHALL rerank retrieved document chunks with a cross-encoder before selecting which chunks are assembled into the LLM prompt, so that the chunks surviving the pipeline's truncation are those the reranker scores most relevant. Reranking SHALL apply only to the document-chunk source; the structured SQL source and the NER source SHALL be unaffected. A reranking failure SHALL degrade result ordering only and SHALL NOT fail the chat request.

#### Scenario: A relevant chunk ranked below the truncation cutoff is promoted into context

- **GIVEN** a tenant whose document chunks include one chunk that answers the user's question but is not among the top 3 by embedding similarity
- **AND** reranking is enabled
- **WHEN** the user sends that question to the chat endpoint
- **THEN** the response SHALL have status 200
- **AND** the chunk that answers the question SHALL appear in the response `sources`

#### Scenario: Chat succeeds with unreranked ordering when the reranker is unavailable

- **GIVEN** reranking is enabled but the reranking service is unavailable
- **WHEN** a user sends a question that matches document chunks
- **THEN** the response SHALL have status 200
- **AND** the response SHALL still contain document chunk sources
- **AND** the response SHALL still contain at least one citation

#### Scenario: Reranking does not alter the structured entity source

- **GIVEN** a question that produces both SQL results and document chunk results
- **AND** reranking is enabled
- **WHEN** the chat pipeline assembles its sources
- **THEN** the SQL source SHALL be unchanged by reranking
- **AND** only document chunk ordering SHALL be affected

### Requirement: Automatic conversation title generation

When a chat message is sent with `conversation_id: null` (creating a new conversation), the system SHALL derive a short title from that first user message and persist it to the new conversation's `title` field. The title SHALL be produced by collapsing whitespace, stripping leading/trailing punctuation, and truncating to a maximum of 60 characters at a word boundary (appending `…` when truncated). If the derived title would be empty, the system SHALL fall back to `"New conversation"`. Title generation SHALL NOT invoke an external LLM call or add measurable latency to the chat response.

#### Scenario: Title generated from a short first message

- **GIVEN** a user with no existing conversation sends `POST /api/v1/chat` with `{"message": "How many organizations did we extract last month?", "conversation_id": null}`
- **THEN** a new conversation SHALL be created
- **AND** the conversation's `title` SHALL be set to a non-null string derived from the message text
- **AND** subsequent `GET /api/v1/chat/conversations` SHALL return that title for the conversation

#### Scenario: Title truncated for a long first message

- **GIVEN** a first message longer than 60 characters
- **WHEN** the conversation is created
- **THEN** the persisted `title` SHALL be at most 60 characters
- **AND** the truncation SHALL occur at a word boundary, not mid-word
- **AND** the title SHALL end with `…`

#### Scenario: Empty-content first message falls back to placeholder title

- **GIVEN** a first message consisting only of whitespace or punctuation
- **WHEN** the conversation is created
- **THEN** the persisted `title` SHALL be `"New conversation"`

#### Scenario: Title is generated once and not overwritten by later messages

- **GIVEN** a conversation that already has a non-null `title`
- **WHEN** the user sends another message with that conversation's `conversation_id`
- **THEN** the conversation's `title` SHALL remain unchanged

### Requirement: Rename conversation endpoint

The system SHALL expose `PATCH /api/v1/chat/conversations/{conv_id}` that allows the authenticated owner of a conversation to set its `title` to a caller-supplied value. The request body SHALL contain a `title` field constrained to 1-100 characters after trimming whitespace. The endpoint SHALL be scoped to the conversation's owning tenant and user, matching the existing DELETE endpoint's ownership semantics.

#### Scenario: Owner renames their conversation

- **GIVEN** a conversation owned by user A with `title: "New conversation"`
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with `{"title": "Q3 entity counts"}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the updated `title` value `"Q3 entity counts"`
- **AND** a subsequent `GET /api/v1/chat/conversations/{conv_id}` SHALL return the updated title

#### Scenario: Renaming another user's conversation returns 404

- **GIVEN** a conversation owned by user A
- **WHEN** user B sends `PATCH /api/v1/chat/conversations/{conv_id}` with a new title
- **THEN** the response SHALL have status 404

#### Scenario: Renaming with an empty title is rejected

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with `{"title": "   "}`
- **THEN** the response SHALL have status 422

#### Scenario: Renaming with an over-length title is rejected

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with a `title` longer than 100 characters
- **THEN** the response SHALL have status 422

#### Scenario: Renaming requires authentication

- **GIVEN** no JWT token
- **WHEN** a PATCH request is sent to `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 401

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

### Requirement: Structured entity value columns are queryable through the SQL path

The system SHALL include the `document_entities` semantic value columns — `value_kind`, `value_number`, `value_number_high`, `value_unit`, `value_date`, and `value_date_high` — in the SQL generation whitelist so that generated queries MAY filter, compare, sort, and aggregate on them. The schema description supplied to the SQL generator SHALL state that comparison and range predicates belong on the typed columns and that equality matching on entity text belongs on `normalized_value`. All existing validation rules — SELECT only, whitelisted tables, enforced LIMIT, no UNION, no non-whitelisted subqueries or JOINs, read-only transaction, 10-second timeout — SHALL remain unchanged.

#### Scenario: Numeric comparison query passes validation

- **GIVEN** a natural language question asking for candidates with more than two years of experience
- **WHEN** the SQL generation produces `SELECT d.filename AS document_name, e.value_number FROM document_entities e JOIN documents d ON d.id = e.document_id WHERE e.entity_type = 'YEARS_OF_EXP' AND e.value_number > 2 LIMIT 100`
- **THEN** the validation layer SHALL pass the query
- **AND** the query SHALL be executed in a read-only transaction

#### Scenario: Date comparison query passes validation

- **GIVEN** a question asking which certifications have expired
- **WHEN** the SQL generation produces a query filtering `entity_type = 'CERTIFICATION_EXPIRY' AND value_date < CURRENT_DATE`
- **THEN** the validation layer SHALL pass the query

#### Scenario: Non-whitelisted column is still rejected

- **GIVEN** a generated query referencing a `document_entities` column that is not in the whitelist
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query

#### Scenario: Text-only queries continue to work

- **GIVEN** a question asking which documents mention AWS
- **WHEN** the SQL generation produces a query filtering `normalized_value = 'aws'`
- **THEN** the validation layer SHALL pass the query
- **AND** the behaviour SHALL be identical to before this change

