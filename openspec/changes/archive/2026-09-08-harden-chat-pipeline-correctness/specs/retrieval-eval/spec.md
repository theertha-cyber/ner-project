# retrieval-eval

## ADDED Requirements

### Requirement: Degraded and failed queries score zero

A golden-set query whose run degraded, errored, or was abandoned SHALL contribute a zero score to the aggregate rather than being marked skipped and excluded from the mean. Exclusion from the mean SHALL be reserved for queries that were never dispatched for a reason unrelated to system behaviour.

#### Scenario: Orchestrator failure scores zero

- **GIVEN** a golden-set query whose orchestrated run reported a retrieval failure
- **WHEN** metrics are computed
- **THEN** the query SHALL contribute zero recall, precision, MRR, and nDCG to the aggregate
- **AND** the query SHALL be counted in the aggregate denominator

#### Scenario: Degraded planning scores zero

- **GIVEN** a golden-set query whose run substituted the degraded fallback plan
- **WHEN** metrics are computed
- **THEN** the query SHALL contribute zero to the aggregate
- **AND** the run SHALL record that it degraded

#### Scenario: Aggregate reports failure counts alongside scores

- **GIVEN** an eval run containing both successful and failed queries
- **WHEN** the aggregate is produced
- **THEN** the aggregate SHALL report the number of degraded and failed queries
- **AND** the reported score SHALL be computed over every dispatched query

#### Scenario: Baseline is regenerated for the new scoring rule

- **GIVEN** a stored baseline produced under the prior skip-based scoring
- **WHEN** the regression gate compares a run under the new scoring rule
- **THEN** the comparison SHALL use a baseline regenerated under the new rule
- **AND** the baseline's metadata SHALL identify the scoring rule it was produced under

### Requirement: Answer-level correctness evaluation

The eval suite SHALL include a harness that evaluates the final answer, not only chunk ranking. Each case SHALL name a question and the facts the answer must contain, and SHALL pass only when the produced reply contains them. Retrieval ranking metrics alone SHALL NOT be treated as evidence that the pipeline answers correctly.

#### Scenario: Answer containing the required facts passes

- **GIVEN** an answer-level case naming a question and its required facts
- **WHEN** the pipeline produces a reply containing every required fact
- **THEN** the case SHALL pass

#### Scenario: Answer omitting a required fact fails

- **GIVEN** an answer-level case whose required facts include a value the reply omits
- **WHEN** the case is evaluated
- **THEN** the case SHALL fail
- **AND** the report SHALL name the omitted fact

#### Scenario: Answer asserting absence of retrievable data fails

- **GIVEN** an answer-level case whose required fact exists in the tenant's data
- **AND** a reply stating that the information could not be found
- **WHEN** the case is evaluated
- **THEN** the case SHALL fail

### Requirement: Query-class evaluation coverage

The eval suite SHALL cover the query classes the investigation exercised: simple structured aggregation, exact entity lookup, attribute filtering, multi-condition questions, multi-document comparison, ambiguous entity references, document-content questions, and mixed structured-plus-semantic questions. Each class SHALL have at least one case.

#### Scenario: Multi-document comparison is covered

- **GIVEN** the eval suite
- **WHEN** its cases are enumerated
- **THEN** at least one case SHALL name two subjects and require facts about both
- **AND** the case SHALL fail if the reply carries evidence for only one subject

#### Scenario: Multi-condition question is covered

- **GIVEN** the eval suite
- **WHEN** its cases are enumerated
- **THEN** at least one case SHALL carry conditions composing with AND
- **AND** the case SHALL record the plan shape the orchestrator produced

#### Scenario: Failed-retrieval turn is covered

- **GIVEN** an eval case constructed so that structured retrieval fails
- **WHEN** the case is evaluated
- **THEN** the case SHALL assert that the reply does not claim the data is absent
- **AND** the case SHALL assert that the turn's retrieval status reports the failure

#### Scenario: Every class has at least one case

- **GIVEN** the enumerated query classes
- **WHEN** the suite is validated
- **THEN** each class SHALL map to at least one case
- **AND** a class with no case SHALL fail suite validation

### Requirement: Evaluation runs against tenant-representative data

The eval suite SHALL be runnable against a tenant-representative corpus in addition to the synthetic fixture corpus. The configuration used for a reported run SHALL identify which corpus produced it, so a score against the synthetic fixture is never presented as evidence about tenant behaviour.

#### Scenario: Run identifies its corpus

- **GIVEN** any completed eval run
- **WHEN** its report is produced
- **THEN** the report SHALL name the corpus the run used

#### Scenario: Synthetic-fixture score is not a tenant claim

- **GIVEN** a run against the synthetic fixture corpus
- **WHEN** its report is compared against a tenant-corpus baseline
- **THEN** the comparison SHALL be rejected as incomparable
- **AND** the rejection SHALL name the corpus mismatch

#### Scenario: Tenant-corpus run is reproducible from configuration

- **GIVEN** a tenant-corpus eval configuration
- **WHEN** the run is repeated with the same configuration
- **THEN** the corpus selection and the query set SHALL be identical between runs
