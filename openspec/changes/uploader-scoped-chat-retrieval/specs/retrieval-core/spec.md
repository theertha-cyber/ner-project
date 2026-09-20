## MODIFIED Requirements

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k, metadata_filter=None) -> list[RetrievalResult]` method. The system SHALL provide three implementations: `DenseRetriever` (pgvector cosine similarity search using an `hnsw` index), `SparseRetriever` (PostgreSQL full-text search ranked by `ts_rank`), and `HybridRetriever` (runs both concurrently and fuses their ranked results via Reciprocal Rank Fusion). All implementations SHALL support an optional `metadata_filter` dict applied as a database-level `WHERE` clause before ranking. All `Retriever` implementations SHALL unconditionally restrict results to chunks whose denormalized `purpose` is `query` — this restriction SHALL NOT be optional or controllable by the caller.

All `Retriever` implementations SHALL additionally apply the uploader-visibility rule as a second unconditional, database-level restriction, evaluated before ranking and derived from the requesting user carried on the retrieval context. The restriction SHALL be expressed against the chunk row's denormalized ingesting actor and uploading user, SHALL NOT be reachable through `metadata_filter`, and SHALL NOT be optional or controllable by the caller. A `metadata_filter` MAY narrow the result further; it SHALL NOT widen it.

#### Scenario: DenseRetriever uses the hnsw index

- **GIVEN** a tenant schema with document chunks and embeddings, and a fixed query string
- **WHEN** `DenseRetriever.retrieve(query, session, schema, top_k=5)` is called
- **THEN** the query SHALL execute against the `hnsw` vector index (not `ivfflat`)
- **AND** the returned `document_id`, `chunk_index`, `chunk_text`, and `similarity_score` values SHALL rank in descending similarity order

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

#### Scenario: Dense retrieval excludes another user's human-ingested chunks

- **GIVEN** a tenant schema holding a `purpose='query'` document ingested by one human and another ingested by a second human, both matching a query semantically
- **WHEN** `DenseRetriever.retrieve` runs for the first user
- **THEN** no returned result SHALL come from the second user's document
- **AND** results MAY come from the first user's document

#### Scenario: Sparse retrieval excludes another user's human-ingested chunks

- **GIVEN** the tenant schema from the preceding scenario and a term appearing in both documents
- **WHEN** `SparseRetriever.retrieve` runs for the first user with that term
- **THEN** no returned result SHALL come from the second user's document

#### Scenario: Source-system chunks remain retrievable by every user

- **GIVEN** a `purpose='query'` document whose ingesting actor is a source system
- **WHEN** any non-administrative user of that tenant retrieves with a matching query
- **THEN** the result MAY include that document's chunks

#### Scenario: metadata_filter cannot widen the uploader restriction

- **GIVEN** a tenant schema holding a `purpose='query'` document ingested by a different human
- **WHEN** `retrieve` is called for a non-administrative user with `metadata_filter={"document_id": "<that document's id>"}`
- **THEN** the result SHALL be empty
- **AND** no exception SHALL be raised

#### Scenario: An administrator is unscoped by the uploader restriction

- **GIVEN** a tenant schema holding documents ingested by several humans
- **WHEN** retrieval runs for a requesting user whose role is `tenant_admin`
- **THEN** results MAY come from any of those documents

#### Scenario: SparseRetriever returns full-text matches

- **GIVEN** a tenant schema with document chunks whose `chunk_text` contains an exact term
- **WHEN** `SparseRetriever.retrieve(query, session, schema, top_k=5)` is called with that term as the query
- **THEN** the result SHALL include the chunk containing that exact term
- **AND** results SHALL be ranked by `ts_rank` descending

#### Scenario: SparseRetriever returns no error on zero matches

- **GIVEN** a tenant schema with document chunks whose text has no overlap with the query
- **WHEN** `SparseRetriever.retrieve` is called with that query
- **THEN** the result SHALL be an empty list
- **AND** no exception SHALL be raised

#### Scenario: HybridRetriever fuses dense and sparse results via RRF

- **GIVEN** a tenant schema with a chunk that matches the query both semantically (high dense similarity) and lexically (exact term match)
- **WHEN** `HybridRetriever.retrieve(query, session, schema, top_k=5)` is called
- **THEN** that chunk SHALL rank at or near the top of the fused result list
- **AND** the fused result list SHALL contain at most `top_k` results

#### Scenario: HybridRetriever includes dense-only matches when sparse search returns nothing

- **GIVEN** a query with strong semantic similarity to a chunk but no lexical/keyword overlap
- **WHEN** `SparseRetriever` returns zero matches for that query but `DenseRetriever` returns that chunk
- **AND** `HybridRetriever.retrieve` is called with the same query
- **THEN** the fused result list SHALL still include that chunk

#### Scenario: metadata_filter restricts results to one document

- **GIVEN** a tenant schema with chunks from two different documents, both matching the query
- **WHEN** `retrieve` is called with `metadata_filter={"document_id": "<one of the two document ids>"}`
- **THEN** every returned `RetrievalResult` SHALL have that `document_id`
- **AND** no result from the other document SHALL be returned
