# sql-query-recovery

## ADDED Requirements

### Requirement: Wrong-entity-type defect detection

A zero-row result SHALL be classified as a retryable defect when a literal the statement compares against `normalized_value` exists in the tenant's data under an `entity_type` other than the one the statement filtered on. This is a distinct defect class from a filter on an `entity_type` that does not exist for the tenant. Detection SHALL be deterministic and SHALL be performed only after a statement has executed and returned zero rows.

#### Scenario: Value exists under a different entity type

- **GIVEN** a tenant whose data holds `aws` only under `entity_type` `TOOL_FRAMEWORK`
- **AND** a validated statement filtering `entity_type = 'PROGRAMMING_LANGUAGE' AND normalized_value = 'aws'`
- **WHEN** the statement executes and returns zero rows
- **THEN** the attempt SHALL be classified as a retryable defect
- **AND** the defect SHALL identify both the literal and the entity type under which it actually occurs

#### Scenario: Defect feedback names the correct entity type

- **GIVEN** an attempt classified with a wrong-entity-type defect for literal `aws`
- **WHEN** the retry prompt is rendered
- **THEN** the feedback SHALL state that the literal occurs under the other entity type
- **AND** the feedback SHALL include the failing statement

#### Scenario: Retry budget is spent on the defect

- **GIVEN** a first attempt classified with a wrong-entity-type defect
- **AND** remaining attempts and remaining deadline budget
- **WHEN** the recovery loop continues
- **THEN** a second attempt SHALL be generated with the defect feedback
- **AND** the loop SHALL NOT terminate as a success on the zero-row first attempt

#### Scenario: Genuinely absent value is not a defect

- **GIVEN** a literal that occurs under no `entity_type` in the tenant's data
- **AND** a validated statement filtering on that literal returning zero rows
- **WHEN** the attempt is classified
- **THEN** the attempt SHALL be classified as a success with zero rows
- **AND** no retry SHALL be triggered by row count alone

#### Scenario: Detection does not fire when the tenant profile is unavailable

- **GIVEN** the tenant's entity profile could not be fetched
- **AND** a validated statement returning zero rows
- **WHEN** the attempt is classified
- **THEN** the attempt SHALL be classified as a success with zero rows
- **AND** an unavailable profile SHALL NOT be interpreted as evidence of absence

### Requirement: Structured retrieval reports result completeness

Structured retrieval SHALL report, alongside its rows, whether the result was truncated by the row limit, and the total number of rows the query matched. Downstream stages SHALL be able to determine whether the returned rows are the complete answer.

#### Scenario: Truncated result is reported as incomplete

- **GIVEN** a tenant whose query matches 142 rows
- **AND** a statement carrying the default row limit of 100
- **WHEN** the statement executes
- **THEN** the result SHALL report 100 rows returned and 142 matched
- **AND** the result SHALL be marked truncated

#### Scenario: Complete result is reported as complete

- **GIVEN** a query matching 12 rows under a limit of 100
- **WHEN** the statement executes
- **THEN** the result SHALL report 12 returned and 12 matched
- **AND** the result SHALL NOT be marked truncated

#### Scenario: Completeness reporting does not change returned rows

- **GIVEN** any executed statement
- **WHEN** completeness is determined
- **THEN** the rows handed to the caller SHALL be identical to those the statement returned
- **AND** the row limit SHALL be unchanged by this requirement

### Requirement: Failed recovery is reported, never laundered into an empty result

When every attempt in the recovery loop has failed, the failure SHALL propagate as a failure with its per-attempt trace intact. It SHALL NOT be converted into an empty row list at any boundary between the recovery loop and prompt assembly.

#### Scenario: Exhausted attempts propagate as failure

- **GIVEN** a recovery loop whose every attempt failed
- **WHEN** the loop terminates
- **THEN** the caller SHALL observe a failure carrying the attempts
- **AND** the caller SHALL NOT observe an empty successful result

#### Scenario: Deadline-abandoned recovery is distinguishable from exhausted attempts

- **GIVEN** a first attempt that failed
- **AND** a remaining deadline already exhausted before the second attempt
- **WHEN** the loop terminates
- **THEN** the reported failure SHALL identify deadline exhaustion as the reason
- **AND** the per-attempt trace SHALL record the attempts actually made

#### Scenario: Per-attempt trace reaches the turn's status

- **GIVEN** a structured invocation that failed after multiple attempts
- **WHEN** the turn's retrieval status is produced
- **THEN** the status SHALL carry the per-attempt outcomes for that invocation
