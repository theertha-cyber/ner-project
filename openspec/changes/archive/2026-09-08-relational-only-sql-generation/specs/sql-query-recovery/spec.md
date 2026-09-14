## RENAMED Requirements

- FROM: `### Requirement: Bounded tenant entity profile in the generation context`
- TO: `### Requirement: Bounded relational surface and value samples in the generation context`

## MODIFIED Requirements

### Requirement: Attempt outcome classification

Every attempt SHALL be classified into exactly one outcome drawn from a closed set: `success`, `generation_error`, `validation_error`, `execution_error`, or `empty_with_defect`. A failure SHALL NOT be represented as a successful empty result. The loop SHALL retry only on the failure outcomes. Classification SHALL be decidable without reference to `entity_type` comparisons in the generated SQL: the defect signals operate over the tenant's resolved relational surface, its own data, and the requested document scope.

#### Scenario: Validation failure is classified and retried

- **GIVEN** the first generated query references a relation outside the resolved surface and the static whitelist
- **WHEN** the validation layer rejects it
- **THEN** the attempt SHALL be classified `validation_error`
- **AND** the query SHALL NOT be executed
- **AND** a second attempt SHALL be made

#### Scenario: A column no relation declares is classified as a validation failure

- **GIVEN** the first generated query selects a column that no relation on the surface declares
- **WHEN** the validation layer rejects it
- **THEN** the attempt SHALL be classified `validation_error`
- **AND** a second attempt SHALL be made

#### Scenario: Execution failure is classified and retried

- **GIVEN** the first generated query passes validation but the database raises an error, such as an invalid join predicate
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `execution_error`
- **AND** a second attempt SHALL be made
- **AND** a second attempt that succeeds SHALL return its rows to the caller

#### Scenario: Generation failure is classified and retried

- **GIVEN** the SQL-generation LLM call raises, or returns text that is not a usable query
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `generation_error`
- **AND** a second attempt SHALL be made

### Requirement: Zero rows is a legitimate result unless a deterministic defect explains it

A zero-row result SHALL be returned as a successful, genuinely empty answer unless a deterministic defect in the executed SQL proves it could not have matched. The system SHALL NOT retry on row count alone. The defect signals in force are:

- a filter on a value that does occur in the tenant's data but is projected into a relation or column the statement did not query;
- a filter requiring a `filename` that no document in the tenant carries;
- a supplied document scope that could not be applied to any relation the statement references.

Additional defect signals MAY be added only where they are decidable from the SQL and the tenant's own metadata, never inferred from the question. A defect SHALL NOT be inferred from the absence of an `entity_type` filter, and no defect SHALL be reported in terms of `entity_type`.

#### Scenario: Unexplained empty result is not retried

- **GIVEN** a generated query that validates, executes without error, returns zero rows, and references only relations and columns on the tenant's resolved surface
- **AND** no defect signal fires
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success`
- **AND** no second SQL-generation LLM call SHALL be made
- **AND** an empty result SHALL be returned to the caller without error

#### Scenario: Empty result caused by a value held in another relation is retried

- **GIVEN** the first generated query filters `e_skill.normalized_value = 'oracle'` and returns zero rows
- **AND** the value `oracle` occurs in the tenant's data under a definition projected as `e_employer`
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `empty_with_defect`
- **AND** a second attempt SHALL be made
- **AND** the second attempt's rows SHALL be returned when it succeeds

#### Scenario: A value that occurs nowhere in the tenant's data is not a defect

- **GIVEN** the first generated query filters on a value that occurs under no relation and no column
- **AND** the query returns zero rows
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success`
- **AND** the empty result SHALL be returned as a genuine answer

#### Scenario: An unscopeable document-scoped statement is a defect

- **GIVEN** a document scope was supplied
- **AND** the generated statement references no relation the scope can be applied to
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `empty_with_defect`
- **AND** a second attempt SHALL be made

#### Scenario: Non-empty result is never retried

- **GIVEN** a generated query that returns at least one row
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success` regardless of any other signal
- **AND** no further SQL-generation LLM call SHALL be made

### Requirement: Previous-attempt feedback is supplied to the generator

Every retry SHALL supply the SQL generator with a bounded record of the preceding attempts, containing the previously generated SQL, the attempt outcome, a sanitized single-line reason, and a corrective instruction directing reconsideration of the relations, columns, values, operators, joins, and filters chosen. Error text SHALL be sanitized before it reaches the prompt or the logs: the driver's echo of the executed statement and its bound parameters SHALL be stripped, and the remaining text SHALL be truncated to a fixed budget. Feedback SHALL NOT be exposed to end users.

Defect feedback SHALL be expressed in terms of the relational surface. Where a value is held elsewhere, the feedback SHALL name the relation or column that holds it. Feedback SHALL NOT instruct the model to re-issue a query against a different `entity_type`, and SHALL NOT instruct it to join the EAV entity store.

#### Scenario: Retry prompt contains the previous SQL and its failure reason

- **GIVEN** the first attempt failed with a database error
- **WHEN** the second attempt's generation prompt is constructed
- **THEN** the prompt SHALL contain the first attempt's SQL
- **AND** the prompt SHALL contain a sanitized description of the failure
- **AND** the prompt SHALL instruct the model to reconsider its assumptions

#### Scenario: Bound parameters are stripped from error feedback

- **GIVEN** a database error whose message appends the executed statement and its bound parameters
- **WHEN** the error is rendered into retry feedback
- **THEN** the appended statement and parameter echo SHALL be removed
- **AND** the retained text SHALL be truncated to the configured budget

#### Scenario: Empty-result feedback names the relation that holds the value

- **GIVEN** the first attempt returned zero rows because it filtered a value in a relation that does not hold it
- **WHEN** the second attempt's generation prompt is constructed
- **THEN** the prompt SHALL state that the previous attempt returned zero rows
- **AND** the prompt SHALL name the relation or column that does hold the value
- **AND** the prompt SHALL NOT reference `entity_type`

#### Scenario: Validation feedback restates the available surface

- **GIVEN** the first attempt was rejected for naming a relation or column that does not exist
- **WHEN** the second attempt's generation prompt is constructed
- **THEN** the prompt SHALL contain the rejection reason
- **AND** the prompt SHALL list the relations and columns available to this tenant

### Requirement: Bounded relational surface and value samples in the generation context

The SQL generator SHALL receive the querying tenant's resolved relational surface — every relation it may read, the columns each declares with their SQL types, and the semantic metadata of the entity definition behind each relation and each `subject` entity column — together with a bounded sample of representative values drawn from that tenant's own data.

Value samples SHALL be keyed by the relation or column the values are projected into, not by the storage-level entity type, so a base-model tenant's CoNLL labels and a fine-tuned tenant's own names both resolve to the relation the generator can query. The sample SHALL be capped per relation or column, capped in total, and truncated per value. The surface and the samples SHALL be fetched once per invocation and reused across attempts. The surface SHALL remain complete: a relation or column SHALL still be listed when it contributes no sample values. No part of the user's question SHALL influence which tenant or schema is queried, nor which rows the samples are drawn from.

#### Scenario: The relational surface appears in the generation context

- **GIVEN** a tenant with an active `multi` definition `Skill` and an active `single` definition `Email`
- **WHEN** the SQL-generation prompt is constructed
- **THEN** the prompt SHALL list `e_skill` with its columns
- **AND** the prompt SHALL list `subject` with its `email` column and that column's SQL type

#### Scenario: Sample values appear under their relation

- **GIVEN** a tenant whose skill entities include values such as `python` and `kubernetes`
- **WHEN** the SQL-generation prompt is constructed
- **THEN** the prompt SHALL list those values under `e_skill`

#### Scenario: Sample size is bounded per relation and in total

- **GIVEN** a tenant with many relations and many distinct values in each
- **WHEN** the samples are fetched
- **THEN** no relation or column SHALL contribute more than the configured per-key sample size
- **AND** the total number of sampled values SHALL NOT exceed the configured overall cap

#### Scenario: Relations with no sampled values are still listed

- **GIVEN** a relation whose rows carry no usable sample values
- **WHEN** the SQL-generation prompt is constructed
- **THEN** that relation SHALL still appear in the listed surface

#### Scenario: Surface and samples are fetched once per invocation

- **GIVEN** an invocation that requires three attempts
- **WHEN** the loop completes
- **THEN** the surface-resolution and sample queries SHALL have been executed once, not once per attempt

#### Scenario: One tenant's surface never appears in another tenant's context

- **GIVEN** two tenants with different catalogs
- **WHEN** a question is asked in each
- **THEN** each prompt SHALL contain only the relations of the tenant whose schema was bound from request context
