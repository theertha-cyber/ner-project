## ADDED Requirements

### Requirement: Cross-encoder reranking endpoint

The model-serving layer SHALL expose an internal reranking endpoint that accepts a query string and a list of candidate texts, scores each (query, candidate) pair with a cross-encoder model, and returns the candidates' original indices with relevance scores in descending score order. The reranker model SHALL be a single tenant-agnostic model shared across all tenants, loaded lazily as a process-level singleton rather than through the per-tenant model cache. The model name SHALL be configurable.

#### Scenario: Rerank reorders candidates by relevance

- **GIVEN** the reranking endpoint is available
- **WHEN** POST to `/internal/v1/rerank` with a query and a list of candidate texts where a later-positioned candidate is more relevant to the query than earlier ones
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a `results` array of objects each having `index` and `score`
- **AND** the results SHALL be ordered by `score` descending
- **AND** the more relevant candidate's original `index` SHALL appear before the less relevant ones

#### Scenario: Rerank respects the requested top_k

- **GIVEN** the reranking endpoint is available
- **WHEN** POST to `/internal/v1/rerank` with 10 candidate texts and `top_k` of 3
- **THEN** the response `results` array SHALL contain exactly 3 entries

#### Scenario: Rerank with an empty candidate list

- **GIVEN** the reranking endpoint is available
- **WHEN** POST to `/internal/v1/rerank` with a query and an empty `documents` list
- **THEN** the response SHALL have status 200
- **AND** the response `results` array SHALL be empty
- **AND** no model inference SHALL be performed

#### Scenario: Reranker model is not held in the per-tenant model cache

- **GIVEN** the reranker has been loaded by serving at least one rerank request
- **WHEN** the per-tenant model cache contents are inspected
- **THEN** the reranker model SHALL NOT be present as a cache entry
- **AND** loading tenant models to the point of LRU eviction SHALL NOT evict the reranker

#### Scenario: Rerank returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** POST to `/internal/v1/rerank` with a valid body
- **THEN** the response SHALL have status 403
