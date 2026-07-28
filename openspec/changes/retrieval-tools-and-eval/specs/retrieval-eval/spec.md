## ADDED Requirements

### Requirement: Versioned golden set

The system SHALL store the retrieval evaluation golden set as a version-controlled JSONL fixture in the repository, one record per query with fields `query_id` (unique, stable), `query` (natural-language text), `relevant` (a list of `{document_id, chunk_index, grade}` entries where `grade` is an integer 0–3), and optional `notes`. The corpus those judgments refer to SHALL also be committed, so any checkout can reproduce a run without production or tenant data. The loader SHALL validate every record on load and fail loudly on a malformed or duplicate record.

#### Scenario: Golden set loads and validates

- **GIVEN** the committed golden-set JSONL file
- **WHEN** the loader reads it
- **THEN** every record SHALL have a non-empty `query_id`, a non-empty `query`, and a `relevant` list
- **AND** every `relevant` entry SHALL have a `document_id`, an integer `chunk_index`, and a `grade` in `0..3`

#### Scenario: Duplicate query ids are rejected

- **GIVEN** a golden-set file containing two records with the same `query_id`
- **WHEN** the loader reads it
- **THEN** loading SHALL fail with an error naming the duplicated `query_id`

#### Scenario: Judgments reference the committed corpus

- **GIVEN** the committed golden set and corpus fixtures
- **WHEN** every `relevant` entry is resolved against the corpus
- **THEN** each referenced `(document_id, chunk_index)` pair SHALL exist in the corpus

#### Scenario: Golden set contains no tenant or production data

- **GIVEN** the committed corpus fixture
- **WHEN** its provenance is inspected
- **THEN** every document SHALL be synthetic content authored for evaluation
- **AND** no document SHALL originate from a live tenant schema

### Requirement: Retrieval metrics

The system SHALL compute, for each evaluated query and each configuration, `recall@k`, `precision@k`, `MRR@k`, and `nDCG@k` over the ranked list of retrieved chunks, matching results to judgments on `(document_id, chunk_index)`. `nDCG` SHALL use graded relevance; the remaining metrics SHALL treat any `grade >= 1` as relevant. Aggregate metrics SHALL be the unweighted mean across queries, and the aggregate report SHALL state the query count.

#### Scenario: Perfect ranking scores 1.0

- **GIVEN** a query with three relevant chunks and a retrieval result listing exactly those three chunks in grade order at ranks 1–3
- **WHEN** metrics are computed at `k=5`
- **THEN** `recall@5` SHALL be `1.0` and `nDCG@5` SHALL be `1.0`
- **AND** `MRR@5` SHALL be `1.0`

#### Scenario: Empty result set scores zero without error

- **GIVEN** a query with at least one relevant chunk and a retrieval result of zero chunks
- **WHEN** metrics are computed
- **THEN** `recall@k`, `precision@k`, `MRR@k`, and `nDCG@k` SHALL all be `0.0`
- **AND** no exception SHALL be raised

#### Scenario: Rank position affects MRR and nDCG but not recall

- **GIVEN** two result lists containing the same single relevant chunk, at rank 1 in one and rank 4 in the other
- **WHEN** metrics are computed at `k=5`
- **THEN** `recall@5` SHALL be equal for both
- **AND** `MRR@5` and `nDCG@5` SHALL be strictly greater for the rank-1 list

#### Scenario: Graded relevance is honoured by nDCG

- **GIVEN** two result lists of the same length, one ranking a `grade=3` chunk above a `grade=1` chunk and the other reversing them
- **WHEN** `nDCG@k` is computed for both
- **THEN** the first SHALL score strictly higher

#### Scenario: A query with no judgments is excluded, not scored as zero

- **GIVEN** a golden-set record whose `relevant` list is empty
- **WHEN** aggregate metrics are computed
- **THEN** that query SHALL be excluded from the aggregate means
- **AND** the report SHALL record it as skipped with a reason

### Requirement: Evaluation executes through the tool layer

The system SHALL execute each golden-set query by invoking the `search_documents` retrieval tool, not by calling `Retriever` implementations directly, so the harness measures the same path the agentic loop will use and exercises the tool contract as a byproduct.

#### Scenario: Eval run invokes the tool layer

- **GIVEN** an eval run configured with a spy tool registry
- **WHEN** the runner evaluates a golden set of N queries
- **THEN** the `search_documents` tool SHALL be invoked exactly N times per configuration

#### Scenario: Tool errors are recorded, not fatal

- **GIVEN** a golden set of N queries where one query's tool invocation returns a `ToolResult` with `error` set
- **WHEN** the eval run completes
- **THEN** the run SHALL evaluate the remaining `N-1` queries
- **AND** the report SHALL list the failed query with its error

### Requirement: Configuration matrix comparison

The system SHALL execute the same golden set under multiple named retrieval configurations in a single run — at minimum dense-only, hybrid, and hybrid-with-reranking, with `retrieval_top_k` and `rerank_candidate_count` variable per configuration — and produce a side-by-side comparison of aggregate metrics. Applying a configuration SHALL NOT mutate process-global settings in a way that persists past the run.

#### Scenario: Matrix run produces per-configuration metrics

- **GIVEN** a matrix defining three named configurations
- **WHEN** the runner executes the golden set
- **THEN** the report SHALL contain one aggregate metrics block per named configuration
- **AND** each block SHALL be labelled with that configuration's name and its parameter values

#### Scenario: Configurations do not leak between runs

- **GIVEN** a matrix run that includes a configuration with reranking disabled followed by one with reranking enabled
- **WHEN** the run completes
- **THEN** the effective global settings SHALL equal their pre-run values
- **AND** the reranking-enabled configuration's results SHALL reflect reranking having been applied

#### Scenario: Per-query results are retained alongside aggregates

- **GIVEN** a completed matrix run
- **WHEN** the JSON report is inspected
- **THEN** it SHALL contain per-query metrics for each configuration, keyed by `query_id`
- **AND** aggregate metrics SHALL be reproducible from the per-query values

### Requirement: Report output

The system SHALL emit each evaluation run as a machine-readable JSON report and a human-readable Markdown summary. The report SHALL record run timestamp, golden-set identifier and record count, every configuration's parameters, per-query and aggregate metrics, skipped queries with reasons, and failed queries with errors.

#### Scenario: JSON report is complete and machine-readable

- **GIVEN** a completed eval run
- **WHEN** the JSON report is parsed
- **THEN** it SHALL contain `run_timestamp`, `golden_set`, `query_count`, `configurations`, `per_query`, and `aggregate` fields

#### Scenario: Markdown summary ranks configurations

- **GIVEN** a completed matrix run over more than one configuration
- **WHEN** the Markdown summary is read
- **THEN** it SHALL present aggregate metrics per configuration
- **AND** it SHALL identify which configuration scored highest on `nDCG@5`

### Requirement: Baseline regression gate

The system SHALL store a committed baseline metrics file and provide a gate that compares a fresh run's aggregate `recall@5` and `nDCG@5` against that baseline, failing when either falls more than a configured tolerance below it. The gate SHALL run only under an explicit pytest marker or CLI invocation, never as part of the default unit-test run, because it requires a live database and embedding backend.

#### Scenario: Regression below tolerance fails the gate

- **GIVEN** a committed baseline with `nDCG@5 = 0.80` and a tolerance of `0.02`
- **WHEN** a run produces `nDCG@5 = 0.70`
- **THEN** the gate SHALL fail
- **AND** the failure message SHALL name the metric, the baseline value, and the observed value

#### Scenario: Movement within tolerance passes

- **GIVEN** a committed baseline with `nDCG@5 = 0.80` and a tolerance of `0.02`
- **WHEN** a run produces `nDCG@5 = 0.79`
- **THEN** the gate SHALL pass

#### Scenario: Improvement passes and is reported

- **GIVEN** a committed baseline
- **WHEN** a run scores above baseline on both gated metrics
- **THEN** the gate SHALL pass
- **AND** the summary SHALL report the deltas as improvements

#### Scenario: Gate is excluded from the default test run

- **GIVEN** the codebase after this change
- **WHEN** the default `pytest` invocation is run without the eval marker
- **THEN** no golden-set evaluation SHALL execute
- **AND** no embedding or database call SHALL be made by the eval modules

#### Scenario: Missing baseline is an explicit failure

- **GIVEN** no committed baseline metrics file
- **WHEN** the gate is invoked
- **THEN** it SHALL fail with an explicit message instructing how to generate and commit a baseline
- **AND** it SHALL NOT silently pass

### Requirement: Deterministic offline evaluation

The system SHALL make a default evaluation run deterministic and free of external API calls by using committed precomputed embeddings for golden-set queries and corpus chunks. Live embedding generation SHALL be available behind an explicit opt-in flag. Repeating a run over an unchanged golden set, corpus, and configuration SHALL produce identical metrics.

#### Scenario: Default run makes no embedding API call

- **GIVEN** the committed precomputed embeddings and no opt-in flag
- **WHEN** an eval run executes
- **THEN** no request SHALL be made to the embedding provider

#### Scenario: Repeated runs are identical

- **GIVEN** an unchanged golden set, corpus, and configuration
- **WHEN** the eval run is executed twice
- **THEN** the aggregate metrics of both runs SHALL be identical

#### Scenario: Stale precomputed embeddings are detected

- **GIVEN** committed embeddings recorded against one embedding model name and a configuration naming a different embedding model
- **WHEN** an eval run starts
- **THEN** the run SHALL fail with an explicit mismatch error naming both models
- **AND** it SHALL NOT score the run against embeddings from the wrong model
