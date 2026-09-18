## ADDED Requirements

### Requirement: External database retrieval tool

The system SHALL provide an `external_database` retrieval tool that answers a natural-language question against the authenticated tenant's connected Azure Database for PostgreSQL through contract-grounded SQL generation and drift-gated execution. Its `args_schema` SHALL declare only `query` (string, required) and SHALL NOT declare a connection, contract, tenant, or schema identifier. The tool SHALL resolve its connection, contract, and live database server-side from `ToolContext.tenant_id`, and SHALL return a `ToolResult` for success and every failure without raising. On failure the `ToolResult.error` SHALL be a finite reason class only.

#### Scenario: Tool arguments expose no scope identifiers

- **GIVEN** the `external_database` tool
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** the only key SHALL be `query`

#### Scenario: Successful query returns rows

- **GIVEN** a tenant with an executable external capability and a fixture database returning two rows
- **WHEN** `external_database.call({"query": "how many unclaimed users"}, context)` is invoked
- **THEN** the `ToolResult` SHALL have `error is None` and two row mappings in `results`

#### Scenario: Drift block is returned as a finite error

- **GIVEN** a tenant whose live metadata no longer matches the published fingerprint
- **WHEN** the tool is invoked
- **THEN** the `ToolResult.error` SHALL be `drift_mismatch`
- **AND** no exception SHALL propagate

### Requirement: Per-request tool availability

The system SHALL compose the planner's tool set per chat turn from authenticated server-side state. The platform tools SHALL always be offered. The `external_database` tool SHALL be offered only when `resolve_external_capability` reports the authenticated tenant executable. When offered, its description SHALL name the published contract's relations and relation descriptions, truncated to a bounded length, so the planner can choose it. A plan entry naming `external_database` on a turn where it was not offered SHALL be rejected without execution. The degraded fallback plan SHALL NOT include `external_database`.

#### Scenario: Tenant without a connection is never offered the tool

- **GIVEN** a tenant with no active `azure_postgresql` connection
- **WHEN** the planner's tool schemas for a turn are exported
- **THEN** `external_database` SHALL NOT be among them

#### Scenario: Tenant with a published contract is offered the tool

- **GIVEN** a tenant with an active `azure_postgresql` connection and a published contract naming `fisc_user_profile`
- **WHEN** the planner's tool schemas for a turn are exported
- **THEN** `external_database` SHALL be among them
- **AND** its description SHALL mention `fisc_user_profile`

#### Scenario: Unoffered tool call is rejected

- **GIVEN** a turn on which `external_database` was not offered
- **WHEN** the planner output names `external_database`
- **THEN** that plan entry SHALL be rejected and never executed

#### Scenario: Fallback plan excludes the external tool

- **GIVEN** a tenant offered `external_database` whose planning call raises
- **WHEN** the degraded fallback plan is built
- **THEN** it SHALL NOT contain an `external_database` entry
