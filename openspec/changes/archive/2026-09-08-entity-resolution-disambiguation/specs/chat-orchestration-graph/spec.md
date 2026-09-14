## MODIFIED Requirements

### Requirement: Fixed topology with no agentic behaviour

The graph SHALL be a fixed DAG. Conditional edges SHALL exist only for terminal short-circuit paths: the guardrail early exits (blocked question type, out-of-domain) and — when entity resolution is enabled — the clarification exit from the `entity_resolution` node. The graph SHALL NOT contain loops, tool-calling nodes, reflection nodes, or LLM-decided routing between retrieval stages.

The `entity_resolution` node SHALL sit between the planning node and retrieval execution. It SHALL either route to retrieval execution (having optionally rewritten the plan's arguments with a resolved document scope) or route directly to END with a clarification reply. Its routing decision SHALL be derived from a counted database result, not from a model's choice of next step. The node SHALL be registered only when the entity-resolution flag is on, so the flag-off compiled graph is identical to the pre-change topology.

#### Scenario: Blocked question short-circuits to END

- **GIVEN** a message matching the `content_generation` blocked pattern
- **WHEN** the graph runs
- **THEN** the guardrail node routes directly to END
- **AND** the reply equals the existing `content_generation` decline string
- **AND** no retrieval, SQL, NER, or LLM call is made

#### Scenario: Out-of-domain question short-circuits to END

- **GIVEN** a message the domain classifier rejects
- **WHEN** the graph runs
- **THEN** the graph routes directly to END with the existing out-of-domain decline
- **AND** no retrieval or generation call is made

#### Scenario: Clarification short-circuits to END

- **GIVEN** entity resolution is enabled and the resolver returns an ambiguous outcome
- **WHEN** the graph runs
- **THEN** the `entity_resolution` node routes directly to END
- **AND** the reply is the deterministically assembled clarification text
- **AND** no retrieval execution or generation call is made

#### Scenario: Unique and unresolved outcomes continue to retrieval

- **GIVEN** entity resolution is enabled and the resolver returns `unique` or `unresolved`
- **WHEN** the graph runs
- **THEN** the `entity_resolution` node routes to retrieval execution
- **AND** the remaining node sequence is unchanged

#### Scenario: Routing is not model-decided

- **GIVEN** any resolver outcome
- **WHEN** the routing function runs
- **THEN** its decision SHALL be a function of the counted candidate documents in state
- **AND** no LLM output SHALL select the next node

#### Scenario: Compiled graph remains acyclic with the flag on

- **GIVEN** entity resolution is enabled
- **WHEN** the graph is compiled and inspected
- **THEN** it SHALL report no cycle

#### Scenario: Flag-off topology is unchanged

- **GIVEN** entity resolution is disabled
- **WHEN** the graph is compiled
- **THEN** the node and edge set SHALL equal the pre-change topology
- **AND** `entity_resolution` SHALL NOT be registered

## ADDED Requirements

### Requirement: Resolution outcome carried in graph state

`ChatState` SHALL carry the entity-resolution outcome additively: the conversation id, the resolution outcome, the resolved document ids, the pending candidate list, and the original message replayed after a selection. Existing state keys SHALL keep their present meaning, and downstream nodes SHALL consume the resolved scope through the existing plan arguments rather than through new node-to-node coupling.

#### Scenario: Outcome is visible in state before retrieval

- **GIVEN** a resolved turn
- **WHEN** the `entity_resolution` node completes
- **THEN** state SHALL carry the outcome and the resolved document ids

#### Scenario: Downstream nodes are unchanged

- **GIVEN** a resolved turn
- **WHEN** source assembly, prompt assembly, and generation run
- **THEN** they SHALL read the same state keys they read before this change

#### Scenario: Unresolved turn adds no scope

- **GIVEN** an `unresolved` outcome
- **WHEN** the plan is executed
- **THEN** no plan entry SHALL carry a document scope added by the resolver
