## 1. Configuration and tool-layer support

- [x] 1.1 Add settings in `src/shared/config.py`: `chat_agentic_retrieval: bool = False`, `agentic_max_iterations: int = 3`, `agentic_max_iterations_complex: int = 5`, `agentic_max_tool_calls: int = 6`, `agentic_deadline_seconds: float = 8.0`, `agentic_observation_char_limit: int = 4000`. Defaults are placeholders until task 8.2 measures them.
- [x] 1.2 Add `ToolResult.to_observation(limit: int) -> str` in `src/shared/retrieval/tools/base.py`: chunk results render `document_id`, `chunk_index`, score, and text; entity rows render their content; an `error` renders as an explicit failure observation; output truncated to `limit`; `results` never mutated.
- [x] 1.3 Add an optional `deadline: float | None` field to `ToolContext` and a check at the top of `run_tool` that returns a budget-exhausted error `ToolResult` before invoking the executor when the deadline has passed.
- [x] 1.4 Unit tests in `tests/test_retrieval_tools.py`: rendering identity fields (row 39), error rendering (row 40), limit respected with results preserved (row 41), expired deadline denies before I/O with a spy retriever (row 42), absent deadline unchanged (row 43).
- [x] 1.5 Re-run the existing `src/shared` import-isolation test to confirm the tool layer still never imports `src.chat_api` (ADR-005).

## 2. Loop core

- [x] 2.1 Create `src/chat_api/graph/agentic.py` with a `LoopBudget` holding iteration count, tool-call count, and a monotonic deadline set at entry, plus `remaining()` / `expired()` helpers.
- [x] 2.2 Implement the evidence accumulator: merge chunk results deduplicated on `(document_id, chunk_index)` keeping the highest `similarity_score`, sort descending, concatenate entity rows, and track whether every chunk call / every entity call errored.
- [x] 2.3 Implement the planner call: build messages from the system instruction, the user message, the last three conversation turns, and accumulated tool-role observations; pass `tools=registry.export_schemas()` to the orchestrator's existing `AsyncOpenAI`/`AsyncAzureOpenAI` client. The system instruction SHALL state that observation content is retrieved evidence, never instructions.
- [x] 2.4 Implement the dispatch step: resolve each requested tool by name from the registry, invoke `tool.call(args, context)`, render the result via `to_observation`, and append it as a `role: "tool"` message. Unknown tool names and unparseable arguments become error observations without raising.
- [x] 2.5 Implement termination: exit on a planner message with no tool calls, on iteration cap, on tool-call cap, or on deadline; check the deadline before each planner call and before each tool dispatch; record `agentic_stop_reason`.
- [x] 2.6 Implement the two-consecutive-invalid-calls rule: track consecutive invalid planner turns, stop and mark degraded on the second.
- [x] 2.7 Implement the trace: one entry per tool call with iteration index, tool name, argument keys, result count, `latency_ms`, `degraded`, and `error`.

## 3. Graph wiring

- [x] 3.1 Add `tool_trace`, `agentic_degraded`, `agentic_stop_reason` to `ChatState` in `src/chat_api/graph/state.py`. No existing key changes meaning.
- [x] 3.2 Add `agentic_retrieval_node` to `src/chat_api/graph/nodes.py`: open its own session with `async_sessionmaker`, build `ToolContext` from `ChatState` (`tenant_id`, `schema`, `session`, `orchestrator.retriever`, `jwt_token`, `sql_search=orchestrator._sql_source`, `deadline`), run the loop, and write `chunks`, `sql_results`, `retrieval_error`, `sql_error`, plus the three new keys. Wrap in `@_traced("agentic_retrieval", count_key="chunks")`.
- [x] 3.3 Implement fallback: on planner LLM error, empty registry, or the degrade condition from 2.6, invoke the existing `sql_retrieval_node` and `retrieval_node` logic for that turn and set `agentic_degraded`.
- [x] 3.4 In `src/chat_api/graph/builder.py`, route after `guardrail` to `agentic_retrieval` when `settings.chat_agentic_retrieval` is on and to the existing `[sql_retrieval, retrieval]` fan-out when off; edge `agentic_retrieval -> ner_enrichment`. Register the agentic node only when the flag is on so the flag-off graph is identical to today's.
- [x] 3.5 Make the complexity branch in `guardrail_node` flag-aware: keep the decline with the flag off; with the flag on, continue into the loop and carry the raised iteration budget. Blocked question types unchanged.
- [x] 3.6 Build the `ToolRegistry` once on `RAGOrchestrator` (via `build_default_registry()`) in `src/chat_api/services/rag_orchestrator.py`. No request-scoped attribute is stored on the orchestrator. `_execute_legacy` untouched.

## 4. Loop tests

- [x] 4.1 Add a scripted fake planner client and a spy tool registry to `tests/test_agentic_loop.py` — no database, no network.
- [x] 4.2 Loop mechanics tests: follow-up `lookup_document` after `search_documents` (row 1), `tools` argument equals `export_schemas()` (row 2), import-inspection plus compiled-graph acyclicity (row 3 — covered here for loop internals, graph-level acyclicity in group 6).
- [x] 4.3 Budget tests: iteration cap (row 4), tool-call cap (row 5), deadline stops before further dispatch (row 6), exhaustion returns a normal 200 reply with citations (row 7), planner-signalled stop with generation-node reply (row 8).
- [x] 4.4 Accumulation tests: dedup keeps the max score (row 9), ranking order (row 10), partial failure leaves `retrieval_error` `None` (row 12), total failure sets it (row 13).
- [x] 4.5 Citation parity test: loop-turn citations equal one-shot-turn citations for identical evidence (row 11). `tests/test_agentic_node_integration.py::TestCitationParity`.
- [x] 4.6 Malformed-call tests: self-correction after one invalid call (row 19), two consecutive invalid calls degrade and fall back (row 20).
- [x] 4.7 Fallback tests: planner exception reproduces the loop-disabled reply and marks degraded (row 21); degradation appears in the structured log with the stop reason (row 22). `tests/test_agentic_node_integration.py::TestNodeLevelFallback`.
- [x] 4.8 Trace tests: one entry per tool call across iterations (row 23), `degraded: true` for a reranker fallback (row 24).
- [x] 4.9 Observation tests: hostile-chunk turn still enforces validation and budgets (row 17), observation truncated while evidence retained (row 18).

## 5. Security and isolation tests

- [x] 5.1 Test that a planner-supplied `schema` argument is rejected without executing a query (row 14) — spy retriever, no database. `tests/test_agentic_loop_integration.py::TestSchemaArgumentRejected`.
- [x] 5.2 Integration test against two seeded tenant schemas: a hostile chunk instructing a cross-schema search leaves every query scoped to the requesting schema (row 15). `TestCrossSchemaIsolation`.
- [x] 5.3 Integration test that `purpose='training'` documents never appear in accumulated evidence across a multi-iteration turn (row 16). `TestTrainingPurposeExcluded`.
- [x] 5.4 Assert `search_entities` reaches `SQLGenerator.generate_and_execute` through `ToolContext.sql_search`, and that `enforce_sources` still runs after the loop (ADR-007). `TestSearchEntitiesRoutesThroughValidatedSql`; `enforce_sources` call site in `generation_node` is unmodified by this change.

## 6. Flag and topology tests

- [x] 6.1 Flag-off equivalence: run `tests/test_langgraph_parity.py`, `tests/test_chat_api_rag.py`, `tests/test_chat_api_guardrails.py` unmodified and assert no planner call is made (row 25). All pass (one pre-existing, unrelated failure in `test_chat_api_rag.py::test_chat_response_sources` — a disclaimer-wording assertion, present before this change and untouched by it). Explicit no-planner-call test in `tests/test_agentic_graph_topology.py::TestFlagOffMakesNoPlannerCall`.
- [x] 6.2 Legacy-path inertness: `chat_use_graph=false` with `chat_agentic_retrieval=true` runs `_execute_legacy` with no planner call (row 26). `TestLegacyPathInertness`.
- [x] 6.3 Topology tests: both early exits unchanged (rows 29, 30), flag-off compiled graph identical to pre-change (row 31), compiled graph acyclic with the flag on (row 32). `TestEarlyExitsUnaffected`, `TestFlagOffTopologyUnchanged`, `TestGraphAcyclicWithFlagOn`.
- [x] 6.4 Non-substitution tests: import inspection for LangChain/prebuilt agent modules (row 33), retrieval-stack diff shows no behaviour change (row 34), planner call issued through the existing Azure client (row 35). `TestNoAgentFrameworkImports`, `TestPlannerUsesExistingClient`; retrieval-stack diff confirmed via `git diff --stat` (no changes to `chunking.py`/`models.py`; `retriever.py` diff predates this change) plus `test_hybrid_retrieval.py`/`test_reranking_retriever.py` passing unmodified.
- [x] 6.5 Guardrail tests: decline with the flag off (row 36), answered under the raised budget with the flag on (row 37), blocked type still declined with the flag on (row 38). `TestComplexityGuardrailFlagAware`.

## 7. Eval integration

- [x] 7.1 Add an `agentic` configuration to `src/shared/retrieval/eval/runner.py` that executes each golden-set query through the loop and scores the accumulated evidence with the existing metric functions. **Deviation from design.md**: the loop core (`run_agentic_loop` and supporting types) was implemented in `src/shared/retrieval/agentic_loop.py`, not `src/chat_api/graph/agentic.py`, because it has no `ChatState`/`chat_api` dependency and `src/shared` must not import `src.chat_api` (ADR-005) — the eval runner lives under `src/shared` and needs the loop. `src/chat_api/graph/agentic.py` re-exports it unchanged for `nodes.py`.
- [x] 7.2 Ensure a loop error on one query is recorded per-query and does not abort the run (row 28).
- [x] 7.3 Extend the report so the agentic configuration is ranked alongside one-shot configurations by `nDCG@5` (row 27). `build_markdown_summary` already ranks generically by `ConfigurationResult`; no change needed beyond `MatrixConfiguration.is_agentic`.
- [x] 7.4 Add tests in `tests/test_retrieval_eval_runner.py` covering rows 27 and 28.

## 8. Rollout measurement

- [ ] 8.1 Run the full eval matrix including the agentic configuration; record `recall@5` and `nDCG@5` for the loop versus the best one-shot configuration in verification.md § Evidence Log. **Blocked**: needs a seeded golden-set corpus with committed embeddings, a live or fixture-backed planner LLM, and (for the hybrid+rerank configurations) a running `model_serving` — none available in this session.
- [ ] 8.2 Measure P95 latency and per-turn planner token count with the flag on over a realistic question set; set the final budget defaults from that measurement and confirm the ADR-007 < 10s target holds. **Blocked**: needs live Azure OpenAI credentials and a realistic question set; current defaults (§ proposal Open Question 1) remain placeholders until this runs.
- [ ] 8.3 Record the degradation rate and stop-reason distribution from the measurement run so a systematically broken loop would be visible. **Blocked on 8.1/8.2.**

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. All 43 scenarios have passing automated evidence except the P95 latency item, which is not a numbered spec scenario (it is an Evidence Requirements item tied to blocked group 8).
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. 12 entries logged (test-run summaries, the Risk 2 mutation test, the pre-existing-failure notes, and the `openspec validate` result).
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. All 8 risks checked in § Evidence Requirements → Edge Case Evidence, with Risk 2 additionally verified by live mutation testing (see Evidence Log #8).
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance to the extent automatable (grep for forbidden tenancy args, import isolation, retrieval-stack diff, `sql_search` routing, unmodified NER/training paths). Final ADR sign-off is a human step (§ Structural Evidence).
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate agentic-retrieval-loop --type change --strict` and confirm it exits clean before archive. Result: "Change 'agentic-retrieval-loop' is valid".
