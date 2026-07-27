## MODIFIED Requirements

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k, metadata_filter=None) -> list[RetrievalResult]` method. The system SHALL provide three implementations: `DenseRetriever` (pgvector cosine similarity search using an `hnsw` index), `SparseRetriever` (PostgreSQL full-text search ranked by `ts_rank`), and `HybridRetriever` (runs both concurrently and fuses their ranked results via Reciprocal Rank Fusion). All implementations SHALL support an optional `metadata_filter` dict applied as a database-level `WHERE` clause before ranking.

#### Scenario: DenseRetriever uses the hnsw index

- **GIVEN** a tenant schema with document chunks and embeddings, and a fixed query string
- **WHEN** `DenseRetriever.retrieve(query, session, schema, top_k=5)` is called
- **THEN** the query SHALL execute against the `hnsw` vector index (not `ivfflat`)
- **AND** the returned `document_id`, `chunk_index`, `chunk_text`, and `similarity_score` values SHALL rank in descending similarity order

#### Scenario: rag_orchestrator retrieves via the Retriever interface

- **GIVEN** the chat orchestrator needs document context for a query
- **WHEN** `RAGOrchestrator._vector_source` executes
- **THEN** it SHALL call a `Retriever` implementation's `retrieve` method rather than calling `EmbeddingService.similarity_search` directly

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

### Requirement: Centralized retrieval configuration

The system SHALL source chunk size, chunk overlap, retrieval top-k, and embedding model name from a single configuration object (`Settings`) rather than from literals duplicated across multiple files.

#### Scenario: Default configuration matches prior hardcoded behavior

- **GIVEN** no retrieval-specific environment variables are set
- **WHEN** the application loads configuration
- **THEN** the effective chunk size SHALL be 512, chunk overlap SHALL be 128, retrieval top-k SHALL be 5, and embedding model SHALL be `text-embedding-3-small`, matching the previous hardcoded values

#### Scenario: Configuration is overridable via environment variable

- **GIVEN** the environment variable `NER_RETRIEVAL_TOP_K` is set to `8`
- **WHEN** the application loads configuration
- **THEN** `DenseRetriever` SHALL use `top_k=8` as its default when no explicit `top_k` argument is passed

#### Scenario: HybridRetriever's per-source candidate count is bounded

- **GIVEN** `retrieval_top_k` is set to a large value (e.g., 20)
- **WHEN** `HybridRetriever.retrieve` queries `DenseRetriever` and `SparseRetriever` for fusion candidates
- **THEN** the per-source candidate count requested from each SHALL NOT exceed a fixed cap (e.g., 50), regardless of `top_k`
