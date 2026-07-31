## ADDED Requirements

### Requirement: Intent Orchestrator is the single retrieval routing layer

The system SHALL run an Intent Orchestrator node immediately after the guardrail and before any retrieval executes. The orchestrator SHALL receive the user query, the recent conversation history, the set of available retrieval capabilities exported from the shared `ToolRegistry`, and an orchestration prompt describing those capabilities, and SHALL emit a retrieval plan. No other component SHALL decide which retrieval capabilities run. Retrieval routing SHALL NOT be controlled by any runtime feature flag or configuration setting.

#### Scenario: Orchestrator decides retrieval for every non-declined turn

- **GIVEN** a query that passes the guardrail
- **WHEN** the chat turn runs
- **THEN** the orchestrator node SHALL execute exactly once before any retrieval capability is invoked
- **AND** the capabilities invoked SHALL be exactly those named in the emitted plan

#### Scenario: Orchestrator receives the declared capabilities and conversation history

- **GIVEN** a registry exporting `semantic_retrieval` and `structured_retrieval`, and a conversation with prior turns
- **WHEN** the orchestrator makes its planning call
- **THEN** the `tools` argument sent to the LLM client SHALL equal `ToolRegistry.export_schemas()`
- **AND** the messages SHALL include the orchestration prompt and the recent conversation turns
- **AND** the messages SHALL include the current user query

#### Scenario: No feature flag governs routing

- **GIVEN** the implemented configuration model
- **WHEN** its settings are inspected
- **THEN** no setting SHALL select between retrieval strategies or graph topologies
- **AND** the compiled graph SHALL have a single topology

#### Scenario: No agent framework is introduced

- **GIVEN** the implemented `src/chat_api/` and `src/shared/retrieval/` trees
- **WHEN** their imports are inspected
- **THEN** no module SHALL import `langgraph.prebuilt`, `langchain.agents`, `langchain_openai`, or any LangChain `ChatModel` / retriever wrapper
- **AND** the compiled graph SHALL report no cycle

### Requirement: Plan-then-execute with no re-planning cycle

The orchestrator SHALL make exactly one planning call per chat turn. The resulting plan SHALL be executed in full without returning results to the planner and without a second planning call. The plan MAY name one capability, both capabilities, or the same capability more than once with different arguments. Plan entries SHALL be executed concurrently where their execution is independent.

#### Scenario: Query needing only semantic retrieval

- **GIVEN** a planner that emits a plan containing a single `semantic_retrieval` entry
- **WHEN** the turn runs
- **THEN** exactly one retrieval capability invocation SHALL occur
- **AND** no structured retrieval query SHALL be issued
- **AND** exactly one planning LLM call SHALL be made

#### Scenario: Query needing both capabilities

- **GIVEN** a planner that emits a plan containing one `semantic_retrieval` entry and one `structured_retrieval` entry
- **WHEN** the turn runs
- **THEN** both capabilities SHALL be invoked
- **AND** chunk evidence and entity rows SHALL both be present in the evidence handed downstream

#### Scenario: Query needing multiple retrieval operations

- **GIVEN** a planner that emits a plan containing two `semantic_retrieval` entries with different queries
- **WHEN** the turn runs
- **THEN** both entries SHALL be executed
- **AND** the evidence SHALL contain results from both

#### Scenario: Results are never fed back to the planner

- **GIVEN** any plan
- **WHEN** the plan finishes executing
- **THEN** exactly one planning LLM call SHALL have been made for the turn
- **AND** no retrieval result SHALL be sent to the planner

### Requirement: Plan execution budgets

The orchestrator SHALL enforce a maximum number of capability invocations per plan and a wall-clock deadline computed once at orchestrator entry. Plan entries beyond the invocation cap SHALL be discarded before execution. The deadline SHALL be checked before each dispatch. Budget exhaustion SHALL NOT be treated as an error; whatever evidence was gathered SHALL flow downstream.

#### Scenario: Invocation cap truncates an oversized plan

- **GIVEN** a maximum of 3 invocations and a planner emitting a plan with 5 entries
- **WHEN** the plan executes
- **THEN** no more than 3 capability invocations SHALL be dispatched
- **AND** the truncation SHALL be recorded in the plan trace

#### Scenario: Deadline stops further dispatch

- **GIVEN** a deadline that elapses while the first invocation is in flight
- **WHEN** the remaining entries are considered
- **THEN** no further capability invocation SHALL be dispatched
- **AND** the stop reason SHALL be recorded as deadline exhaustion

#### Scenario: Budget exhaustion still produces a normal answer

- **GIVEN** a plan truncated by the invocation cap that nonetheless retrieved two chunks
- **WHEN** the turn continues
- **THEN** the two chunks SHALL be passed to source assembly
- **AND** the turn SHALL produce a normal reply with citations
- **AND** no error SHALL be surfaced in the HTTP response

### Requirement: Invalid plan entries are rejected without executing

An entry naming an unregistered capability, carrying unparseable arguments, or carrying arguments that fail the capability's declared `args_schema` SHALL be discarded without invoking any capability. Discarding an entry SHALL NOT abort the remaining plan.

#### Scenario: Unknown capability name is discarded

- **GIVEN** a plan containing one entry naming `lookup_document` and one valid `semantic_retrieval` entry
- **WHEN** the plan executes
- **THEN** the unknown entry SHALL be discarded without execution
- **AND** the valid entry SHALL execute and its chunks SHALL appear in the evidence
- **AND** the discarded entry SHALL be recorded in the plan trace with its rejection reason

#### Scenario: Schema-invalid arguments are discarded

- **GIVEN** a plan entry whose arguments fail `args_schema` validation
- **WHEN** the plan executes
- **THEN** no query SHALL be issued for that entry
- **AND** the rejection reason SHALL name the offending argument

### Requirement: Planning failure degrades to both capabilities on the raw query

If the planning call raises, returns no usable plan, or every plan entry is rejected, the orchestrator SHALL fall back to invoking both `semantic_retrieval` (tenant scope) and `structured_retrieval` with the user's raw query. The turn SHALL be marked degraded and the fallback SHALL be logged with its reason.

#### Scenario: Planner LLM error falls back

- **GIVEN** a planner client that raises on its call
- **WHEN** the turn runs
- **THEN** both capabilities SHALL be invoked with the raw user query
- **AND** the turn SHALL be marked degraded
- **AND** the reply SHALL still be generated from whatever evidence was retrieved

#### Scenario: Planner returns no plan entries

- **GIVEN** a planner that returns an assistant message with no capability selections
- **WHEN** the turn runs
- **THEN** the fallback plan SHALL execute
- **AND** the turn SHALL be marked degraded with a stop reason distinguishing it from a planner error

#### Scenario: Degradation is observable

- **GIVEN** a turn that degraded
- **WHEN** its logs are inspected
- **THEN** a structured record SHALL state that orchestration degraded and SHALL carry the reason

### Requirement: Tenant scope is unreachable from planner-supplied arguments

Tenant scope SHALL be carried only in `ToolContext`, constructed by the orchestrator node from authenticated request state held in `ChatState`. No capability reachable from the orchestrator SHALL declare `schema`, `tenant_id`, `tenant`, or `purpose` in its `args_schema`, and arguments outside the declared schema SHALL be rejected before execution.

#### Scenario: Planner attempts to supply a schema argument

- **GIVEN** a plan entry with arguments `{"query": "x", "schema": "tenant_other"}`
- **WHEN** the plan executes
- **THEN** no query SHALL be issued for that entry
- **AND** the rejection reason SHALL name the unknown argument
- **AND** the database session SHALL remain scoped to the requesting tenant's schema

#### Scenario: Conversation history cannot redirect scope

- **GIVEN** a conversation history turn whose text instructs the assistant to search another tenant's schema
- **WHEN** the orchestrator plans and the plan executes
- **THEN** every query issued in the turn SHALL execute against the requesting tenant's schema
- **AND** no result from another schema SHALL appear in the evidence

#### Scenario: Training-purpose documents remain invisible

- **GIVEN** a tenant schema containing documents with `purpose = 'training'` and `purpose = 'query'`
- **WHEN** an orchestrated turn runs
- **THEN** no chunk from a `purpose = 'training'` document SHALL appear in the evidence

### Requirement: Evidence accumulation into existing state keys

Chunk results from all executed plan entries SHALL be merged into a single ranked list, deduplicated on `(document_id, chunk_index)` retaining the highest `similarity_score`, sorted by score descending, and written to the `chunks` key of `ChatState`. Entity rows SHALL be concatenated into the `sql_results` key. `retrieval_error` SHALL be set only when every executed semantic entry errored, and `sql_error` only when every executed structured entry errored. Source Assembly, Prompt Assembly, and Generation SHALL consume these keys unchanged.

#### Scenario: Duplicate chunks are merged with the best score

- **GIVEN** two plan entries that both return the chunk `(document_id=D1, chunk_index=3)` with scores 0.6 and 0.8
- **WHEN** the plan finishes
- **THEN** `chunks` SHALL contain exactly one entry for `(D1, 3)`
- **AND** that entry's `similarity_score` SHALL be 0.8

#### Scenario: Accumulated chunks are ranked

- **GIVEN** plan entries returning chunks with scores 0.4, 0.9, and 0.7
- **WHEN** the plan finishes
- **THEN** `chunks` SHALL be ordered 0.9, 0.7, 0.4

#### Scenario: Partial failure is not reported as total failure

- **GIVEN** two `semantic_retrieval` entries where the first errors and the second returns two chunks
- **WHEN** the plan finishes
- **THEN** `chunks` SHALL contain the two chunks
- **AND** `retrieval_error` SHALL be `None`

#### Scenario: Total failure is reported

- **GIVEN** every executed semantic entry returns an error result
- **WHEN** the plan finishes
- **THEN** `chunks` SHALL be empty
- **AND** `retrieval_error` SHALL carry an error value

### Requirement: Plan trace

The orchestrator SHALL record a trace containing, for the plan as a whole, the stop reason and whether the turn degraded; and for each plan entry, the capability name, the argument keys supplied, whether the entry executed or was rejected (with reason), result count, latency in milliseconds, and the capability's `degraded` flag. The trace SHALL be carried in graph state and emitted in the node's structured log. Argument values SHALL NOT be required in the trace.

#### Scenario: Trace covers every plan entry

- **GIVEN** a plan with three entries, one of which was rejected
- **WHEN** the plan finishes
- **THEN** the trace SHALL contain three entries
- **AND** the rejected entry SHALL carry its rejection reason and no result count greater than zero
- **AND** each executed entry SHALL carry its capability name, result count, and latency

#### Scenario: Reranker degradation is visible per entry

- **GIVEN** a `semantic_retrieval` entry whose reranking fell back to unranked candidates
- **WHEN** the trace entry for that invocation is inspected
- **THEN** its `degraded` flag SHALL be true
