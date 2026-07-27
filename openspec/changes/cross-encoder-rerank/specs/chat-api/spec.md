## ADDED Requirements

### Requirement: Reranked document context

The chat pipeline SHALL rerank retrieved document chunks with a cross-encoder before selecting which chunks are assembled into the LLM prompt, so that the chunks surviving the pipeline's truncation are those the reranker scores most relevant. Reranking SHALL apply only to the document-chunk source; the structured SQL source and the NER source SHALL be unaffected. A reranking failure SHALL degrade result ordering only and SHALL NOT fail the chat request.

#### Scenario: A relevant chunk ranked below the truncation cutoff is promoted into context

- **GIVEN** a tenant whose document chunks include one chunk that answers the user's question but is not among the top 3 by embedding similarity
- **AND** reranking is enabled
- **WHEN** the user sends that question to the chat endpoint
- **THEN** the response SHALL have status 200
- **AND** the chunk that answers the question SHALL appear in the response `sources`

#### Scenario: Chat succeeds with unreranked ordering when the reranker is unavailable

- **GIVEN** reranking is enabled but the reranking service is unavailable
- **WHEN** a user sends a question that matches document chunks
- **THEN** the response SHALL have status 200
- **AND** the response SHALL still contain document chunk sources
- **AND** the response SHALL still contain at least one citation

#### Scenario: Reranking does not alter the structured entity source

- **GIVEN** a question that produces both SQL results and document chunk results
- **AND** reranking is enabled
- **WHEN** the chat pipeline assembles its sources
- **THEN** the SQL source SHALL be unchanged by reranking
- **AND** only document chunk ordering SHALL be affected
