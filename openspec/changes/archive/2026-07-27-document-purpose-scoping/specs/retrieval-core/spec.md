## MODIFIED Requirements

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k) -> list[RetrievalResult]` method, and SHALL provide a `DenseRetriever` implementation that performs pgvector cosine similarity search. All `Retriever` implementations SHALL unconditionally restrict results to chunks whose denormalized `purpose` is `query` — this restriction SHALL NOT be optional or controllable by the caller.

#### Scenario: DenseRetriever matches existing similarity search behavior

- **GIVEN** a tenant schema with document chunks and embeddings, and a fixed query string
- **WHEN** `DenseRetriever.retrieve(query, session, schema, top_k=5)` is called
- **THEN** the returned `document_id`, `chunk_index`, `chunk_text`, and `similarity_score` values for each result SHALL be identical to those previously returned by `EmbeddingService.similarity_search` for the same query and tenant data
- **AND** the result ordering SHALL be identical (descending similarity)

#### Scenario: rag_orchestrator retrieves via the Retriever interface

- **GIVEN** the chat orchestrator needs document context for a query
- **WHEN** `RAGOrchestrator._vector_source` executes
- **THEN** it SHALL call a `Retriever` implementation's `retrieve` method rather than calling `EmbeddingService.similarity_search` directly

#### Scenario: Retrieval excludes training-purpose chunks

- **GIVEN** a tenant schema with chunks from a `purpose='training'` document and chunks from a `purpose='query'` document, both matching a query semantically
- **WHEN** `DenseRetriever.retrieve` is called with that query
- **THEN** the result SHALL NOT include any chunk from the `purpose='training'` document
- **AND** the result MAY include chunks from the `purpose='query'` document

#### Scenario: A chat query cannot bypass the purpose restriction

- **GIVEN** a tenant schema with a `purpose='training'` document's chunks
- **WHEN** `RAGOrchestrator._vector_source` is called with any user-supplied query text, including text naming that document or its content
- **THEN** the retriever's SQL SHALL still exclude `purpose='training'` chunks
- **AND** no caller-supplied parameter SHALL be able to override this restriction
