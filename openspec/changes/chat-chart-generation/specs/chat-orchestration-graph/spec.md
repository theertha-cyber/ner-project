## MODIFIED Requirements

### Requirement: Fixed topology with no agentic behaviour

The graph SHALL be a fixed DAG. Conditional edges SHALL exist only for the two early-exit paths that already exist in `RAGOrchestrator.execute` — blocked question type and complexity above threshold. The graph SHALL NOT contain loops, planner nodes, reflection nodes, or LLM-decided routing.

A node MAY offer the model a bounded tool whose result is consumed inside that same node, provided the tool performs no retrieval and no side effect, cannot be called more than once per turn, and cannot influence which node runs next. Such a tool call SHALL NOT introduce an edge, a loop, or a re-entry into any node. The generation node's `render_chart` tool is the only such tool, and its sole effect is to produce a chart payload carried in state.

The graph SHALL NOT contain a node whose next hop is chosen by the model, and SHALL NOT re-enter a node in response to a tool result.

#### Scenario: Blocked question short-circuits to END

- **GIVEN** a message matching the `content_generation` blocked pattern
- **WHEN** the graph runs
- **THEN** the guardrail node routes directly to END
- **AND** the reply equals the existing `content_generation` decline string
- **AND** no retrieval, SQL, NER, or LLM call is made

#### Scenario: Excess complexity short-circuits to END

- **GIVEN** a message whose `GuardrailService.assess_complexity` score exceeds 3
- **WHEN** the graph runs
- **THEN** the graph routes directly to END with the existing "requires multiple lookups" reply
- **AND** no retrieval, SQL, NER, or LLM call is made

#### Scenario: Chart tool call does not alter graph routing

- **GIVEN** a chart-eligible turn in which the model calls `render_chart`
- **WHEN** the graph runs
- **THEN** the sequence of nodes executed SHALL be identical to the sequence executed for the same turn without a chart
- **AND** the generation node SHALL NOT be re-entered
- **AND** no edge SHALL be traversed as a consequence of the tool call

## ADDED Requirements

### Requirement: Two-stage generation for chart-eligible turns

The generation node SHALL run in two stages for chart-eligible turns, as defined by the `chat-chart-generation` capability. The first stage SHALL be a non-streaming model call that offers the `render_chart` tool and whose purpose is to determine whether a chart is warranted and, if so, to obtain its payload. The second stage SHALL produce the natural-language reply using the existing streaming or non-streaming call, with the first stage's tool call and its result appended to the messages so that the reply is written in the knowledge that a chart accompanies it.

When the first stage returns no tool call, the node SHALL proceed to produce the reply exactly as the single-stage path does today, with no change to the messages sent, the sampling parameters, or the streaming behaviour.

The streaming contract SHALL be preserved: no content token SHALL be emitted during the first stage, and token emission SHALL remain gated on the turn having non-empty sources.

#### Scenario: Model declines to chart and the reply path is unchanged

- **GIVEN** a chart-eligible turn
- **WHEN** the first-stage call returns no tool call
- **THEN** the reply SHALL be produced by the existing generation call
- **AND** the reply SHALL be identical to the one the single-stage path produces for the same inputs
- **AND** no chart SHALL be carried in state

#### Scenario: Model charts and the narrative reply is written alongside it

- **GIVEN** a chart-eligible turn
- **WHEN** the first-stage call returns a `render_chart` tool call that passes validation
- **THEN** the second-stage call's messages SHALL include the tool call and its result
- **AND** the reply SHALL be streamed by the second-stage call as it is today
- **AND** state SHALL carry the resulting chart payload

#### Scenario: No tokens are emitted during the decision stage

- **GIVEN** a chart-eligible streaming turn
- **WHEN** the first-stage call runs
- **THEN** no `token` event SHALL be emitted for the duration of that call
- **AND** the first `token` event SHALL correspond to content produced by the second-stage call

#### Scenario: Failure of the decision stage degrades to a text answer

- **GIVEN** a chart-eligible turn
- **WHEN** the first-stage call raises an error or returns a malformed tool call
- **THEN** the node SHALL fall back to the single-stage generation path
- **AND** the turn SHALL produce its ordinary text answer
- **AND** the failure SHALL be logged

### Requirement: Chart payload carried in graph state

Graph state SHALL carry an optional chart value, absent by default and set only by the generation node when a proposed chart has passed both structural and grounding validation. The value SHALL be the terminal chart for the turn, in the same way `reply` is the terminal answer, and SHALL be cleared when citation enforcement replaces the reply.

#### Scenario: State carries no chart for an ordinary turn

- **GIVEN** a turn for which no chart was proposed
- **WHEN** the graph completes
- **THEN** the chart value in state SHALL be absent

#### Scenario: State carries the validated chart

- **GIVEN** a turn whose proposed chart passed validation and whose reply was not replaced
- **WHEN** the graph completes
- **THEN** the chart value in state SHALL be the validated payload
