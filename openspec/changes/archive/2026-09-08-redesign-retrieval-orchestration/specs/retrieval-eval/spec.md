## MODIFIED Requirements

### Requirement: Evaluation executes through the tool layer

The system SHALL execute each golden-set query by invoking the `semantic_retrieval` capability, not by calling `Retriever` implementations directly, so the harness measures the same path the chat pipeline uses and exercises the capability contract as a byproduct.

#### Scenario: Eval run invokes the capability layer

- **GIVEN** an eval run configured with a spy capability registry
- **WHEN** the runner evaluates a golden set of N queries
- **THEN** the `semantic_retrieval` capability SHALL be invoked exactly N times per baseline configuration

#### Scenario: Capability errors are recorded, not fatal

- **GIVEN** a golden set of N queries where one query's invocation returns a result with `error` set
- **WHEN** the eval run completes
- **THEN** the run SHALL evaluate the remaining `N-1` queries
- **AND** the report SHALL list the failed query with its error

## ADDED Requirements

### Requirement: Orchestrated configuration is measured against the direct baseline

The harness SHALL support an orchestrated configuration that runs each golden-set query through the Intent Orchestrator's plan-and-execute path and scores the accumulated evidence with the existing metric functions, producing results directly comparable to the direct `semantic_retrieval` baseline configurations in the same report.

#### Scenario: Orchestrated configuration appears in the report

- **GIVEN** the golden set and an eval run including the orchestrated configuration
- **WHEN** the report is produced
- **THEN** the report SHALL contain `recall@5` and `nDCG@5` for the orchestrated configuration alongside the baseline configurations
- **AND** the configurations SHALL be ranked by `nDCG@5`

#### Scenario: Orchestration failures during eval do not abort the run

- **GIVEN** an eval run in which one query's planning call errors
- **WHEN** the run completes
- **THEN** the remaining queries SHALL still be scored
- **AND** the failed query SHALL be recorded with its degraded status in the per-query results

#### Scenario: Configuration fields match the orchestrator's budgets

- **GIVEN** the matrix configuration model
- **WHEN** its orchestration fields are inspected
- **THEN** they SHALL express the plan invocation cap and the wall-clock deadline
- **AND** SHALL NOT express loop iteration counts or observation character limits
