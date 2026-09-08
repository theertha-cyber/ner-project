## ADDED Requirements

### Requirement: Reranker interface

The system SHALL define a `Reranker` interface (structural protocol) with a `rerank(query, results, top_k) -> list[RetrievalResult] | None` method, and SHALL provide a `CrossEncoderReranker` implementation that delegates scoring to the model-serving reranking endpoint. The implementation SHALL return `None` (rather than raising) when the reranking service is unreachable, errors, or times out.

#### Scenario: CrossEncoderReranker reorders results by cross-encoder score

- **GIVEN** a list of `RetrievalResult` objects and a query
- **WHEN** `CrossEncoderReranker.rerank` is called and the reranking service returns scores that rank a later result highest
- **THEN** the returned list SHALL be ordered by the service's scores descending
- **AND** each returned item SHALL be a `RetrievalResult` preserving its original `document_id`, `chunk_index`, and `chunk_text`

#### Scenario: CrossEncoderReranker returns None when the service is unavailable

- **GIVEN** the reranking service is unreachable or times out
- **WHEN** `CrossEncoderReranker.rerank` is called
- **THEN** it SHALL return `None`
- **AND** it SHALL NOT raise an exception

### Requirement: Reranking retriever composition

The system SHALL provide a `RerankingRetriever` that implements the `Retriever` protocol by wrapping another `Retriever` and a `Reranker`. When reranking is enabled it SHALL request a configurable candidate count from the wrapped retriever, rerank those candidates, and return at most `top_k` results. When reranking is disabled or the reranker returns no result, it SHALL return the wrapped retriever's own ordering truncated to `top_k`.

#### Scenario: RerankingRetriever over-fetches candidates then truncates to top_k

- **GIVEN** reranking is enabled with a candidate count of 20
- **WHEN** `RerankingRetriever.retrieve` is called with `top_k=5`
- **THEN** the wrapped retriever SHALL be asked for 20 results
- **AND** the reranker SHALL be given those candidates
- **AND** the returned list SHALL contain at most 5 results

#### Scenario: RerankingRetriever falls back to original order when reranking fails

- **GIVEN** reranking is enabled but the reranker returns `None`
- **WHEN** `RerankingRetriever.retrieve` is called with `top_k=5`
- **THEN** the result SHALL be the wrapped retriever's original ordering truncated to 5
- **AND** no exception SHALL propagate to the caller

#### Scenario: RerankingRetriever bypasses reranking when disabled

- **GIVEN** the reranking feature flag is disabled
- **WHEN** `RerankingRetriever.retrieve` is called with `top_k=5`
- **THEN** the wrapped retriever SHALL be asked for 5 results, not the larger candidate count
- **AND** the reranker SHALL NOT be invoked

#### Scenario: RerankingRetriever satisfies the Retriever protocol

- **GIVEN** a `RerankingRetriever` wrapping any `Retriever` implementation
- **WHEN** it is used anywhere a `Retriever` is expected
- **THEN** its `retrieve` method SHALL accept the same arguments as the wrapped retriever's and return `list[RetrievalResult]`

### Requirement: Reranking configuration

The system SHALL source the reranking feature flag, reranker model name, and rerank candidate count from the shared configuration object.

#### Scenario: Reranking defaults are applied when no environment overrides are set

- **GIVEN** no reranking-specific environment variables are set
- **WHEN** the application loads configuration
- **THEN** reranking SHALL be enabled by default
- **AND** the rerank candidate count SHALL be 20
- **AND** the reranker model name SHALL default to a cross-encoder model identifier

#### Scenario: Reranking can be disabled via environment variable

- **GIVEN** the environment variable `NER_RERANKER_ENABLED` is set to `false`
- **WHEN** the application loads configuration
- **THEN** `RerankingRetriever` SHALL bypass reranking
