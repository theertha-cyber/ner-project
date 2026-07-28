## Why

Retrieval today is one shot: `retrieval_node` (`src/chat_api/graph/nodes.py:87`) issues exactly one `retriever.retrieve` call per chat turn with the user's raw message as the query, and `sql_retrieval_node` issues exactly one SQL attempt in parallel. A question whose answer lives in two documents, or whose wording does not lexically or semantically match the chunk that answers it, cannot be recovered — there is no second attempt, no reformulation, and no way to follow a lead found in the first result. Worse, `GuardrailService.assess_complexity` actively refuses exactly the questions that would benefit most: a message scoring above 3 is answered with "That question requires multiple lookups. Please simplify" (`src/chat_api/graph/nodes.py:73`), turning a retrieval limitation into a product limitation.

The prerequisites are now in place. `retrieval-tools-and-eval` shipped a tenant-scoped, argument-validated tool layer (`ToolRegistry`, `search_documents`, `lookup_document`, `search_entities`, `ToolContext`) whose schemas already export in OpenAI tool-calling format, plus a golden-set eval harness that can measure whether a change to retrieval actually helps. The tool layer currently has exactly one consumer — the eval harness. This change makes the chat pipeline its second consumer.

## What Changes

- Add an **agentic retrieval loop** as a new LangGraph node (`agentic_retrieval`) in `src/chat_api/graph/`: an LLM-driven plan → call tools → observe → decide cycle over the existing `ToolRegistry`, bounded by explicit iteration, tool-call, and wall-clock budgets.
- The loop LLM is bound to the exported tool schemas (`registry.export_schemas()`) via the existing `AsyncAzureOpenAI` / `AsyncOpenAI` client. No LangChain `Runnable`, agent executor, or `ChatModel` wrapper is introduced — consistent with the constraint already in force for the graph.
- **Evidence accumulation across iterations**: chunk results are merged and deduplicated by `(document_id, chunk_index)` keeping the best score; entity rows are accumulated per tool call. The loop's terminal state populates the *existing* `chunks` and `sql_results` keys of `ChatState`, so `ner_enrichment`, `source_assembly`, `prompt_assembly`, and `generation` are untouched and citations keep working exactly as they do today.
- **Budgets and termination**: the loop terminates when the model returns a message with no tool calls, when the iteration cap is reached, when the tool-call cap is reached, or when a wall-clock deadline derived from the ADR-007 P95 < 10s target expires. Budget exhaustion is not an error — the loop stops and hands whatever evidence it has to the normal generation path.
- **Fallback path**: any loop failure (LLM error, malformed tool call after retry, no tool exposed) degrades to the existing one-shot `sql_retrieval` + `retrieval` behaviour rather than failing the turn. Degradation is recorded in state and logged.
- **Feature-flagged**: new setting `chat_agentic_retrieval` (default `false`). When off, the graph is byte-for-byte the topology in force today. This mirrors the existing `chat_use_graph` flag pattern and keeps the change reversible in production without a deploy.
- **Complexity guardrail becomes budget-aware**: when the agentic loop is enabled, a complexity score above the threshold routes *into* the loop with a larger budget instead of returning the "please simplify" decline. Blocked question types (classification, content generation, summarization, cross-tenant, PII) are unchanged and still short-circuit before any retrieval.
- **Retrieved content is data, never instructions**: tool observations are injected as `role: "tool"` messages under a system instruction that the loop planner treats chunk text strictly as evidence. Tool arguments remain LLM-supplied but tenant scope stays structurally unreachable (it lives only in `ToolContext`), so the existing isolation guarantee is inherited unchanged.
- **Loop trace in state and logs**: each iteration emits a structured record (iteration index, tool name, argument keys, result count, latency, degraded flag), and the accumulated trace is carried in `ChatState` for observability and eval.
- **Measured, not asserted**: the `retrieval-eval` harness gains a mode that scores the loop end-to-end against the golden set and compares it side-by-side with the one-shot configuration, so enabling the flag is a measured decision.
- No new database migration. No new required Python dependency. No change to any HTTP request or response schema.

## Capabilities

### New Capabilities

- `agentic-retrieval`: the loop itself — planner contract and tool binding, iteration/tool-call/wall-clock budgets, termination conditions, evidence accumulation and deduplication, malformed-tool-call handling, fallback-to-one-shot semantics, injection-resistance rules for tool observations, and the per-iteration trace format.

### Modified Capabilities

- `chat-orchestration-graph` (currently specified in the unarchived `langgraph-orchestration` change, not yet synced to `openspec/specs/`): its requirement *"Fixed topology with no agentic behaviour"* — which states the graph SHALL NOT contain loops, tool-calling nodes, or LLM-decided routing — is superseded. The replacement requirement admits exactly one bounded loop node behind a feature flag, and pins the flag-off topology to the current DAG.
- `chat-api`: the complexity guardrail requirement changes. Multi-lookup questions are no longer declined outright when the loop is enabled; they are answered within a budget. Blocked-question-type behaviour and the response contract are unchanged.
- `retrieval-tools` (specified in the unarchived `retrieval-tools-and-eval` change): gains a requirement that a `ToolResult` be renderable into a bounded, LLM-consumable observation string, and that `ToolContext` carry the loop's remaining budget so a tool can be denied rather than started when no budget remains.

## Impact

**Code**
- `src/chat_api/graph/agentic.py` (new) — the loop: planner call, tool dispatch, evidence accumulator, budget bookkeeping.
- `src/chat_api/graph/nodes.py` — new `agentic_retrieval_node`; existing `retrieval_node` / `sql_retrieval_node` retained unchanged as the fallback and flag-off path.
- `src/chat_api/graph/builder.py` — conditional routing after `guardrail`: loop node when `chat_agentic_retrieval` is on, current parallel fan-out when off.
- `src/chat_api/graph/state.py` — additive keys: `tool_trace`, `agentic_degraded`, `agentic_stop_reason`. Existing keys keep their meaning.
- `src/chat_api/services/rag_orchestrator.py` — builds the `ToolRegistry` once and supplies `sql_search` (its existing validated SQL path) into `ToolContext`. `_execute_legacy` is not touched.
- `src/shared/retrieval/tools/base.py` — `ToolResult.to_observation()` and budget fields on `ToolContext`.
- `src/shared/config.py` — `chat_agentic_retrieval`, `agentic_max_iterations`, `agentic_max_tool_calls`, `agentic_deadline_seconds`.
- `src/shared/retrieval/eval/runner.py` — an agentic configuration alongside the existing retriever configurations.

**Tests**
- `tests/test_agentic_loop.py` (new) — budgets, termination, accumulation, fallback, injection resistance, with a scripted fake LLM client.
- `tests/test_langgraph_parity.py`, `tests/test_chat_api_rag.py`, `tests/test_chat_api_guardrails.py` — must pass unmodified with the flag off.

**Operational**
- Each turn now issues 1 + N LLM calls (planner iterations) instead of 1. Token cost and latency rise with the flag on; the deadline budget is the control. The ADR-007 P95 < 10s target is the binding constraint on default budget values.

**Not in scope**: query rewriting as a standalone retrieval strategy, HyDE, multi-query expansion, checkpointing/resumable conversations, human-in-the-loop interrupts, answer-quality (LLM-as-judge) evaluation, streaming the loop's intermediate steps to the portal UI, and any change to ingestion, chunking, or embeddings.

## Open Questions

1. **Default budget values.** Assumption: `agentic_max_iterations = 3`, `agentic_max_tool_calls = 6`, `agentic_deadline_seconds = 8` (leaving headroom under the ADR-007 P95 < 10s target for generation). Confirm, or set from a measured latency run before defaults are committed.
2. **Planner model.** Assumption: the loop reuses `orchestrator.llm_model` (the same deployment used for generation). A cheaper/faster deployment for planning would cut cost and latency but adds a second deployment to configure — confirm whether a separate `agentic_planner_model` setting is wanted now or deferred.
3. **Complexity guardrail with the flag off.** Assumption: unchanged — high-complexity questions still receive the "please simplify" decline when `chat_agentic_retrieval` is false, so flag-off behaviour is identical to today. Confirm.
4. **Conversation context in the planner prompt.** Assumption: the last three turns are supplied to the planner (matching `_sql_source`'s existing behaviour) so follow-up questions can resolve "that document". Confirm this is acceptable given it enlarges the injection surface across turns.
5. **`search_entities` inside the loop.** The SQL path already runs its own LLM call for SQL generation, so an agentic turn that calls it incurs a nested LLM call. Assumption: acceptable, counted against the tool-call budget like any other tool. Confirm, or restrict `search_entities` to a single call per turn.
6. **Whether the flag ships on.** Assumption: it ships off, is enabled only after the eval comparison shows the loop beats one-shot on the golden set, and that comparison is the exit criterion for this change rather than a follow-up.
