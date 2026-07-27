## MODIFIED Requirements

### Requirement: pgvector semantic search

The system SHALL perform semantic search over pre-computed document chunk embeddings using pgvector similarity search. The embedding for the user's query SHALL be computed using the same embedding model used at chunk-ingestion time. Results SHALL be ranked by cosine similarity and limited to a configurable top-K (default: 5). When a retrieved chunk has page/location metadata, the resulting citation SHALL include the page number.

#### Scenario: Semantic search returns relevant chunks

- **GIVEN** document chunks with embeddings for a tenant
- **WHEN** the RAG pipeline performs semantic search with a user query
- **THEN** the result SHALL contain the top-K most similar chunks
- **AND** each result SHALL include `document_id`, `chunk_text`, `similarity_score`

#### Scenario: Semantic search with empty corpus

- **GIVEN** a tenant with no document chunks
- **WHEN** the RAG pipeline performs semantic search
- **THEN** the pipeline SHALL skip the pgvector source
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
