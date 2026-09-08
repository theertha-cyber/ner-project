## ADDED Requirements

### Requirement: A labelled entity fixture covers every observed failure class

The system SHALL provide an evaluation fixture of documents with human-labelled expected entities, drawn from real tenant documents. The fixture SHALL contain at least one case for each of: correct extractions that must survive unchanged, entity-type misclassification, fragmented multi-token spans, malformed values including trailing punctuation and Unicode format characters, repeated mentions, duration and numeric values, dates, organization names, and person names.

#### Scenario: Fixture coverage is enforced

- **GIVEN** the entity evaluation fixture
- **WHEN** the harness loads it
- **THEN** the harness SHALL fail if any required failure class has no case

#### Scenario: Fixture cases derive from real documents

- **GIVEN** a fixture case
- **WHEN** it is inspected
- **THEN** it SHALL reference a real tenant document and the source text supporting each expected entity

### Requirement: Entity-level metrics are computed per configuration

The evaluation harness SHALL compute entity precision, entity recall, entity F1, exact-value accuracy, entity-type accuracy, and hallucination rate for each configuration under test. Hallucination rate SHALL count entities emitted with no substring support in the source document, and entities present after post-processing that correspond to no BERT candidate.

#### Scenario: All required metrics are reported

- **GIVEN** a completed evaluation run
- **WHEN** its report is produced
- **THEN** the report SHALL contain precision, recall, F1, exact-value accuracy, entity-type accuracy, and hallucination rate for every configuration

#### Scenario: An unsupported emitted value counts as a hallucination

- **GIVEN** a configuration that emits an entity value not present in the source document text
- **WHEN** metrics are computed
- **THEN** that entity SHALL be counted in the hallucination rate

#### Scenario: An entity with no BERT candidate counts as a hallucination

- **GIVEN** a post-processed result containing an entity that traces to no submitted candidate
- **WHEN** metrics are computed
- **THEN** that entity SHALL be counted in the hallucination rate

### Requirement: Three configurations are compared so the LLM's contribution is isolated

The harness SHALL evaluate three configurations over the same fixture: BERT-only as it behaves before this change; BERT with the deterministic repairs; and BERT with the deterministic repairs plus LLM post-processing. Reporting SHALL attribute improvements between adjacent configurations, so gains from deterministic repairs are not credited to post-processing.

#### Scenario: All three configurations are reported

- **GIVEN** an evaluation run
- **WHEN** the report is produced
- **THEN** it SHALL contain results for all three configurations
- **AND** it SHALL report the delta between each adjacent pair

#### Scenario: A deterministic-only gain is attributed correctly

- **GIVEN** a fixture case fixed by the deterministic repairs alone
- **WHEN** the report is produced
- **THEN** the improvement SHALL appear in the delta between BERT-only and BERT-with-repairs
- **AND** it SHALL NOT appear in the delta attributed to post-processing

### Requirement: Downstream structured-query success is measured

The retrieval evaluation suite SHALL report a structured-query success rate: for each golden query whose expected answer requires `document_entities`, whether the generated SQL returned the expected rows. Entity-quality changes SHALL be scored on this metric, not on value appearance alone.

#### Scenario: Structured-query success is reported per configuration

- **GIVEN** golden queries in the `simple_structured`, `exact_entity_lookup`, and `attribute_filtering` classes
- **WHEN** the retrieval evaluation runs against a configuration
- **THEN** the report SHALL contain a structured-query success rate for that configuration

#### Scenario: A query unreachable by exact match is scored as a failure

- **GIVEN** a golden query whose expected rows exist but are unreachable because a stored value carries a Unicode format character
- **WHEN** the structured-query success rate is computed
- **THEN** that query SHALL be scored as a failure

### Requirement: A post-processing configuration must pass a quality gate before being offered

A post-processing configuration SHALL NOT be offered as a selectable processing mode unless its hallucination rate on the fixture is zero and its structured-query success rate does not regress against the BERT-with-repairs configuration. An improvement in F1 alone SHALL NOT satisfy the gate.

#### Scenario: A hallucinating configuration is blocked

- **GIVEN** a post-processing configuration whose hallucination rate on the fixture is greater than zero
- **WHEN** the gate is evaluated
- **THEN** the gate SHALL fail
- **AND** the configuration SHALL NOT be offered as a processing mode

#### Scenario: A configuration that regresses retrieval is blocked

- **GIVEN** a post-processing configuration with improved entity F1 but a lower structured-query success rate than BERT-with-repairs
- **WHEN** the gate is evaluated
- **THEN** the gate SHALL fail

#### Scenario: A passing configuration is recorded with its model and prompt version

- **GIVEN** a configuration that satisfies the gate
- **WHEN** the result is recorded
- **THEN** the record SHALL name the post-processor model and prompt version evaluated
