## MODIFIED Requirements

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

### Requirement: Single chunking implementation

The system SHALL implement text chunking in exactly one shared module used by both the document ingestion service and the chat API, with no duplicate chunking function elsewhere in the codebase. Chunking SHALL be performed per source span (page), so a single chunk never contains text from more than one span.

#### Scenario: Ingestion and chat share one chunking function

- **GIVEN** the codebase after this change
- **WHEN** searching for chunking implementations (fixed-size token splitting with overlap)
- **THEN** exactly one implementation SHALL exist in `src/shared/retrieval`
- **AND** `src/document_service/services/ocr_worker.py` SHALL import and call that implementation instead of defining its own `_chunk_text`

#### Scenario: A chunk never spans more than one page

- **GIVEN** a document with two spans, span A on page 0 and span B on page 1
- **WHEN** the document is ingested and chunked
- **THEN** no resulting `Chunk` SHALL contain text drawn from both span A and span B
- **AND** each `Chunk`'s `page_number` SHALL match exactly one of the source spans' `page_number`

#### Scenario: Empty spans produce no chunks

- **GIVEN** a document text span whose text is empty or whitespace-only
- **WHEN** the document is chunked
- **THEN** no `Chunk` SHALL be produced for that span
