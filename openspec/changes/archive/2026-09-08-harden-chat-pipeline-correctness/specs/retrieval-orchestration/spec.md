# retrieval-orchestration

## ADDED Requirements

### Requirement: Per-invocation retrieval status

Plan execution SHALL record, for every plan entry, a status drawn from the closed set `not_attempted`, `ok`, `empty`, and `failed`, together with the underlying error text when the status is `failed`. The orchestration result SHALL expose these per-invocation statuses to its caller. A collapsed signal that fires only when every invocation of a capability kind fails SHALL NOT be the sole error channel, because it erases partial failure.

#### Scenario: One of two structured invocations fails

- **GIVEN** a plan with two `structured_retrieval` entries
- **AND** the first raises a generation failure and the second returns rows
- **WHEN** the plan is executed
- **THEN** the result SHALL report status `failed` for the first entry with its error text
- **AND** the result SHALL report status `ok` for the second entry
- **AND** the rows from the second entry SHALL still be accumulated

#### Scenario: Rejected entry is distinguishable from a failed one

- **GIVEN** a plan entry rejected at validation time and never dispatched
- **WHEN** the plan is executed
- **THEN** the entry SHALL report status `not_attempted`
- **AND** the entry SHALL NOT report status `empty`

#### Scenario: Legitimate empty result is distinguishable from failure

- **GIVEN** a `structured_retrieval` entry whose validated query executed and matched no rows
- **WHEN** the plan is executed
- **THEN** the entry SHALL report status `empty`
- **AND** the entry SHALL report no error text

#### Scenario: Underlying error text survives accumulation

- **GIVEN** a `structured_retrieval` entry that fails with a specific database error
- **WHEN** the orchestration result is produced
- **THEN** the entry's recorded error SHALL retain the specific failure detail
- **AND** the result SHALL NOT replace it with only a generic all-invocations-failed string

### Requirement: Retrieval status reaches the answer model

The turn's per-invocation retrieval status SHALL be propagated from plan execution through graph state to prompt assembly. A state field carrying retrieval outcome SHALL have at least one consumer that renders it into the generation prompt. No retrieval failure SHALL be represented to the answer model as an absence of data.

#### Scenario: Failed structured retrieval is visible in the prompt

- **GIVEN** a turn whose only `structured_retrieval` entry failed
- **WHEN** the generation prompt is assembled
- **THEN** the prompt SHALL contain a retrieval-status statement naming the structured source as failed
- **AND** the prompt SHALL NOT present the turn as one where no matching data exists

#### Scenario: Fully successful turn carries no failure statement

- **GIVEN** a turn in which every attempted capability reported `ok` or `empty`
- **WHEN** the generation prompt is assembled
- **THEN** the prompt SHALL NOT contain any failure statement

#### Scenario: Degraded planning is surfaced rather than silent

- **GIVEN** a turn in which the planning call raised and the degraded fallback plan was substituted
- **WHEN** the turn completes
- **THEN** the turn's retrieval status SHALL record that planning degraded and the stop reason
- **AND** that record SHALL be readable by prompt assembly and by the response payload

### Requirement: Bounded structured-to-semantic recovery

When a plan contains no `semantic_retrieval` entry and every `structured_retrieval` entry reported `empty`, the system SHALL perform exactly one additional `semantic_retrieval` invocation using the turn's original question, subject to the existing retrieval deadline and invocation budget. This recovery SHALL NOT re-invoke the planner, SHALL NOT iterate, and SHALL be attempted at most once per turn.

#### Scenario: Structured-only plan returning nothing recovers semantically

- **GIVEN** a plan containing a single `structured_retrieval` entry and no semantic entry
- **AND** that entry executed successfully and matched no rows
- **WHEN** plan execution completes its dispatched entries
- **THEN** the system SHALL invoke `semantic_retrieval` once with the turn's original question
- **AND** any chunks it returns SHALL be accumulated into the turn's evidence
- **AND** the recovery invocation SHALL appear in the turn's retrieval status

#### Scenario: Recovery is not attempted when a semantic entry already ran

- **GIVEN** a plan containing both a structured and a semantic entry
- **AND** the structured entry returned no rows
- **WHEN** plan execution completes
- **THEN** no additional semantic invocation SHALL be made

#### Scenario: Recovery is not attempted when structured retrieval failed rather than emptied

- **GIVEN** a plan whose only structured entry reported status `failed`
- **WHEN** plan execution completes
- **THEN** the failure SHALL be reported in the retrieval status
- **AND** whether recovery runs SHALL follow the same rule as for `empty`, and the resulting status SHALL record both the original failure and the recovery outcome separately

#### Scenario: Recovery is skipped when the remaining budget is insufficient

- **GIVEN** a structured-only plan that returned no rows
- **AND** less than the configured minimum remaining budget before the retrieval deadline
- **WHEN** recovery would otherwise be attempted
- **THEN** the recovery SHALL be skipped
- **AND** the turn's retrieval status SHALL record the skip and its reason
- **AND** the skip SHALL NOT be represented as an empty result

#### Scenario: Recovery is at most one invocation

- **GIVEN** a structured-only plan that returned no rows
- **AND** the recovery semantic invocation also returns no chunks
- **WHEN** plan execution completes
- **THEN** no further retrieval invocation SHALL be made for that turn

### Requirement: Consistent cross-invocation score semantics

Chunks accumulated from more than one `semantic_retrieval` invocation SHALL be ordered on a comparable scale. When invocations differ in whether reranking succeeded, their scores SHALL be normalised to a common basis before merging and ordering. The score surfaced on a citation SHALL carry documented, consistent semantics.

#### Scenario: Reranked and fallback results merge on a comparable basis

- **GIVEN** two `semantic_retrieval` invocations in one plan
- **AND** the first returns reranker scores while the second falls back to fusion scores
- **WHEN** their chunks are accumulated and ordered
- **THEN** the ordering SHALL be computed on a single normalised scale
- **AND** a chunk SHALL NOT outrank another solely because its invocation used a different scoring basis

#### Scenario: Single-invocation ordering is unchanged

- **GIVEN** a plan with exactly one `semantic_retrieval` invocation
- **WHEN** its chunks are accumulated and ordered
- **THEN** the relative ordering SHALL be identical to the ordering the retriever returned

### Requirement: Conjunctive and multi-source planning contract

The orchestration capability contract SHALL require that a question whose conditions compose with AND be expressed as a single `structured_retrieval` invocation carrying every condition, rather than as separate invocations whose intersection no downstream stage computes. The contract SHALL further require a `semantic_retrieval` invocation alongside `structured_retrieval` for questions that enumerate values or identify subjects.

#### Scenario: Conjunctive question yields one composed structured invocation

- **GIVEN** the question "Find backend engineers with AWS and Kubernetes experience"
- **WHEN** the planner produces a plan
- **THEN** the plan SHALL NOT contain two independent `structured_retrieval` entries each carrying one condition
- **AND** the conditions SHALL be carried by a single structured invocation

#### Scenario: Enumeration question is planned with both capabilities

- **GIVEN** a question that asks which documents or subjects mention a named value
- **WHEN** the planner produces a plan
- **THEN** the plan SHALL contain a `structured_retrieval` entry
- **AND** the plan SHALL contain a `semantic_retrieval` entry

#### Scenario: Plan shape is observable for evaluation

- **GIVEN** any planned turn
- **WHEN** the turn's trace is inspected
- **THEN** the capability name and argument keys of every entry SHALL be recorded
- **AND** entries discarded by the invocation cap SHALL be recorded with their discard reason

### Requirement: Structural document-scope enforcement for structured retrieval

When a resolved document scope applies to a turn, that scope SHALL constrain structured retrieval structurally rather than as free text appended to the natural-language query. The scope SHALL be applied such that the row limit cannot truncate away the in-scope rows before the scope is honoured.

#### Scenario: Scope is applied as a constraint, not a suggestion

- **GIVEN** a turn resolved to a set of document identifiers
- **WHEN** structured retrieval executes
- **THEN** the executed statement SHALL constrain `document_id` to that set
- **AND** the constraint SHALL NOT depend on the generating model having honoured an instruction in prose

#### Scenario: Out-of-scope rows cannot consume the row budget

- **GIVEN** a tenant whose unconstrained query would return the row limit's worth of rows before reaching an in-scope document
- **AND** a turn resolved to that in-scope document
- **WHEN** structured retrieval executes
- **THEN** the returned rows SHALL include the in-scope document's rows
- **AND** the result SHALL NOT be empty solely because out-of-scope rows filled the limit first
