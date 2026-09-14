## MODIFIED Requirements

### Requirement: Centralized retrieval configuration

The system SHALL source chunk size, chunk overlap, retrieval top-k, and embedding model name from a single configuration object (`Settings`) rather than from literals duplicated across multiple files. The system SHALL additionally allow the retrieval-behaviour settings — `retrieval_top_k`, `reranker_enabled`, and `rerank_candidate_count` — to be supplied as a per-retriever-instance or per-call override resolved ahead of the process-global `settings` object, so alternative retrieval configurations can be executed side by side within one process without mutating global state. When no override is supplied, the effective values SHALL be exactly those read from `settings` today.

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

#### Scenario: Per-instance override takes precedence over global settings

- **GIVEN** `settings.reranker_enabled` is `True`
- **AND** a `RerankingRetriever` constructed with a retrieval-configuration override where `reranker_enabled` is `False`
- **WHEN** that retriever's `retrieve` is called
- **THEN** the reranker SHALL NOT be invoked
- **AND** the wrapped retriever's ordering SHALL be returned

#### Scenario: Absent override falls back to global settings

- **GIVEN** a retriever constructed with no retrieval-configuration override
- **WHEN** `retrieve` is called with no explicit `top_k`
- **THEN** the effective `top_k`, `reranker_enabled`, and `rerank_candidate_count` SHALL be those on the global `settings` object

#### Scenario: Overrides do not mutate global settings

- **GIVEN** the process-global `settings` values are recorded before a run
- **WHEN** two retrievers configured with different overrides each execute a retrieval
- **THEN** each retrieval SHALL use its own override values
- **AND** the global `settings` values after the run SHALL be unchanged from the recorded values

#### Scenario: Existing call sites are unaffected

- **GIVEN** the codebase after this change
- **WHEN** the existing retrieval and chat test suites are run without modification
- **THEN** they SHALL pass
