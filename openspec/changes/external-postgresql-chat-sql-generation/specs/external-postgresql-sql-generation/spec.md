## ADDED Requirements

### Requirement: Contract-grounded SQL generation

The system SHALL generate external SQL from the authenticated tenant's published contract only. The generation prompt SHALL consist of fixed, code-owned rules plus schema context built from the published contract version's schema-index entries (relation names, column names, relation and column descriptions, and approved join keys). No schema text SHALL be hardcoded for an external tenant. The LLM SHALL return one JSON object `{"sql": <string>, "params": <object>}`, where every filter value is a named `%(name)s` placeholder in `sql` and its value is carried in `params`. The generator SHALL NOT receive a database credential, connection, or connection configuration.

#### Scenario: Prompt is built from the published contract version

- **GIVEN** tenant A with a published contract version 2 whose index entries describe `fisc_user_profile`
- **WHEN** the generator builds a prompt for a question from tenant A
- **THEN** the prompt SHALL contain the version-2 index entry text for `fisc_user_profile`
- **AND** the prompt SHALL NOT contain entries from any other version, connection, or tenant

#### Scenario: Generated statement uses placeholders for values

- **GIVEN** a published contract authorizing `fisc_user_profile.claim_ind`
- **WHEN** the LLM returns `{"sql": "SELECT COUNT(*) FROM fisc_user_profile WHERE claim_ind = %(p1)s", "params": {"p1": "0"}}`
- **THEN** the generator SHALL accept the statement for execution
- **AND** the value `"0"` SHALL be passed only as a bound parameter

#### Scenario: Malformed LLM output is not executed

- **GIVEN** an LLM response that is not a JSON object with a string `sql` and an object `params`
- **WHEN** the generator parses it
- **THEN** no statement SHALL reach the tenant database
- **AND** the attempt SHALL be recorded with the finite reason `malformed_output`

#### Scenario: Missing parameter value is not executed

- **GIVEN** a generated `sql` containing `%(p2)s` with no `p2` key in `params`
- **WHEN** the generator checks the output
- **THEN** no statement SHALL reach the tenant database
- **AND** the attempt SHALL be recorded with the finite reason `missing_param`

### Requirement: Local validation with bounded reason-guided retry

The system SHALL validate each generated statement against the published canonical contract with the existing external AST validator before any tenant-database access. On rejection it SHALL retry generation at most two more times (three attempts in total), providing the LLM only the finite rejection reason class and the offending contract identifier from the previous attempt. It SHALL NOT provide row values or live metadata. Only a locally accepted statement SHALL be passed to drift-gated execution. Retries SHALL NOT perform drift checks or tenant-database calls.

#### Scenario: Rejected statement is retried with reason feedback

- **GIVEN** a first attempt rejected with reason `unapproved_column` and reference `ssn`
- **WHEN** the generator makes the second attempt
- **THEN** the second prompt SHALL include the reason `unapproved_column` and the identifier `ssn`
- **AND** the tenant database SHALL NOT have been contacted for the first attempt

#### Scenario: Attempts are bounded

- **GIVEN** an LLM whose every output is rejected by the validator
- **WHEN** the generator runs for one question
- **THEN** exactly three generation attempts SHALL be made
- **AND** the outcome SHALL be the finite reason `generation_exhausted`
- **AND** no statement SHALL reach the tenant database

#### Scenario: Accepted statement executes once through the drift gate

- **GIVEN** a statement accepted by local validation on the second attempt
- **WHEN** the generator hands it to execution
- **THEN** `execute_external_query` SHALL be called exactly once
- **AND** the drift check SHALL run before that execution

### Requirement: Bounded schema context without retrieval

The system SHALL include every index entry of the published contract version in the prompt while the rendered schema context fits a configured character budget. When the rendered context exceeds the budget, generation SHALL fail with the finite reason `schema_context_too_large` without truncating entries or calling the LLM. Embedding-based relation retrieval is out of scope.

#### Scenario: Oversized contract fails closed

- **GIVEN** a published contract whose rendered schema context exceeds the configured budget
- **WHEN** a question is asked
- **THEN** no LLM generation call SHALL be made
- **AND** the outcome SHALL be the finite reason `schema_context_too_large`

### Requirement: Generation telemetry is content-free

The system SHALL record, per generation attempt, only the attempt number, a finite outcome/reason class, and latency. It SHALL NOT log or trace the question, prompt, generated SQL text, parameter values, or result rows.

#### Scenario: Rejected attempt logs no SQL

- **GIVEN** a generated statement rejected by the validator
- **WHEN** logs and metrics for that attempt are inspected
- **THEN** they SHALL contain the reason class and attempt number
- **AND** they SHALL NOT contain the SQL text or any parameter value
