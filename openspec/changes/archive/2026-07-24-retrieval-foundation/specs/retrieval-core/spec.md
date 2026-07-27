## ADDED Requirements

### Requirement: Typed retrieval domain model

The system SHALL represent document chunks and retrieval results using typed models (`Chunk`, `RetrievalResult`) shared by the document ingestion pipeline and the chat retrieval pipeline, instead of passing untyped dicts between layers.

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

### Requirement: Retriever interface

The system SHALL define a `Retriever` interface (structural protocol) with a `retrieve(query, session, schema, top_k) -> list[RetrievalResult]` method, and SHALL provide a `DenseRetriever` implementation that performs pgvector cosine similarity search.

#### Scenario: DenseRetriever matches existing similarity search behavior

- **GIVEN** a tenant schema with document chunks and embeddings, and a fixed query string
- **WHEN** `DenseRetriever.retrieve(query, session, schema, top_k=5)` is called
- **THEN** the returned `document_id`, `chunk_index`, `chunk_text`, and `similarity_score` values for each result SHALL be identical to those previously returned by `EmbeddingService.similarity_search` for the same query and tenant data
- **AND** the result ordering SHALL be identical (descending similarity)

#### Scenario: rag_orchestrator retrieves via the Retriever interface

- **GIVEN** the chat orchestrator needs document context for a query
- **WHEN** `RAGOrchestrator._vector_source` executes
- **THEN** it SHALL call a `Retriever` implementation's `retrieve` method rather than calling `EmbeddingService.similarity_search` directly

### Requirement: Single chunking implementation

The system SHALL implement text chunking in exactly one shared module used by both the document ingestion service and the chat API, with no duplicate chunking function elsewhere in the codebase.

#### Scenario: Ingestion and chat share one chunking function

- **GIVEN** the codebase after this change
- **WHEN** searching for chunking implementations (fixed-size token splitting with overlap)
- **THEN** exactly one implementation SHALL exist in `src/shared/retrieval`
- **AND** `src/document_service/services/ocr_worker.py` SHALL import and call that implementation instead of defining its own `_chunk_text`

#### Scenario: Chunking output is unchanged for existing documents

- **GIVEN** a document's full extracted text used to produce N chunks under the old `_chunk_text` (512 tokens, 128 overlap)
- **WHEN** the same text is chunked by the shared implementation with the equivalent default configuration
- **THEN** the resulting chunk boundaries and chunk count SHALL be identical to the old implementation's output

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
