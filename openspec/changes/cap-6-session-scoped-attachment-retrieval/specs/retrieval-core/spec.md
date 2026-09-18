## MODIFIED Requirements

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k, metadata_filter=None) -> list[RetrievalResult]` method. The system SHALL provide three implementations: `DenseRetriever` (pgvector cosine similarity search using an `hnsw` index), `SparseRetriever` (PostgreSQL full-text search ranked by `ts_rank`), and `HybridRetriever` (runs both concurrently and fuses their ranked results via Reciprocal Rank Fusion). All implementations SHALL support an optional `metadata_filter` dict applied as a database-level `WHERE` clause before ranking. All `Retriever` implementations SHALL unconditionally restrict results to chunks whose denormalized `purpose` is `query` — this restriction SHALL NOT be optional or controllable by the caller.

All `Retriever` implementations SHALL additionally apply an unconditional conversation-visibility restriction: a chunk SHALL be admitted only when its denormalized `conversation_id` is absent, or equals the conversation the retrieval is being performed for. The conversation SHALL be supplied by the caller's authenticated request context rather than through `metadata_filter`, and no value of `metadata_filter` SHALL widen the set of chunks this restriction admits. When no conversation is supplied, only chunks with an absent `conversation_id` SHALL be admitted.

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

#### Scenario: Retrieval excludes chunks owned by another conversation

- **GIVEN** a tenant schema with chunks from a document whose `conversation_id` is conversation A, and chunks from a library document whose `conversation_id` is absent, both matching a query semantically
- **WHEN** `DenseRetriever.retrieve` is called for conversation B
- **THEN** the result SHALL NOT include any chunk whose `conversation_id` is conversation A
- **AND** the result MAY include chunks from the library document

#### Scenario: Retrieval includes chunks owned by the current conversation

- **GIVEN** a tenant schema with chunks from a document whose `conversation_id` is conversation A
- **WHEN** `DenseRetriever.retrieve` is called for conversation A with a semantically matching query
- **THEN** the result MAY include those chunks

#### Scenario: metadata_filter cannot widen conversation visibility

- **GIVEN** a tenant schema with chunks from a document owned by conversation A
- **WHEN** `retrieve` is called for conversation B with `metadata_filter={"document_ids": ["<conversation A's document id>"]}`
- **THEN** the result SHALL be empty
- **AND** no caller-supplied parameter SHALL be able to override the conversation restriction

#### Scenario: Retrieval without a conversation admits only unowned chunks

- **GIVEN** a tenant schema with conversation-owned chunks and library chunks, both matching a query
- **WHEN** `retrieve` is called with no conversation supplied
- **THEN** the result SHALL contain only chunks whose `conversation_id` is absent

#### Scenario: SparseRetriever returns full-text matches

- **GIVEN** a tenant schema with document chunks whose `chunk_text` contains an exact term
- **WHEN** `SparseRetriever.retrieve(query, session, schema, top_k=5)` is called with that term as the query
- **THEN** the result SHALL include the chunk containing that exact term
- **AND** results SHALL be ranked by `ts_rank` descending

#### Scenario: SparseRetriever applies the same conversation restriction as DenseRetriever

- **GIVEN** a tenant schema with a chunk owned by conversation A whose `chunk_text` contains an exact term
- **WHEN** `SparseRetriever.retrieve` is called for conversation B with that term as the query
- **THEN** the result SHALL NOT include that chunk

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

## ADDED Requirements

### Requirement: Chunks carry denormalized conversation ownership

Each `document_chunks` row SHALL carry a nullable `conversation_id` denormalized from the document it was derived from, in the same way `purpose` is denormalized, so that retrieval can evaluate conversation visibility without joining `documents`. Chunks derived from a document with no conversation owner SHALL carry a null `conversation_id`.

#### Scenario: Ingesting a conversation-owned document stamps its chunks

- **GIVEN** a document ingested with a conversation owner
- **WHEN** the processing worker writes that document's chunks
- **THEN** every chunk row SHALL carry that document's `conversation_id`

#### Scenario: Ingesting a library document leaves chunk ownership null

- **GIVEN** a document ingested with no conversation owner
- **WHEN** the processing worker writes that document's chunks
- **THEN** every chunk row SHALL carry a null `conversation_id`

#### Scenario: Chunks written before this change remain retrievable

- **GIVEN** `document_chunks` rows created before the `conversation_id` column existed
- **WHEN** the migration adds the column and retrieval runs for any conversation
- **THEN** those rows SHALL have a null `conversation_id`
- **AND** they SHALL remain retrievable exactly as they were before this change
