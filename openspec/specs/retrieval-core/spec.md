# retrieval-core

## Purpose

Typed domain models, a pluggable `Retriever` interface, a single shared chunking implementation, and centralized retrieval configuration used by document ingestion and chat retrieval, so later retrieval strategies (hybrid search, reranking, agentic tool loops) can be added without reworking call sites.

## Requirements

### Requirement: Typed retrieval domain model

The system SHALL represent document chunks and retrieval results using typed models (`Chunk`, `RetrievalResult`) shared by the document ingestion pipeline and the chat retrieval pipeline, instead of passing untyped dicts between layers. Both models SHALL carry optional page/location metadata (`page_number`, `char_start`, `char_end`) so a chunk can be attributed back to its source page when that metadata is available.

#### Scenario: Ingestion produces typed chunks

- **GIVEN** a document has been text-extracted into spans
- **WHEN** the shared chunking function splits the text into chunks
- **THEN** each chunk SHALL be represented as a `Chunk` model instance with `chunk_index` and `chunk_text` fields
- **AND** the ingestion code SHALL NOT construct or pass raw `dict` objects for chunk data between the chunking step and the storage step

#### Scenario: Retrieval returns typed results

- **GIVEN** a similarity search is executed for a query
- **WHEN** the retriever returns matching chunks
- **THEN** each result SHALL be a `RetrievalResult` model instance exposing `document_id`, `chunk_index`, `chunk_text`, and `similarity_score`
- **AND** `rag_orchestrator` SHALL consume `RetrievalResult` objects, not raw dicts, when building `Source` objects

#### Scenario: Chunk carries page metadata when produced from a span

- **GIVEN** a document text span with `page_number=2`, `char_start=100`, `char_end=400`
- **WHEN** the shared chunking function chunks that span's text
- **THEN** every resulting `Chunk` SHALL have `page_number` equal to `2`
- **AND** each `Chunk`'s `char_start`/`char_end` SHALL fall within the span's `[100, 400]` range

#### Scenario: RetrievalResult exposes page metadata when present

- **GIVEN** a `document_chunks` row with `page_number=2`, `char_start=100`, `char_end=250`
- **WHEN** `DenseRetriever.retrieve` returns that row as a result
- **THEN** the `RetrievalResult` SHALL have `page_number == 2`, `char_start == 100`, `char_end == 250`

#### Scenario: RetrievalResult metadata is None for chunks ingested before this change

- **GIVEN** a `document_chunks` row with `page_number`, `char_start`, `char_end` all `NULL`
- **WHEN** `DenseRetriever.retrieve` returns that row as a result
- **THEN** the `RetrievalResult` SHALL have `page_number`, `char_start`, `char_end` all `None`
- **AND** no exception SHALL be raised

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k, metadata_filter=None) -> list[RetrievalResult]` method. The system SHALL provide three implementations: `DenseRetriever` (pgvector cosine similarity search using an `hnsw` index), `SparseRetriever` (PostgreSQL full-text search ranked by `ts_rank`), and `HybridRetriever` (runs both concurrently and fuses their ranked results via Reciprocal Rank Fusion). All implementations SHALL support an optional `metadata_filter` dict applied as a database-level `WHERE` clause before ranking. All `Retriever` implementations SHALL unconditionally restrict results to chunks whose denormalized `purpose` is `query` — this restriction SHALL NOT be optional or controllable by the caller.

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

### Requirement: Single chunking implementation

The system SHALL implement text chunking in exactly one shared module used by both the document ingestion service and the chat API, with no duplicate chunking function elsewhere in the codebase. Chunking SHALL be performed per source span (page), so a single chunk never contains text from more than one span.

#### Scenario: Ingestion and chat share one chunking function

- **GIVEN** the codebase after this change
- **WHEN** searching for chunking implementations (fixed-size token splitting with overlap)
- **THEN** exactly one implementation SHALL exist in `src/shared/retrieval`
- **AND** `src/document_service/services/ocr_worker.py` SHALL import and call that implementation instead of defining its own `_chunk_text`

#### Scenario: Chunking output is unchanged for existing documents

- **GIVEN** a document's full extracted text used to produce N chunks under the old `_chunk_text` (512 tokens, 128 overlap)
- **WHEN** the same text is chunked by the shared implementation with the equivalent default configuration
- **THEN** the resulting chunk boundaries and chunk count SHALL be identical to the old implementation's output

#### Scenario: A chunk never spans more than one page

- **GIVEN** a document with two spans, span A on page 0 and span B on page 1
- **WHEN** the document is ingested and chunked
- **THEN** no resulting `Chunk` SHALL contain text drawn from both span A and span B
- **AND** each `Chunk`'s `page_number` SHALL match exactly one of the source spans' `page_number`

#### Scenario: Empty spans produce no chunks

- **GIVEN** a document text span whose text is empty or whitespace-only
- **WHEN** the document is chunked
- **THEN** no `Chunk` SHALL be produced for that span

### Requirement: Citation enrichment executes without error

The system SHALL successfully execute the SQL used to resolve document filenames during citation enrichment when a response includes one or more sources with a `document_id`.

#### Scenario: Document name resolution succeeds for a chat response with document sources

- **GIVEN** a chat response includes at least one `Source` with a `document_id`
- **WHEN** `RAGOrchestrator._enrich_citations` runs
- **THEN** the document filename lookup query SHALL execute without raising a `NameError`
- **AND** the resulting `Citation` objects SHALL have `document_name` populated from the `documents` table when the document exists

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
