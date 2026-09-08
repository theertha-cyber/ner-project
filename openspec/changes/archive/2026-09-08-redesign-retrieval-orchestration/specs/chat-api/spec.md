## MODIFIED Requirements

### Requirement: RAG chat endpoint

The system SHALL expose a chat endpoint that accepts a natural language message and a conversation_id from an authenticated tenant user, and returns a response with citations drawn from two retrieval sources: structured entity data (via controlled SQL generation) and document context (via semantic search). Every non-declined turn SHALL run the fixed pipeline guardrail → intent orchestrator → planned retrieval → source assembly → prompt assembly → generation, with no alternative execution path selectable at runtime. The underlying LLM for guardrail classification, orchestration planning, SQL generation, and response synthesis SHALL support both direct OpenAI and Azure OpenAI configurations, selected via environment variables (`NER_AZURE_OPENAI_ENDPOINT`, `NER_AZURE_OPENAI_CHAT_DEPLOYMENT`, `NER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT`).

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

#### Scenario: Responses carry no live-NER sources

- **GIVEN** any successful chat turn
- **WHEN** the response `sources` array is inspected
- **THEN** no entry SHALL have `source_type` of `ner`
- **AND** entity information SHALL be present only where it came from structured retrieval over persisted extraction results

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

### Requirement: Guardrail — blocked question types

The guardrail SHALL act solely as a domain filter on the incoming query, deciding whether the query belongs to the platform's supported domain — the tenant's documents and their extracted entities. Out-of-domain queries SHALL be declined with a graceful message and an empty `sources` array, before the intent orchestrator or any retrieval runs. The decision SHALL be made by an LLM classifier, preceded by deterministic short-circuit checks that decline cross-tenant references and requests for PII not present in extracted entities. The guardrail SHALL NOT assess query complexity, select retrieval capabilities, or influence routing in any way.

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

### Requirement: Guardrail — source citation enforcement

Every chat response SHALL include a `sources` array with at least one citation referencing one or more of the retrieval sources. Responses without any source SHALL be rejected by the guardrail layer before being returned to the user. A domain decline SHALL be exempt from this rule and SHALL return its decline message with an empty `sources` array.

#### Scenario: Response without sources is rejected

- **GIVEN** the pipeline produces a reply with no sources
- **WHEN** the guardrail layer inspects the response
- **THEN** the response SHALL be replaced with "I couldn't find relevant information to answer that question."
- **AND** the event SHALL be logged

#### Scenario: Domain decline keeps its message

- **GIVEN** a query declined as out-of-domain
- **WHEN** the response is returned
- **THEN** the `reply` SHALL be the domain decline message, not the no-sources fallback

### Requirement: pgvector semantic search

The system SHALL perform hybrid search over pre-computed document chunk embeddings and full-text search over chunk text, fusing dense (pgvector cosine similarity) and sparse (PostgreSQL full-text `ts_rank`) rankings via Reciprocal Rank Fusion. The embedding for the search query SHALL be computed using the same embedding model used at chunk-ingestion time. Fused results SHALL be limited to a configurable top-K (default: 5). When a retrieved chunk has page/location metadata, the resulting citation SHALL include the page number. Semantic search SHALL be reachable only through the `semantic_retrieval` capability, whose scope argument selects tenant-wide or document-restricted search.

#### Scenario: Semantic search returns relevant chunks

- **GIVEN** document chunks with embeddings for a tenant
- **WHEN** the orchestrator's plan invokes `semantic_retrieval`
- **THEN** the result SHALL contain the top-K fused-ranked chunks
- **AND** each result SHALL include `document_id`, `chunk_text`, `similarity_score`

#### Scenario: Semantic search with empty corpus

- **GIVEN** a tenant with no document chunks
- **WHEN** `semantic_retrieval` is invoked
- **THEN** the turn SHALL produce no document chunk sources
- **AND** the turn SHALL NOT raise

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

## REMOVED Requirements

### Requirement: NER inference for chat context

**Reason**: Retrieval-time NER re-ran inference over chunks the pipeline had just retrieved, adding one model-serving round trip per chunk for entity information that persistent ingestion-time NER already stores and that structured retrieval already serves. It contributed sources the answer rarely cited and inflated prompt token usage.

**Migration**: Persistent NER at document ingestion is unchanged and remains the source of entity data, reachable through `structured_retrieval`. The `ner_enrichment` graph node, the `ner_entities` state key, `source_type="ner"` response sources, and the NER block in prompt assembly are removed. Portal chat and the embeddable widget must render citation lists that contain no `ner` sources; stored historical messages may still contain them and SHALL continue to render.

### Requirement: Guardrail — query complexity limits

**Reason**: Complexity scoring was a routing decision embedded in the guardrail. It refused legitimate multi-part questions that the intent orchestrator can now serve by planning multiple retrieval operations.

**Migration**: `GuardrailService.assess_complexity` and the "That question requires multiple lookups" decline are removed. Multi-lookup questions now reach the orchestrator, which bounds work through its invocation and deadline budgets instead.
