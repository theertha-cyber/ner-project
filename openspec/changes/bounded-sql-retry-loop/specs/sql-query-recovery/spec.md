## ADDED Requirements

### Requirement: Bounded SQL attempt loop

Natural-language-to-SQL retrieval SHALL be executed as a bounded attempt loop of generate → validate → execute → inspect. The loop SHALL make at most `settings.sql_max_attempts` attempts (default 3, clamped to a minimum of 1) per structured-retrieval invocation. The loop SHALL return immediately on the first successful attempt and SHALL NOT issue any further SQL-generation LLM call after a success. The attempt cap SHALL be read from configuration in exactly one place; the numeric limit SHALL NOT be duplicated as a literal elsewhere in the implementation.

#### Scenario: Successful first attempt makes exactly one generation call

- **GIVEN** a natural-language question and a configured attempt cap of 3
- **WHEN** the first generated query validates, executes, and returns at least one row
- **THEN** the rows SHALL be returned to the caller
- **AND** exactly one SQL-generation LLM call SHALL have been made
- **AND** exactly one SQL execution SHALL have been performed

#### Scenario: Loop stops at the configured attempt cap

- **GIVEN** a configured attempt cap of 3 and a generator whose every attempt fails
- **WHEN** the third attempt fails
- **THEN** the loop SHALL terminate
- **AND** no fourth SQL-generation LLM call SHALL be made
- **AND** no fourth SQL execution SHALL be attempted

#### Scenario: Attempt cap of 1 reproduces single-pass behaviour

- **GIVEN** `sql_max_attempts` is configured as 1
- **WHEN** the first attempt fails with a validation error
- **THEN** no second SQL-generation LLM call SHALL be made
- **AND** the invocation SHALL report failure to its caller

#### Scenario: Loop stops early when the retrieval deadline has passed

- **GIVEN** an attempt has failed and the tool context's deadline has already elapsed
- **WHEN** the loop considers a further attempt
- **THEN** no further SQL-generation LLM call SHALL be made
- **AND** the invocation SHALL report failure to its caller

### Requirement: Attempt outcome classification

Every attempt SHALL be classified into exactly one outcome drawn from a closed set: `success`, `generation_error`, `validation_error`, `execution_error`, or `empty_with_defect`. A failure SHALL NOT be represented as a successful empty result. The loop SHALL retry only on the failure outcomes.

#### Scenario: Validation failure is classified and retried

- **GIVEN** the first generated query references a table outside the whitelist
- **WHEN** the validation layer rejects it
- **THEN** the attempt SHALL be classified `validation_error`
- **AND** the query SHALL NOT be executed
- **AND** a second attempt SHALL be made

#### Scenario: Execution failure is classified and retried

- **GIVEN** the first generated query passes validation but the database raises an undefined-column error
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

A zero-row result SHALL be returned as a successful, genuinely empty answer unless a deterministic defect in the executed SQL proves it could not have matched. The system SHALL NOT retry on row count alone. The only defect signal in force is that the executed SQL compares `entity_type` against a string literal that is not among the tenant's actual entity types; such an attempt SHALL be classified `empty_with_defect` and retried. Additional defect signals MAY be added only where they are decidable from the SQL and the tenant's own metadata, never inferred from the question.

#### Scenario: Unexplained empty result is not retried

- **GIVEN** a generated query that validates, executes without error, returns zero rows, and references only entity types that exist for the tenant
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success`
- **AND** no second SQL-generation LLM call SHALL be made
- **AND** an empty result SHALL be returned to the caller without error

#### Scenario: Empty result caused by a nonexistent entity type is retried

- **GIVEN** the tenant's entity types are `PER`, `ORG`, and `SKILL`
- **AND** the first generated query filters on `entity_type = 'EMPLOYER'` and returns zero rows
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `empty_with_defect`
- **AND** a second attempt SHALL be made
- **AND** the second attempt's rows SHALL be returned when it succeeds

#### Scenario: Non-empty result is never retried

- **GIVEN** a generated query that returns at least one row
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success` regardless of any other signal
- **AND** no further SQL-generation LLM call SHALL be made

### Requirement: Previous-attempt feedback is supplied to the generator

Every retry SHALL supply the SQL generator with a bounded record of the preceding attempts, containing the previously generated SQL, the attempt outcome, a sanitized single-line reason, and a corrective instruction directing reconsideration of entity types, values, operators, joins, and filters. Error text SHALL be sanitized before it reaches the prompt or the logs: the driver's echo of the executed statement and its bound parameters SHALL be stripped, and the remaining text SHALL be truncated to a fixed budget. Feedback SHALL NOT be exposed to end users.

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

#### Scenario: Empty-result feedback states the row count and the defect

- **GIVEN** the first attempt returned zero rows because it filtered on an entity type the tenant does not have
- **WHEN** the second attempt's generation prompt is constructed
- **THEN** the prompt SHALL state that the previous attempt returned zero rows
- **AND** the prompt SHALL name the entity-type literal that does not exist for this tenant

### Requirement: Bounded tenant entity profile in the generation context

The SQL generator SHALL receive, in addition to the tenant's complete list of entity types, a bounded sample of representative values drawn from that tenant's own data. The sample SHALL be capped per entity type, capped in total across all types, and truncated per value. The profile SHALL be fetched once per invocation and reused across attempts. The complete type list SHALL remain complete: an entity type SHALL still be listed when it contributes no sample values. No part of the user's question SHALL influence which tenant or schema is queried, nor which rows the profile is drawn from.

#### Scenario: Sample values appear in the generation context

- **GIVEN** a tenant whose `SKILL` entities include values such as `python` and `kubernetes`
- **WHEN** the SQL-generation prompt is constructed
- **THEN** the prompt SHALL list `SKILL` with a bounded sample of its actual values

#### Scenario: Sample size is bounded per type and in total

- **GIVEN** a tenant with many entity types and many distinct values per type
- **WHEN** the entity profile is fetched
- **THEN** no entity type SHALL contribute more than the configured per-type sample size
- **AND** the total number of sampled values SHALL NOT exceed the configured overall cap

#### Scenario: Entity types with no sampled values are still listed

- **GIVEN** an entity type whose rows all have a NULL normalized value
- **WHEN** the SQL-generation prompt is constructed
- **THEN** that entity type SHALL still appear in the list of available entity types

#### Scenario: Profile is fetched once per invocation

- **GIVEN** an invocation that requires three attempts
- **WHEN** the loop completes
- **THEN** the entity-profile queries SHALL have been executed once, not once per attempt

### Requirement: Tenant isolation and validation hold across every attempt

Every attempt SHALL pass through the same validation layer and the same execution path as the first attempt. The schema SHALL be bound once from authenticated request context before the loop begins and SHALL NOT be re-derived from generated SQL, from feedback, or from the user's question at any point. No attempt SHALL be able to change the tenant or schema being queried.

#### Scenario: Every retried query is validated

- **GIVEN** an invocation in which attempts 1 and 2 fail and attempt 3 is generated
- **WHEN** attempt 3 is processed
- **THEN** attempt 3's SQL SHALL be passed through the validation layer before execution

#### Scenario: A retry cannot escape the table whitelist

- **GIVEN** a retry whose generated SQL references a table outside the whitelist
- **WHEN** the attempt is processed
- **THEN** validation SHALL reject it
- **AND** the query SHALL NOT be executed

#### Scenario: Retries execute against the schema from request context

- **GIVEN** an invocation for a schema supplied by authenticated request context
- **WHEN** three attempts are made
- **THEN** every attempt SHALL execute against that same schema
- **AND** no attempt SHALL execute against a schema named in generated SQL or in the user's question

#### Scenario: Retries remain read-only

- **GIVEN** any retry attempt
- **WHEN** it is executed
- **THEN** it SHALL execute in the same read-only transaction path with the same timeout as the first attempt

### Requirement: Exhausted retries report failure rather than an empty result

When every attempt fails, the invocation SHALL report a failure to its caller rather than returning an empty successful result. The failure SHALL surface at the retrieval tool boundary as a tool error, so that downstream state distinguishes a failed structured retrieval from one that legitimately found nothing. The system SHALL NOT fabricate an answer, and the user-facing outcome SHALL remain the existing controlled fallback response.

#### Scenario: Exhausted retries surface as a structured-retrieval error

- **GIVEN** an invocation whose every attempt fails
- **WHEN** the loop terminates
- **THEN** the structured-retrieval capability SHALL report an error result
- **AND** the turn's structured-retrieval error state SHALL be populated

#### Scenario: A legitimate empty result is not reported as an error

- **GIVEN** an invocation whose first attempt succeeds with zero rows
- **WHEN** the invocation completes
- **THEN** the structured-retrieval capability SHALL report a successful result with no rows
- **AND** no error SHALL be reported

#### Scenario: Exhausted retries do not produce a fabricated answer

- **GIVEN** a turn whose structured retrieval failed on every attempt and produced no other sources
- **WHEN** the answer is generated
- **THEN** the existing source-citation guardrail SHALL replace the reply with the controlled fallback response

### Requirement: Per-attempt observability

Each attempt SHALL emit a structured internal record carrying at minimum the attempt index, the configured cap, the generated SQL, the outcome, the returned row count where applicable, and the sanitized error where applicable. Records SHALL be written to logs and SHALL be appended to a caller-supplied trace sink so a completed turn can be diagnosed from its captured internal state. Raw SQL and attempt diagnostics SHALL NOT be added to any user-facing response payload.

#### Scenario: A recovered query is fully traceable

- **GIVEN** an invocation whose first attempt failed and whose second attempt succeeded
- **WHEN** the invocation completes
- **THEN** the trace SHALL contain two records
- **AND** the first record SHALL carry its attempt index, its SQL, and its failure outcome with a sanitized error
- **AND** the second record SHALL carry its attempt index, its SQL, its success outcome, and its row count

#### Scenario: Attempt diagnostics stay out of the chat response

- **GIVEN** a turn that required retries
- **WHEN** the chat response is returned to the caller
- **THEN** the response payload SHALL NOT contain generated SQL or attempt diagnostics
