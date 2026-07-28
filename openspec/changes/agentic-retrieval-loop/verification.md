# Verification Plan

**Change:** agentic-retrieval-loop
**Generated:** 2026-07-28
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | agentic-retrieval | Bounded agentic retrieval loop | Planner issues a follow-up search after the first result | Given a scripted planner that calls `search_documents` then `lookup_document` scoped to a document from the first call, when the turn runs, then both calls execute and chunks from both appear in the evidence handed downstream | unit test: `tests/test_agentic_loop.py::test_follow_up_lookup_after_search` | - [ ] |
| 2 | agentic-retrieval | Bounded agentic retrieval loop | Tool schemas come from the registry | Given the default registry, when the first planner call is made, then the `tools` argument equals `ToolRegistry.export_schemas()` and every entry has shape `{"type":"function","function":{name,description,parameters}}` | unit test: `tests/test_agentic_loop.py::test_planner_bound_to_registry_schemas` | - [ ] |
| 3 | agentic-retrieval | Bounded agentic retrieval loop | No agent framework is introduced | Given the implemented `src/chat_api/` tree, when imports are inspected, then no module imports `langgraph.prebuilt`, `langchain.agents`, `langchain_openai`, or a LangChain ChatModel/retriever wrapper, and the compiled graph reports no cycle | static test: `tests/test_agentic_graph_topology.py::test_no_agent_framework_imports_and_acyclic` | - [ ] |
| 4 | agentic-retrieval | Iteration, tool-call, and wall-clock budgets | Iteration cap stops the loop | Given `agentic_max_iterations = 2` and a planner that always requests more, when the turn runs, then exactly 2 planner iterations execute and the stop reason is iteration-cap exhaustion | unit test: `tests/test_agentic_loop.py::test_iteration_cap_stops_loop` | - [ ] |
| 5 | agentic-retrieval | Iteration, tool-call, and wall-clock budgets | Tool-call cap stops the loop | Given `agentic_max_tool_calls = 3` and a planner requesting two calls per iteration, when the turn runs, then at most 3 tool calls are dispatched and the stop reason is tool-call-cap exhaustion | unit test: `tests/test_agentic_loop.py::test_tool_call_cap_stops_loop` | - [ ] |
| 6 | agentic-retrieval | Iteration, tool-call, and wall-clock budgets | Deadline stops the loop before a further tool dispatch | Given a 1-second deadline and a tool that exceeds it, when the first call returns past the deadline, then no further planner call or tool dispatch occurs and the stop reason is deadline exhaustion | unit test: `tests/test_agentic_loop.py::test_deadline_stops_before_dispatch` | - [ ] |
| 7 | agentic-retrieval | Iteration, tool-call, and wall-clock budgets | Budget exhaustion is not an error | Given a loop that exhausts a budget holding two chunks, when the turn continues, then those chunks reach the downstream nodes, a normal reply with citations is produced, and no error surfaces in the HTTP response | unit test: `tests/test_agentic_loop.py::test_budget_exhaustion_returns_normal_reply` | - [ ] |
| 8 | agentic-retrieval | Planner-signalled termination | Planner stops after sufficient evidence | Given a planner that calls `search_documents` once then returns a message with no tool calls, when the turn runs, then the loop exits after the second planner call, exactly one tool call was dispatched, and the reply comes from the generation node rather than the planner message | unit test: `tests/test_agentic_loop.py::test_planner_signalled_termination` | - [ ] |
| 9 | agentic-retrieval | Evidence accumulation into existing state keys | Duplicate chunks are merged with the best score | Given two calls both returning `(D1, chunk_index=3)` with scores 0.6 and 0.8, when the loop terminates, then `chunks` holds one entry for `(D1,3)` with score 0.8 | unit test: `tests/test_agentic_loop.py::test_dedup_keeps_max_score` | - [ ] |
| 10 | agentic-retrieval | Evidence accumulation into existing state keys | Accumulated chunks are ranked | Given calls returning scores 0.4, 0.9, 0.7, when the loop terminates, then `chunks` is ordered 0.9, 0.7, 0.4 | unit test: `tests/test_agentic_loop.py::test_accumulated_chunks_ranked` | - [ ] |
| 11 | agentic-retrieval | Evidence accumulation into existing state keys | Citations are produced from loop evidence unchanged | Given a loop turn with chunks from two documents and one entity row, when source assembly and citation enrichment run, then the emitted `Citation` objects carry `document_name`, `document_id`, `relevance_score`, `context_snippet`, `page_number` exactly as for a one-shot turn with the same evidence | unit test: `tests/test_agentic_loop.py::test_citation_parity_with_one_shot` | - [ ] |
| 12 | agentic-retrieval | Evidence accumulation into existing state keys | Partial tool failure is not reported as total failure | Given two `search_documents` calls where the first errors and the second returns two chunks, when the loop terminates, then `chunks` holds the two chunks and `retrieval_error` is `None` | unit test: `tests/test_agentic_loop.py::test_partial_failure_no_retrieval_error` | - [ ] |
| 13 | agentic-retrieval | Evidence accumulation into existing state keys | Total tool failure is reported | Given every chunk-producing call errors, when the loop terminates, then `chunks` is empty and `retrieval_error` carries an error value | unit test: `tests/test_agentic_loop.py::test_total_failure_sets_retrieval_error` | - [ ] |
| 14 | agentic-retrieval | Tenant scope is unreachable from planner-supplied arguments | Planner attempts to supply a schema argument | Given a planner emitting `search_documents` with `{"query":"x","schema":"tenant_other"}`, when the call is dispatched, then no query executes, an error `ToolResult` names the unknown argument, and the session stays scoped to the requesting tenant's schema | unit test: `tests/test_agentic_loop.py::test_schema_argument_rejected` | - [ ] |
| 15 | agentic-retrieval | Tenant scope is unreachable from planner-supplied arguments | Retrieved content instructing the planner does not cross tenants | Given a seeded chunk instructing a search of another tenant's schema, when the loop continues to a further iteration, then every query executes against the requesting tenant's schema and no other schema's results appear in the evidence | integration test: `tests/test_agentic_loop_integration.py::test_hostile_chunk_does_not_cross_schema` | - [ ] |
| 16 | agentic-retrieval | Tenant scope is unreachable from planner-supplied arguments | Training-purpose documents remain invisible across iterations | Given a schema with `purpose='training'` and `purpose='query'` documents, when a multi-iteration turn runs, then no `purpose='training'` chunk appears in the accumulated evidence | integration test: `tests/test_agentic_loop_integration.py::test_training_purpose_excluded_across_iterations` | - [ ] |
| 17 | agentic-retrieval | Tool observations are treated as evidence, not instructions | Hostile chunk does not redirect the loop | Given a retrieved chunk directing the assistant to ignore prior instructions and call a different tool, when the loop continues, then argument validation and budgets still apply to any resulting call and the turn completes within its budgets | unit test: `tests/test_agentic_loop.py::test_hostile_chunk_still_bounded` | - [ ] |
| 18 | agentic-retrieval | Tool observations are treated as evidence, not instructions | Observation size is bounded | Given a call whose combined chunk text exceeds the observation limit, when the observation is rendered, then it is truncated to the limit while the full results remain in the accumulated evidence | unit test: `tests/test_agentic_loop.py::test_observation_truncated_evidence_retained` | - [ ] |
| 19 | agentic-retrieval | Malformed tool calls get one corrective retry, then the loop degrades | Planner self-corrects after an invalid call | Given a planner that first calls a non-existent tool then calls `search_documents` correctly, when the turn runs, then the first call yields an error observation without raising and the second call's chunks appear in the evidence | unit test: `tests/test_agentic_loop.py::test_planner_self_corrects_after_invalid_call` | - [ ] |
| 20 | agentic-retrieval | Malformed tool calls get one corrective retry, then the loop degrades | Two consecutive invalid calls degrade the turn | Given a planner emitting invalid calls on two consecutive iterations, when the turn runs, then the loop stops, the turn is marked degraded, and the one-shot path supplies the evidence | unit test: `tests/test_agentic_loop.py::test_two_invalid_calls_degrade_to_one_shot` | - [ ] |
| 21 | agentic-retrieval | Loop failure falls back to one-shot retrieval | Planner LLM error falls back | Given a planner client that raises on its first call, when the turn runs, then the one-shot path executes, reply and citations match the loop-disabled result for the same inputs, and the turn is marked degraded | unit test: `tests/test_agentic_loop.py::test_planner_error_falls_back` | - [ ] |
| 22 | agentic-retrieval | Loop failure falls back to one-shot retrieval | Fallback is observable | Given a turn that fell back, when its logs are inspected, then a structured record states that agentic retrieval degraded and carries the stop reason | log assertion test: `tests/test_agentic_loop.py::test_fallback_logged_with_stop_reason` | - [ ] |
| 23 | agentic-retrieval | Per-iteration loop trace | Trace covers every tool call | Given a turn dispatching three tool calls across two iterations, when the loop terminates, then the trace holds three entries each carrying iteration index, tool name, result count, and latency | unit test: `tests/test_agentic_loop.py::test_trace_entry_per_tool_call` | - [ ] |
| 24 | agentic-retrieval | Per-iteration loop trace | Reranker degradation is visible per call | Given a `search_documents` call whose reranking fell back, when its trace entry is inspected, then its `degraded` flag is true | unit test: `tests/test_agentic_loop.py::test_trace_marks_reranker_degraded` | - [ ] |
| 25 | agentic-retrieval | Feature flag and flag-off equivalence | Flag off reproduces current behaviour | Given `chat_agentic_retrieval = false`, when a turn runs, then `sql_retrieval` and `retrieval` execute in parallel, no planner call is made, and `test_langgraph_parity.py`, `test_chat_api_rag.py`, `test_chat_api_guardrails.py` pass unmodified | regression run: `tests/test_langgraph_parity.py`, `tests/test_chat_api_rag.py`, `tests/test_chat_api_guardrails.py` unmodified + `tests/test_agentic_graph_topology.py::test_flag_off_no_planner_call` | - [ ] |
| 26 | agentic-retrieval | Feature flag and flag-off equivalence | Loop flag is inert on the legacy path | Given `chat_use_graph = false` and `chat_agentic_retrieval = true`, when a turn runs, then `_execute_legacy` runs unchanged and no planner call is made | unit test: `tests/test_agentic_loop.py::test_loop_flag_inert_on_legacy_path` | - [ ] |
| 27 | agentic-retrieval | Loop is measured against the one-shot configuration | Agentic configuration appears in the eval report | Given an eval run including the agentic configuration, when the report is produced, then it carries `recall@5` and `nDCG@5` for the agentic configuration alongside one-shot configurations, ranked by `nDCG@5` | unit test: `tests/test_retrieval_eval_runner.py::test_agentic_config_in_report` | - [ ] |
| 28 | agentic-retrieval | Loop is measured against the one-shot configuration | Loop failures during eval do not abort the run | Given an eval run where one query's loop errors, when the run completes, then remaining queries are still scored and the failed query is recorded with its error | unit test: `tests/test_retrieval_eval_runner.py::test_loop_error_does_not_abort_run` | - [ ] |
| 29 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Blocked question short-circuits to END | Given a `content_generation`-blocked message, when the graph runs, then guardrail routes to END with the existing decline string and no retrieval, SQL, NER, agentic, or LLM call is made | unit test: `tests/test_chat_api_guardrails.py` (blocked-type short-circuit, unmodified) | - [ ] |
| 30 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Excess complexity short-circuits to END when the loop is disabled | Given the loop disabled and complexity above 3, when the graph runs, then it routes to END with the existing "requires multiple lookups" reply and no retrieval, SQL, NER, or LLM call is made | unit test: `tests/test_chat_api_guardrails.py` (complexity decline, flag off, unmodified) | - [ ] |
| 31 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Flag-off topology is unchanged | Given the loop disabled, when the graph is compiled, then its nodes and edges are identical to the pre-change topology and the agentic node is unreachable | unit test: `tests/test_agentic_graph_topology.py::test_flag_off_topology_identical` | - [ ] |
| 32 | chat-orchestration-graph | Fixed topology with no agentic behaviour | Graph remains acyclic with the loop enabled | Given the loop enabled, when the graph is compiled and inspected, then it contains no cycle and only the agentic node can invoke tools repeatedly | unit test: `tests/test_agentic_graph_topology.py::test_graph_acyclic_with_flag_on` | - [ ] |
| 33 | chat-orchestration-graph | Retrieval and model components are orchestrated, not replaced | No LangChain model, retriever, or agent wrappers are imported | Given the `src/chat_api/` tree, when imports are inspected, then none of the named LangChain/prebuilt modules are imported and only `langgraph` / `langchain_core` type imports were added | static test: `tests/test_agentic_graph_topology.py::test_no_langchain_agent_imports` | - [ ] |
| 34 | chat-orchestration-graph | Retrieval and model components are orchestrated, not replaced | Retrieval stack is untouched | Given the implemented codebase, when `chunking.py`, `retriever.py`, and `models.py` are diffed against the pre-change revision, then no retrieval, ranking, or fusion behaviour has changed | code review: diff of `src/shared/retrieval/chunking.py`, `retriever.py`, `models.py` against pre-change revision | - [ ] |
| 35 | chat-orchestration-graph | Retrieval and model components are orchestrated, not replaced | Planner uses the existing client | Given an Azure-configured deployment, when the agentic node makes a planner call, then it is issued through the orchestrator's existing `AsyncAzureOpenAI` client | unit test: `tests/test_agentic_loop.py::test_planner_uses_existing_azure_client` | - [ ] |
| 36 | chat-api | Guardrail — query complexity limits | Overly complex question is simplified when the loop is disabled | Given the loop disabled and a 4-lookup question, when the complexity guardrail evaluates it, then the response asks the user to simplify and the complexity score is logged | unit test: `tests/test_chat_api_guardrails.py::test_complex_question_declined_flag_off` | - [ ] |
| 37 | chat-api | Guardrail — query complexity limits | Overly complex question is answered when the loop is enabled | Given the loop enabled and a 4-lookup question, when the guardrail evaluates it, then the turn proceeds into the loop, the response is 200 with reply and citations, the score is logged, and the raised iteration budget is used | unit test: `tests/test_chat_api_guardrails.py::test_complex_question_answered_flag_on` | - [ ] |
| 38 | chat-api | Guardrail — query complexity limits | Blocked question type is still declined with the loop enabled | Given the loop enabled and a blocked-type message, when the guardrail evaluates it, then the existing decline message is returned, `sources` is empty, and no planner or retrieval call is made | unit test: `tests/test_chat_api_guardrails.py::test_blocked_type_declined_flag_on` | - [ ] |
| 39 | retrieval-tools | Tool results render into bounded LLM observations | Chunk results render with follow-up identity | Given a `search_documents` `ToolResult` with two results, when rendered, then the observation names each `document_id`, `chunk_index`, and score, and includes the chunk text | unit test: `tests/test_retrieval_tools.py::test_observation_includes_identity` | - [ ] |
| 40 | retrieval-tools | Tool results render into bounded LLM observations | Error result renders as an error observation | Given a `ToolResult` with `error` set and empty results, when rendered, then the observation states the call failed and carries the error text | unit test: `tests/test_retrieval_tools.py::test_error_result_renders_error_observation` | - [ ] |
| 41 | retrieval-tools | Tool results render into bounded LLM observations | Rendering respects the character limit and preserves results | Given a `ToolResult` whose rendered form exceeds the limit, when rendered with that limit, then the observation does not exceed the limit and `ToolResult.results` still holds every original item | unit test: `tests/test_retrieval_tools.py::test_observation_limit_preserves_results` | - [ ] |
| 42 | retrieval-tools | Tool context carries remaining execution budget | Expired deadline denies the call before any I/O | Given a `ToolContext` with a passed deadline and a spy retriever, when `search_documents.call` runs, then the spy is never invoked and the `ToolResult` carries a budget-exhausted error | unit test: `tests/test_retrieval_tools.py::test_expired_deadline_denies_before_io` | - [ ] |
| 43 | retrieval-tools | Tool context carries remaining execution budget | Absent deadline preserves existing behaviour | Given a `ToolContext` without a deadline, when any registered tool is called, then it executes as before and existing tool tests pass unmodified | regression run: `tests/test_retrieval_tools.py` unmodified (no-deadline context) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Loop-as-graph-cycle (design Decision 1) | Implementing the loop as `planner`/`tools` graph nodes with a conditional back-edge, leaking budget and message bookkeeping into `ChatState` and breaking the acyclic guarantee | Inspect `builder.py` — confirm no edge returns to an earlier node; confirm `ChatState` gained only `tool_trace`, `agentic_degraded`, `agentic_stop_reason`; confirm the cycle lives inside `agentic.py` |
| 2 | Deadline enforcement (design Decision 2) | Implementing only iteration and tool-call caps, or checking the deadline once at loop entry rather than before each planner call and each tool dispatch — the wall-clock bound silently does not exist | Read the loop body for two deadline checks per cycle; run the deadline test (row 6) and confirm it fails when either check is removed |
| 3 | Evidence accumulation into existing keys (design Decision 3) | Inventing a new `evidence` state key, or changing `source_assembly` / citation logic to consume a richer structure, expanding the change into the user-visible citation path | Diff `source_assembly_node`, `prompt_assembly_node`, `ner_enrichment_node` — they must be byte-unchanged; confirm the loop writes `chunks` and `sql_results` |
| 4 | Dedup and error semantics (rows 9, 12, 13) | Deduplicating on `document_id` alone, keeping the first score instead of the highest, or setting `retrieval_error` when any single call errors rather than when all do | Read the accumulator; verify the dedup key is the `(document_id, chunk_index)` pair and the score reducer is `max`; run rows 9, 12, 13 |
| 5 | Tenant isolation under planner control (design Decision 4, ADR-001) | Adding `schema`, `tenant_id`, or `document scope` to an `args_schema` "so the planner can be more precise", or building `ToolContext` from planner output instead of `ChatState` | Grep every `args_schema` for the forbidden keys; confirm `assert_no_tenancy_params` still runs at registration; confirm `ToolContext(...)` is constructed only from `ChatState` values; run rows 14–16 |
| 6 | Fallback path (design Decision 5, rows 20–22) | Implementing the happy path only — raising on planner error, or marking degraded without actually running the one-shot nodes, so a broken loop silently produces answerless turns | Force a planner exception in a test and assert the reply equals the loop-disabled reply for the same inputs; confirm `agentic_degraded` appears in both state and the log record |
| 7 | Complexity guardrail gating (design Decision 6) | Removing the "please simplify" decline unconditionally rather than only when the flag is on, breaking flag-off equivalence and existing guardrail tests | Run `tests/test_chat_api_guardrails.py` unmodified with the flag off; read `guardrail_node` for the flag check; run rows 36–37 |
| 8 | Observation rendering (retrieval-tools spec) | Truncating `ToolResult.results` itself rather than only the rendered string, silently discarding retrieved evidence before it reaches accumulation | Run row 41 and assert `len(result.results)` is unchanged after rendering |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant PostgreSQL schemas, `search_path` enforcement | Tenant scope lives only in `ToolContext` built from authenticated request state; no planner-supplied argument may influence schema selection | Grep all `args_schema` blocks for `schema`/`tenant_id`/`tenant`/`purpose` — expect none; run the two-schema isolation test and the hostile-chunk test (rows 14–16) |
| ADR-003 Per-Tenant Model Serving Topology | Shared serving pool, tenant-aware routing | Every retrieval call in the loop is another reranker HTTP hop; degradation must stay visible per call and budgets must be wall-clock | Confirm each trace entry carries `degraded`; run row 24; confirm the deadline check precedes each dispatch |
| ADR-004 OpenSpec SDD Governance | Proposal → design → spec → tasks → evidence gates | Enabling the flag requires eval evidence, not argument; the loop trace must be durable enough to serve as evidence | Confirm the eval report contains the agentic configuration (row 27) and that the recorded comparison against the best one-shot configuration is logged in Section 5 before the flag is enabled anywhere |
| ADR-005 OpenCode Agent Permissions and Boundaries | Agent permission boundaries for repo automation | `src/shared` must not import `src.chat_api` | Run the existing import-isolation test over `src/shared/retrieval/tools/` after the `ToolContext` and rendering changes |
| ADR-006 Training Infrastructure with Asynchronous GPU Workers | Async GPU training workers | Training path untouched | Confirm no file under `src/training/` or the worker tree is modified in the diff |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, SQL validation layer, citation enforcement, P95 < 10s | The loop feeds the same `chunks`/`sql_results` keys (not a fourth source); `search_entities` keeps routing through the validated SQL path; budgets must leave generation inside 10s | Confirm `search_entities` reaches `SQLGenerator.generate_and_execute` via `ToolContext.sql_search`; confirm `enforce_sources` still runs after the loop; record a measured P95 with the flag on in Section 5 |
| ADR-008 Base Model as Default Inference Model | Base model answers when no tenant model is promoted | NER enrichment unchanged | Confirm `ner_enrichment_node` is unmodified in the diff |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Rows 1–3 (loop mechanics): test output showing the follow-up-search, registry-schema, and no-agent-framework/acyclic tests pass
- [x] Rows 4–6 (budgets): test output showing iteration-cap, tool-call-cap, and deadline tests pass with the recorded stop reason for each
- [x] Row 7 (exhaustion is not an error): test output showing a budget-exhausted turn returns a 200 reply with citations
- [x] Row 8 (planner-signalled stop): test output showing the loop exits on a no-tool-call message and the reply comes from the generation node
- [x] Rows 9–10 (dedup and ranking): test output showing the merged score is `max` and the list is score-descending
- [x] Row 11 (citations unchanged): test output or API trace comparing loop-turn citations against a one-shot turn with identical evidence
- [x] Rows 12–13 (error semantics): test output for partial-failure and total-failure cases
- [x] Rows 14–16 (tenant isolation): test output for the rejected `schema` argument, the two-schema isolation run, and the `purpose='training'` exclusion
- [x] Rows 17–18 (observation handling): test output for the hostile-chunk turn and the truncation bound
- [x] Rows 19–20 (malformed calls): test output for self-correction and for the two-consecutive-invalid degrade path
- [x] Rows 21–22 (fallback): test output showing planner-error fallback matches the loop-disabled reply, plus the log excerpt carrying `agentic_degraded` and the stop reason
- [x] Rows 23–24 (trace): log excerpt showing one trace entry per tool call and a `degraded: true` entry for a reranker fallback
- [x] Rows 25–26 (flag): output of `test_langgraph_parity.py`, `test_chat_api_guardrails.py` unmodified with the flag off, plus the legacy-path inertness test. `test_chat_api_rag.py` has one pre-existing failure (`TestGuardrailEnforcement::test_chat_response_sources`, a disclaimer-wording assertion) confirmed present on `main` before this change via `git stash` — unrelated to this change and not caused by it.
- [x] Rows 27–28 (eval): the generated eval report showing the agentic configuration ranked against one-shot configurations, and a run in which one query errored without aborting
- [x] Rows 29–32 (topology): test output for both early exits, the flag-off topology comparison, and the acyclic assertion with the flag on
- [x] Rows 33–35 (no framework substitution): import-inspection test output, the retrieval-stack diff, and evidence the planner call used the existing Azure client
- [x] Rows 36–38 (complexity guardrail): test output for the decline with the flag off, the answered turn with the flag on, and the still-declined blocked type
- [x] Rows 39–41 (observation rendering): test output for identity fields, error rendering, and the limit-with-results-preserved case
- [x] Rows 42–43 (context budget): test output for the expired-deadline denial and the no-deadline regression run
- [ ] Measured P95 latency for a realistic question set with the flag on, against the ADR-007 < 10s target — **not collected this session**: requires live Azure OpenAI credentials, a running `model_serving` reranker, and a realistic question set, none available in this environment. Blocks tasks.md 8.1–8.3.

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations) — **requires human reviewer**; see Section 2 note on the one documented deviation (loop core module location).
- [ ] All ADR compliance steps in Section 3 confirmed ✓ — automatable checks (grep, import isolation, diff) run and recorded below; final sign-off is a human step.
- [ ] No undocumented architectural patterns introduced — human judgment call.
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files) — human judgment call.

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — graph inspected via `TestGraphAcyclicWithFlagOn`/`TestFlagOffTopologyUnchanged`; no cycle; `ChatState` additions limited to `tool_trace`, `agentic_degraded`, `agentic_stop_reason`.
- [x] Risk 2 mitigation confirmed — both deadline checks (before each planner call, before each tool dispatch) verified live: removed the inner per-tool-dispatch check, added `tests/test_agentic_loop.py::TestBudgets::test_deadline_stops_mid_iteration_before_second_call` (a single planner turn requesting two tool calls where the first exceeds the deadline), confirmed it fails without the inner check (`assert second_tool.calls == []` → `[{'query': 'b', 'document_id': 'D1'}]`), then restored the check and confirmed the full suite (19/19) passes again.
- [x] Risk 3 mitigation confirmed — `ner_enrichment_node`, `source_assembly_node`, `prompt_assembly_node`, `generation_node` in `src/chat_api/graph/nodes.py` are byte-unchanged by this session's diff (only `guardrail_node`'s complexity branch changed, and `agentic_retrieval_node` was added).
- [x] Risk 4 mitigation confirmed — dedup key is `(document_id, chunk_index)`, reducer is `max` on `similarity_score` (`src/shared/retrieval/agentic_loop.py::_Accumulator.add`); verified by rows 9, 12, 13.
- [x] Risk 5 mitigation confirmed — no `args_schema` in `src/shared/retrieval/tools/` declares `schema`/`tenant_id`/`tenant`/`purpose`; `assert_no_tenancy_params` still runs at `ToolRegistry.register`; `ToolContext` in `agentic_retrieval_node` is built only from `ChatState` fields, never from planner output.
- [x] Risk 6 mitigation confirmed — `tests/test_agentic_node_integration.py::TestNodeLevelFallback` forces a planner exception and asserts the fallback's `chunks`/`sql_results`/`retrieval_error`/`sql_error` equal the one-shot nodes' direct output for identical state; `agentic_degraded`/`agentic_stop_reason` present in both the returned state and the log record.
- [x] Risk 7 mitigation confirmed — `tests/test_chat_api_guardrails.py` passes unmodified with the flag off (default); `tests/test_agentic_graph_topology.py::TestComplexityGuardrailFlagAware` covers both flag states explicitly.
- [x] Risk 8 mitigation confirmed — `tests/test_retrieval_tools.py::TestObservationRendering::test_observation_limit_preserves_results` asserts `len(result.results) == 50` unchanged after rendering at a 200-char limit.

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_agentic_loop.py -q` → 19 passed (loop core: mechanics, budgets, accumulation, malformed calls, planner failure, trace, observation bounds) | Rows 1–10, 12–13, 17–24 | claude-opus-5 (agent) | 2026-07-28 |
| 2 | Functional | `pytest tests/test_agentic_node_integration.py -q` → 3 passed (citation parity via `source_assembly_node`; node-level fallback matches one-shot output exactly; fallback log record) | Rows 11, 21, 22 | claude-opus-5 (agent) | 2026-07-28 |
| 3 | Functional | `pytest tests/test_agentic_loop_integration.py -q` → 4 passed against real seeded Postgres schemas (schema-arg rejection, cross-schema isolation with a hostile chunk, `purpose='training'` exclusion, `search_entities` → `sql_search` routing) | Rows 14–16, ADR-007 SQL-path check | claude-opus-5 (agent) | 2026-07-28 |
| 4 | Functional | `pytest tests/test_agentic_graph_topology.py -q` → 11 passed (no LangChain/prebuilt imports, acyclic compiled graph with flag on, flag-off node set unchanged, no planner call with flag off, legacy-path inertness, planner uses orchestrator's client, early exits, flag-aware complexity guardrail) | Rows 3, 25, 26, 29–38 | claude-opus-5 (agent) | 2026-07-28 |
| 5 | Functional | `pytest tests/test_retrieval_tools.py -q` → 23 passed, including `TestObservationRendering` and `TestToolContextBudget` | Rows 39–43 | claude-opus-5 (agent) | 2026-07-28 |
| 6 | Functional | `pytest tests/test_retrieval_eval_runner.py -q` → 11 passed, including `TestAgenticConfigurationInReport` and `TestAgenticQueryErrorDoesNotAbortRun` | Rows 27–28 | claude-opus-5 (agent) | 2026-07-28 |
| 7 | Functional (regression) | `pytest tests/test_langgraph_parity.py tests/test_chat_api_guardrails.py tests/test_hybrid_retrieval.py tests/test_reranking_retriever.py -q` → all pass unmodified, flag off by default | Row 25 (partial — see note below) | claude-opus-5 (agent) | 2026-07-28 |
| 8 | Edge Case | Mutation test for Risk 2: removed the inner per-tool-dispatch deadline check in `src/shared/retrieval/agentic_loop.py`, ran `test_deadline_stops_mid_iteration_before_second_call`, observed it fail (`assert second_tool.calls == []` failed with one call recorded), reverted, confirmed `tests/test_agentic_loop.py` 19/19 pass again | Risk 2 (Hallucination Risk Register) | claude-opus-5 (agent) | 2026-07-28 |
| 9 | Note | `tests/test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources` fails on unmodified `main` (verified via `git stash` + rerun) — a disclaimer-wording assertion drift unrelated to `src/chat_api/api/v1/schemas.py`'s prior (pre-session) edit. Not caused by this change; flagged for separate follow-up, not fixed here (out of scope). | Row 25 caveat | claude-opus-5 (agent) | 2026-07-28 |
| 10 | Note | Full-repo `pytest tests/` (minus a pre-existing, unrelated syntax-error collection failure in `test_analytics_dashboard.py`) surfaces unrelated failures in `test_user_auth.py`, `test_tenant_schema_migrations.py`, `test_verify_schema.py`, etc. Confirmed pre-existing and reproducible on unmodified `main` via `git stash` (same `test_user_auth.py` failures, same error signatures). Also observed transient FK-teardown failures (`audit_events` referencing `tenants`) from cross-test DB state pollution during bulk runs, resolved by `TRUNCATE audit_events` + `scripts/setup_test_db.py`; reproduces on unmodified `main` too. None of this is caused by or specific to this change. | N/A — full-suite baseline note | claude-opus-5 (agent) | 2026-07-28 |
| 11 | Structural | `git diff --stat -- src/shared/retrieval/chunking.py src/shared/retrieval/retriever.py src/shared/retrieval/models.py` — no changes to `chunking.py`/`models.py`; the `retriever.py` diff (config-override plumbing) predates this session (from `retrieval-tools-and-eval`), confirmed via `tests/test_hybrid_retrieval.py`/`tests/test_reranking_retriever.py` passing unmodified | Row 34 | claude-opus-5 (agent) | 2026-07-28 |
| 12 | Structural | `openspec validate agentic-retrieval-loop --type change --strict` → "Change 'agentic-retrieval-loop' is valid" | tasks.md 9.6 | claude-opus-5 (agent) | 2026-07-28 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** agentic-retrieval-loop
**Proposal:** `openspec/changes/agentic-retrieval-loop/proposal.md`
**Spec files reviewed:**
  - specs/agentic-retrieval/spec.md
  - specs/chat-orchestration-graph/spec.md
  - specs/chat-api/spec.md
  - specs/retrieval-tools/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
