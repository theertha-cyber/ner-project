# telemetry-tenant-safety Specification

## Purpose
TBD - created by archiving change observability-workload-instrumentation. Update Purpose after archive.
## Requirements
### Requirement: Cross-Tenant Access Attempts Are Counted

Every rejection caused by a mismatch between the tenant asserted in a validated token and the tenant addressed by the request SHALL increment a dedicated counter. The counter SHALL be distinct from general authorization failures, because a non-zero value indicates an attempted cross-tenant access rather than an ordinary permission denial. Neither tenant identifier involved SHALL appear as a metric label on this counter.

#### Scenario: A tenant mismatch increments the counter

- **GIVEN** a request bearing a valid token for one tenant that addresses a different tenant's resource
- **WHEN** the request is rejected
- **THEN** a tenant-mismatch counter SHALL have incremented
- **AND** the rejection SHALL also produce a log record at WARNING or higher carrying the request's correlation context

#### Scenario: A tenant mismatch is distinguishable from an ordinary auth failure

- **GIVEN** one request rejected for a missing or invalid token and another rejected for a tenant mismatch
- **WHEN** the counters are read
- **THEN** the two SHALL have incremented different counters

#### Scenario: The mismatch counter carries no tenant label

- **GIVEN** the tenant-mismatch counter as exposed on `/metrics`
- **WHEN** its label set is examined
- **THEN** it SHALL NOT include a tenant identifier

### Requirement: Tenant Schema Is Asserted Before Query Execution

Before a query is executed against a tenant schema, the schema name SHALL be asserted to match the expected tenant-schema pattern. A name that does not match SHALL increment a violation counter and produce a log record at ERROR identifying the code path, in addition to whatever the calling code does with the failure.

#### Scenario: A well-formed tenant schema passes the assertion

- **GIVEN** a query executed against a schema named for a valid tenant identifier
- **WHEN** the assertion runs
- **THEN** it SHALL pass
- **AND** the violation counter SHALL NOT increment

#### Scenario: A malformed schema name is counted and logged

- **GIVEN** a code path that would set a search path to a value not matching the tenant-schema pattern
- **WHEN** the assertion runs
- **THEN** the violation counter SHALL increment
- **AND** an ERROR record SHALL be emitted identifying the code path
- **AND** the schema name SHALL be recorded in a form that does not echo arbitrary caller input verbatim

### Requirement: Authorization Failures And Rate-Limit Rejections Are Counted

Authentication and authorization failures SHALL be counted by an enumerated reason. Rate-limit rejections SHALL be counted and MAY carry a tenant label, subject to the cardinality allowlist.

#### Scenario: Auth failures are counted by reason

- **GIVEN** requests rejected for a missing header, a malformed token and an expired token
- **WHEN** the auth-failure counter is read
- **THEN** each SHALL have incremented under a distinct enumerated reason
- **AND** no token value or fragment SHALL appear in any label

#### Scenario: Rate-limit rejections are counted

- **GIVEN** a caller that exceeds its configured rate limit
- **WHEN** the rate-limit counter is read
- **THEN** it SHALL have incremented

### Requirement: Metric Label Cardinality Allowlist

The set of metric families permitted to carry a `tenant_id` label SHALL be defined as a single enumerated list in one place. Any metric family not on that list SHALL NOT carry a tenant label. The constraint SHALL be enforced by an automated test rather than by review, so that adding a tenant label to a new metric fails the build unless the list is amended deliberately.

#### Scenario: An allowlisted family may carry the tenant label

- **GIVEN** a metric family named on the allowlist
- **WHEN** its label set is examined
- **THEN** it MAY include `tenant_id`

#### Scenario: A non-allowlisted family carrying a tenant label fails the check

- **GIVEN** a metric family not named on the allowlist that has been given a `tenant_id` label
- **WHEN** the allowlist enforcement check runs
- **THEN** it SHALL fail and identify the offending family

#### Scenario: The allowlist is small and explicit

- **GIVEN** the allowlist definition
- **WHEN** it is read
- **THEN** it SHALL enumerate its members explicitly
- **AND** it SHALL NOT be expressed as a pattern, prefix or wildcard that admits families not written down

### Requirement: Automated Release-Gate Telemetry Scan

The release pipeline SHALL run an automated check that exercises a seeded end-to-end flow against a running stack and inspects the telemetry it produced — log records, span attributes and metric labels — for sensitive content. The check SHALL fail the build when it finds seeded entity values or content matching personal-data patterns. Passing SHALL require the check to have actually run and produced telemetry, so that an empty capture cannot be mistaken for a clean result.

#### Scenario: A clean run passes the scan

- **GIVEN** a seeded end-to-end flow executed against the running stack
- **WHEN** the scan inspects the captured telemetry
- **THEN** it SHALL find no seeded entity value and no personal-data pattern match
- **AND** it SHALL exit successfully

#### Scenario: A deliberately reintroduced leak fails the scan

- **GIVEN** a code path modified to log a seeded entity value
- **WHEN** the scan runs
- **THEN** it SHALL fail
- **AND** it SHALL identify the offending record or attribute

#### Scenario: An empty capture is treated as a failure, not a pass

- **GIVEN** the seeded flow produced no telemetry, for example because export was misconfigured
- **WHEN** the scan runs
- **THEN** it SHALL fail rather than report a clean result

#### Scenario: The scan covers spans and metric labels, not only logs

- **GIVEN** a seeded entity value present in a span attribute or a metric label but in no log record
- **WHEN** the scan runs
- **THEN** it SHALL fail

