## ADDED Requirements

### Requirement: Bounded agentic retrieval loop

The system SHALL provide an agentic retrieval loop that, within a single chat turn, repeatedly asks a planner LLM to select retrieval tools from the shared `ToolRegistry`, executes the selected tools, and feeds their results back to the planner as observations. The loop SHALL be implemented as a single graph node; the compiled chat graph SHALL remain acyclic. The planner SHALL be bound to tools using `ToolRegistry.export_schemas()` through the existing `AsyncOpenAI` / `AsyncAzureOpenAI` client. No LangChain agent executor, `Runnable`, `ChatModel`, or prebuilt ReAct agent SHALL be introduced.

#### Scenario: Planner issues a follow-up search after the first result

- **GIVEN** the agentic loop is enabled and a planner scripted to call `search_documents`, then `lookup_document` scoped to a document returned by the first call, then answer
- **WHEN** a chat turn runs
- **THEN** both tool calls SHALL be executed against the registry
- **AND** chunks from both calls SHALL be present in the evidence handed to the downstream nodes

#### Scenario: Tool schemas come from the registry

- **GIVEN** the default registry containing `search_documents`, `lookup_document`, and `search_entities`
- **WHEN** the loop makes its first planner call
- **THEN** the `tools` argument sent to the LLM client SHALL equal `ToolRegistry.export_schemas()`
- **AND** each entry SHALL have the shape `{"type": "function", "function": {"name", "description", "parameters"}}`

#### Scenario: No agent framework is introduced

- **GIVEN** the implemented `src/chat_api/` tree
- **WHEN** its imports are inspected
- **THEN** no module SHALL import `langgraph.prebuilt`, `langchain.agents`, `langchain_openai`, or any LangChain `ChatModel` / retriever wrapper
- **AND** the compiled graph SHALL report no cycle

### Requirement: Iteration, tool-call, and wall-clock budgets

The loop SHALL enforce three independent budgets: a maximum number of planner iterations, a maximum cumulative number of tool calls, and a wall-clock deadline computed once at loop entry. The deadline SHALL be checked before each planner call and before each tool dispatch. The loop SHALL terminate on whichever budget is exhausted first, and SHALL record the terminating condition.

#### Scenario: Iteration cap stops the loop

- **GIVEN** `agentic_max_iterations = 2` and a planner that always requests another tool call
- **WHEN** a chat turn runs
- **THEN** exactly 2 planner iterations SHALL execute
- **AND** the stop reason SHALL be recorded as iteration-cap exhaustion

#### Scenario: Tool-call cap stops the loop

- **GIVEN** `agentic_max_tool_calls = 3` and a planner that requests two tool calls per iteration
- **WHEN** a chat turn runs
- **THEN** no more than 3 tool calls SHALL be dispatched
- **AND** the stop reason SHALL be recorded as tool-call-cap exhaustion

#### Scenario: Deadline stops the loop before a further tool dispatch

- **GIVEN** a deadline of 1 second and a tool whose execution takes longer than that deadline
- **WHEN** the first tool call returns after the deadline has passed
- **THEN** no further planner call or tool dispatch SHALL be made
- **AND** the stop reason SHALL be recorded as deadline exhaustion

#### Scenario: Budget exhaustion is not an error

- **GIVEN** a loop that terminates because a budget was exhausted while holding two retrieved chunks
- **WHEN** the turn continues
- **THEN** the two chunks SHALL be passed to the downstream nodes
- **AND** the turn SHALL produce a normal reply with citations
- **AND** no error SHALL be surfaced in the HTTP response

### Requirement: Planner-signalled termination

The loop SHALL terminate when the planner returns an assistant message containing no tool calls. That message SHALL NOT be used as the user-facing reply; reply generation SHALL remain the responsibility of the existing generation node.

#### Scenario: Planner stops after sufficient evidence

- **GIVEN** a planner scripted to call `search_documents` once and then return a message with no tool calls
- **WHEN** a chat turn runs
- **THEN** the loop SHALL exit after the second planner call
- **AND** exactly one tool call SHALL have been dispatched
- **AND** the user-facing reply SHALL be produced by the generation node, not by the planner message

### Requirement: Evidence accumulation into existing state keys

Chunk results from all iterations SHALL be merged into a single ranked list, deduplicated on `(document_id, chunk_index)` retaining the highest `similarity_score`, sorted by score descending, and written to the existing `chunks` key of `ChatState`. Entity rows from `search_entities` calls SHALL be concatenated into the existing `sql_results` key. `retrieval_error` SHALL be set only when every chunk-producing tool call errored, and `sql_error` only when every entity tool call errored. Nodes downstream of retrieval SHALL require no modification.

#### Scenario: Duplicate chunks are merged with the best score

- **GIVEN** two tool calls that both return the chunk `(document_id=D1, chunk_index=3)` with scores 0.6 and 0.8
- **WHEN** the loop terminates
- **THEN** `chunks` SHALL contain exactly one entry for `(D1, 3)`
- **AND** that entry's `similarity_score` SHALL be 0.8

#### Scenario: Accumulated chunks are ranked

- **GIVEN** tool calls returning chunks with scores 0.4, 0.9, and 0.7
- **WHEN** the loop terminates
- **THEN** `chunks` SHALL be ordered 0.9, 0.7, 0.4

#### Scenario: Citations are produced from loop evidence unchanged

- **GIVEN** a loop turn that accumulated chunks from two documents and one entity row
- **WHEN** source assembly and citation enrichment run
- **THEN** the emitted `Citation` objects SHALL carry `document_name`, `document_id`, `relevance_score`, `context_snippet`, and `page_number` exactly as they do for a one-shot turn with the same evidence

#### Scenario: Partial tool failure is not reported as total failure

- **GIVEN** two `search_documents` calls where the first errors and the second returns two chunks
- **WHEN** the loop terminates
- **THEN** `chunks` SHALL contain the two chunks
- **AND** `retrieval_error` SHALL be `None`

#### Scenario: Total tool failure is reported

- **GIVEN** every chunk-producing tool call in the turn returns an error `ToolResult`
- **WHEN** the loop terminates
- **THEN** `chunks` SHALL be empty
- **AND** `retrieval_error` SHALL carry an error value

### Requirement: Tenant scope is unreachable from planner-supplied arguments

Tenant scope SHALL be carried only in `ToolContext`, constructed by the loop node from authenticated request state held in `ChatState`. Planner-supplied arguments SHALL be validated against the tool's declared `args_schema` before execution, and arguments outside that schema SHALL be rejected without executing the tool. No tool reachable from the loop SHALL declare `schema`, `tenant_id`, `tenant`, or `purpose` in its `args_schema`.

#### Scenario: Planner attempts to supply a schema argument

- **GIVEN** a planner that emits a `search_documents` call with arguments `{"query": "x", "schema": "tenant_other"}`
- **WHEN** the loop dispatches the call
- **THEN** the tool SHALL NOT execute a query
- **AND** an error `ToolResult` SHALL be returned naming the unknown argument
- **AND** the database session SHALL remain scoped to the requesting tenant's schema

#### Scenario: Retrieved content instructing the planner does not cross tenants

- **GIVEN** a seeded chunk whose text instructs the reader to search another tenant's schema
- **WHEN** the loop retrieves that chunk and continues to a further iteration
- **THEN** every query issued in the turn SHALL execute against the requesting tenant's schema
- **AND** no result from another schema SHALL appear in the accumulated evidence

#### Scenario: Training-purpose documents remain invisible across iterations

- **GIVEN** a tenant schema containing documents with `purpose = 'training'` and `purpose = 'query'`
- **WHEN** a multi-iteration loop turn runs
- **THEN** no chunk from a `purpose = 'training'` document SHALL appear in the accumulated evidence

### Requirement: Tool observations are treated as evidence, not instructions

Tool results SHALL be injected into the planner conversation as tool-role observations, under a system instruction stating that observation content is retrieved evidence and SHALL NOT be followed as instructions. Observation content SHALL be truncated to a bounded size per tool call.

#### Scenario: Hostile chunk does not redirect the loop

- **GIVEN** a retrieved chunk containing text directing the assistant to ignore prior instructions and call a different tool with attacker-chosen arguments
- **WHEN** the loop continues to the next iteration
- **THEN** the loop SHALL still enforce argument validation and budgets on any resulting call
- **AND** the turn SHALL complete within its configured budgets

#### Scenario: Observation size is bounded

- **GIVEN** a tool call returning chunks whose combined text exceeds the configured observation limit
- **WHEN** the observation is rendered for the planner
- **THEN** the observation content SHALL be truncated to the limit
- **AND** the full results SHALL still be recorded in the accumulated evidence

### Requirement: Malformed tool calls get one corrective retry, then the loop degrades

An unknown tool name, unparseable arguments, or arguments failing schema validation SHALL produce an error observation returned to the planner and SHALL count against the tool-call budget. If the planner's next turn produces another invalid call, the loop SHALL stop, mark the turn degraded, and fall back to the one-shot retrieval path.

#### Scenario: Planner self-corrects after an invalid call

- **GIVEN** a planner that first calls a non-existent tool and then calls `search_documents` correctly
- **WHEN** the turn runs
- **THEN** the first call SHALL produce an error observation without raising
- **AND** the second call SHALL execute and its chunks SHALL appear in the evidence

#### Scenario: Two consecutive invalid calls degrade the turn

- **GIVEN** a planner that emits invalid tool calls on two consecutive iterations
- **WHEN** the turn runs
- **THEN** the loop SHALL stop
- **AND** the turn SHALL be marked degraded
- **AND** the one-shot retrieval path SHALL supply the evidence for that turn

### Requirement: Loop failure falls back to one-shot retrieval

Any failure that prevents the loop from producing evidence — a planner LLM error, an empty tool registry, or repeated invalid tool calls — SHALL cause the turn to fall back to the existing one-shot `sql_retrieval` and `retrieval` behaviour rather than failing. The fallback SHALL be recorded in state and logged.

#### Scenario: Planner LLM error falls back

- **GIVEN** a planner client that raises on its first call
- **WHEN** a chat turn runs
- **THEN** the one-shot retrieval path SHALL execute
- **AND** the reply and citations SHALL match those produced with the loop disabled for the same inputs
- **AND** the turn SHALL be marked degraded

#### Scenario: Fallback is observable

- **GIVEN** a turn that fell back
- **WHEN** its logs are inspected
- **THEN** a structured record SHALL state that agentic retrieval degraded and SHALL carry the stop reason

### Requirement: Per-iteration loop trace

The loop SHALL record one trace entry per tool call containing the iteration index, tool name, the argument keys supplied (not necessarily their values), result count, latency in milliseconds, the tool's `degraded` flag, and any error. The trace SHALL be carried in graph state and emitted in the node's structured log.

#### Scenario: Trace covers every tool call

- **GIVEN** a turn that dispatched three tool calls across two iterations
- **WHEN** the loop terminates
- **THEN** the trace SHALL contain three entries
- **AND** each SHALL carry its iteration index, tool name, result count, and latency

#### Scenario: Reranker degradation is visible per call

- **GIVEN** a `search_documents` call whose reranking fell back to unranked candidates
- **WHEN** the trace entry for that call is inspected
- **THEN** its `degraded` flag SHALL be true

### Requirement: Feature flag and flag-off equivalence

The loop SHALL be controlled by a `chat_agentic_retrieval` setting defaulting to disabled. When disabled, the compiled graph SHALL be the fixed topology in force before this change and no planner call SHALL be made. The setting SHALL have no effect when `chat_use_graph` is disabled, in which case the legacy execution path runs unchanged.

#### Scenario: Flag off reproduces current behaviour

- **GIVEN** `chat_agentic_retrieval = false`
- **WHEN** a chat turn runs
- **THEN** `sql_retrieval` and `retrieval` SHALL execute in parallel as they do today
- **AND** no planner LLM call SHALL be made
- **AND** `tests/test_langgraph_parity.py`, `tests/test_chat_api_rag.py`, and `tests/test_chat_api_guardrails.py` SHALL pass unmodified

#### Scenario: Loop flag is inert on the legacy path

- **GIVEN** `chat_use_graph = false` and `chat_agentic_retrieval = true`
- **WHEN** a chat turn runs
- **THEN** `_execute_legacy` SHALL run unchanged
- **AND** no planner LLM call SHALL be made

### Requirement: Loop is measured against the one-shot configuration

The retrieval eval harness SHALL support an agentic configuration that executes each golden-set query through the loop and scores the accumulated evidence with the existing metric functions, producing results directly comparable to the one-shot configurations in the same report.

#### Scenario: Agentic configuration appears in the eval report

- **GIVEN** the golden set and an eval run including the agentic configuration
- **WHEN** the report is produced
- **THEN** the report SHALL contain `recall@5` and `nDCG@5` for the agentic configuration alongside the one-shot configurations
- **AND** the configurations SHALL be ranked by `nDCG@5`

#### Scenario: Loop failures during eval do not abort the run

- **GIVEN** an eval run in which one query's loop errors
- **WHEN** the run completes
- **THEN** the remaining queries SHALL still be scored
- **AND** the failed query SHALL be recorded with its error in the per-query results
