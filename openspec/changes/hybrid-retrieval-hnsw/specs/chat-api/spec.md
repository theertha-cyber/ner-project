## MODIFIED Requirements

### Requirement: pgvector semantic search

The system SHALL perform hybrid search over pre-computed document chunk embeddings and full-text search over chunk text, fusing dense (pgvector cosine similarity) and sparse (PostgreSQL full-text `ts_rank`) rankings via Reciprocal Rank Fusion. The embedding for the user's query SHALL be computed using the same embedding model used at chunk-ingestion time. Fused results SHALL be limited to a configurable top-K (default: 5). When a retrieved chunk has page/location metadata, the resulting citation SHALL include the page number.

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
