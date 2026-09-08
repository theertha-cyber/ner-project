## 1. Retrieval layer: one semantic capability with internal scope

- [x] 1.1 Widen `_metadata_filter_clause` in `src/shared/retrieval/retriever.py` to accept `{"document_ids": [...]}` and emit `AND document_id = ANY(:mf_document_ids)` with bound parameters; keep the single-id form working during the transition.
- [x] 1.2 Add `SemanticRetrievalTool` (`name = "semantic_retrieval"`) in `src/shared/retrieval/tools/document_tools.py` with `args_schema` `{query, top_k?, scope?}`, where `scope` is an object with `type` (`tenant` | `document`) and, for `document`, `document_ids: [string]`. Reject unknown `scope.type` and unknown scope keys via `validate_args` plus an explicit scope check.
- [x] 1.3 Translate `scope` to the retriever `metadata_filter` inside the capability; keep `top_k` clamping via `_clamp_top_k`; keep the `degraded_sink` wiring for `RerankingRetriever`.
- [x] 1.4 Delete `SearchDocumentsTool` and `LookupDocumentTool` and their module-level instances.
- [x] 1.5 Rename `SearchEntitiesTool.name` to `structured_retrieval` and rename the exported instance; leave arguments and `sql_search` delegation unchanged.
- [x] 1.6 Update `src/shared/retrieval/tools/__init__.py` exports and `build_default_registry` to register exactly `semantic_retrieval` and `structured_retrieval`.
- [x] 1.7 Review both capability descriptions so each states what information it retrieves, not how (verification rows 32–33).
- [x] 1.8 Rewrite `tests/test_retrieval_tools.py` for the new surface: default tenant scope, single-document scope, multi-document scope, unknown scope type rejected, `top_k` clamping, retriever failure returned as an error result, registry exposing exactly two names (verification rows 26–33). — 30 passed
- [x] 1.9 Update `tests/test_retrieval_tools_integration.py` to exercise multi-document scope against a real schema and assert bound-parameter usage (verification row 28). — 7 passed
- [ ] 1.10 Grep `src/` and `tests/` for `search_documents`, `lookup_document`, `search_entities`; confirm no live references remain (verification rows 34–35). — deferred until agentic_loop.py (group 4) and eval runner (group 7) are updated; remaining hits confirmed confined to those two files

## 2. Orchestrator core in `src/shared/retrieval/orchestrator.py`

- [x] 2.1 Create `src/shared/retrieval/orchestrator.py` with no `src.chat_api` imports (ADR-005). Define `PlanEntry`, `RetrievalPlan`, `OrchestrationResult`, and `OrchestrationBudget` dataclasses.
- [x] 2.2 Write the orchestration system prompt describing the two capabilities and the platform domain; keep it in this module as a named constant.
- [x] 2.3 Implement `plan_retrieval(message, conversation_context, llm_client, llm_model, registry) -> RetrievalPlan`: one LLM call with `tools=registry.export_schemas()`, `tool_choice="auto"`, temperature 0; map returned `tool_calls` to plan entries; never send retrieval results back (verification rows 2, 8).
- [x] 2.4 Validate each entry at plan time: unknown capability name, unparseable JSON arguments, or `args_schema` failure marks the entry rejected with a reason; rejection never aborts sibling entries (verification rows 12–13, 17).
- [x] 2.5 Implement `execute_plan(plan, context, budget)`: truncate to `max_invocations`, check the deadline before each dispatch, run surviving entries concurrently with `asyncio.gather`, each entry using its **own** `AsyncSession` supplied by the caller's session factory (verification rows 9–10; risk 1). — `context_factory` is an async context manager per entry, guaranteeing session close.
- [x] 2.6 Implement accumulation: dedupe chunks on `(document_id, chunk_index)` keeping the highest `similarity_score`, sort descending, concatenate entity rows, and set `retrieval_error` / `sql_error` only on total failure of their respective entry class (verification rows 20–23).
- [x] 2.7 Implement the degraded fallback: on planning exception or an empty/all-rejected plan, execute `semantic_retrieval` (tenant scope) and `structured_retrieval` on the raw query, mark degraded, record a distinguishing stop reason, and log a structured record (verification rows 14–16).
- [x] 2.8 Build the plan trace: per-entry capability name, argument keys, executed-or-rejected with reason, result count, latency ms, `degraded` flag; plus plan-level stop reason, truncation flag, and degraded flag. No `iteration` key (verification rows 24–25; risk 7).
- [x] 2.9 Add `tests/test_retrieval_orchestrator.py` with a scripted planner client covering: single-capability plan, both-capabilities plan, multi-entry same-capability plan, exactly-one-planning-call assertion, invocation-cap truncation, deadline halt, unknown-capability rejection alongside a valid sibling, schema-argument rejection, planner-raises fallback, empty-plan fallback, accumulation semantics, and trace shape (verification rows 5–16, 20–25). — 20 passed
- [x] 2.10 Add an integration test executing a two-entry plan concurrently against a real database, asserting both entries return and no `IllegalStateChangeError` occurs (verification row 6; risk 1). — 3 passed (also covers rows 18–19)

## 3. Guardrail as a domain filter

- [x] 3.1 Delete `assess_complexity`, `MAX_COMPLEXITY_SCORE`, and the `classification` / `content_generation` / `summarization` entries of `BLOCKED_PATTERNS` from `src/chat_api/services/guardrails.py` (verification row 55).
- [x] 3.2 Keep the deterministic short-circuits: cross-tenant schema reference and PII request; both decline without an LLM call (verification row 44).
- [x] 3.3 Add `classify_domain(message, conversation_context, llm_client, llm_model)` with a fixed system prompt describing the supported domain and labelled in-domain / out-of-domain examples, including edge cases such as "summarise the findings in this contract" (in-domain).
- [x] 3.4 Fail open: any exception from the classifier logs and admits the query (verification row 45; risk 3).
- [x] 3.5 Add the domain decline message as `DOMAIN_DECLINE_REPLY`. `enforce_sources` needs no special-casing — declines never reach it (short-circuit before `generation_node`, verified at graph level in task 4.8) (verification rows 47–48).
- [x] 3.6 Rewrite `tests/test_chat_api_guardrails.py`: the three named out-of-domain prompts decline with no retrieval, an in-domain query is admitted, the cross-tenant short-circuit makes no classifier call, classifier failure fails open, and a multi-lookup question is no longer refused (verification rows 41–46). — 14 passed (full decline/no-retrieval + multi-lookup HTTP-level assertions in tests/test_chat_api_rag.py, group 6)

## 4. Graph rewiring

- [x] 4.1 Update `ChatState` in `src/chat_api/graph/state.py`: remove `complexity`, `ner_entities`, `tool_trace`, `agentic_degraded`, `agentic_stop_reason`; add `retrieval_plan`, `plan_trace`, `orchestration_degraded`, `orchestration_stop_reason`. Leave `chunks`, `sql_results`, `retrieval_error`, `sql_error`, `sources`, `document_names`, `prompt_messages`, `reply` unchanged.
- [x] 4.2 Rewrite `guardrail_node` to call the domain classifier and return a decline (with empty `sources`) or admit (verification rows 41–46).
- [x] 4.3 Add `orchestrator_node`: build `ToolContext` from `ChatState` (tenant/schema from authenticated state only), call `plan_retrieval`, write `retrieval_plan` to state (verification rows 1–2, 17–18). — split so the plan (or its degraded-fallback substitute) is visible in state before execution.
- [x] 4.4 Add `retrieval_execution_node`: call `execute_plan` with a session factory, write `chunks`, `sql_results`, `retrieval_error`, `sql_error`, `plan_trace`, `orchestration_degraded`, `orchestration_stop_reason`.
- [x] 4.5 Delete `sql_retrieval_node`, `retrieval_node`, `agentic_retrieval_node`, `ner_enrichment_node` from `src/chat_api/graph/nodes.py`.
- [x] 4.6 Rewrite `build_chat_graph` to a fixed topology with exactly one conditional edge (guardrail decline to END): `guardrail → orchestrator → retrieval_execution → source_assembly → prompt_assembly → generation → END`. Remove the `agentic_enabled` branch and any build-time parameters that select topology (verification rows 3–4; risk 6).
- [x] 4.7 Delete `src/chat_api/graph/agentic.py` and `src/shared/retrieval/agentic_loop.py`; delete `tests/test_agentic_loop.py` and `tests/test_agentic_loop_integration.py` (verification row 61). — also deleted `tests/test_agentic_graph_topology.py` and `tests/test_agentic_node_integration.py` (flag-topology tests with no surviving subject) and `tests/test_langgraph_parity.py` (existed solely to compare the now-removed legacy vs. graph paths, per task 6.6).
- [x] 4.8 Add graph tests asserting the compiled topology, single conditional edge, acyclicity, absence of the removed LangChain imports, and that a declined query invokes neither the orchestrator nor any retrieval capability (verification rows 1, 3, 4, 41). — see `tests/test_chat_graph_topology.py` (group 9 test-writing pass).

## 5. Remove retrieval-time NER

- [x] 5.1 Strip `ner_entities` construction and `source_type="ner"` sources from `source_assembly_node`; keep SQL and chunk source assembly and citation enrichment unchanged (verification row 38).
- [x] 5.2 Remove the `ner_entities` parameter, the NER context block, and its token accounting from `ContextAssembler.assemble`; update all call sites (verification row 54; risk 4).
- [x] 5.3 Remove `self.ner_client` from `RAGOrchestrator.__init__`; delete `src/chat_api/services/ner_client.py` only after confirming no consumer outside chat (design Open Questions). — grepped repo-wide; only `tests/test_chat_api_reranking.py` referenced it (test double), now updated. Deleted.
- [x] 5.4 Keep `entity_type`, `value`, `confidence` on `Source` and `Citation` so stored historical messages still deserialise (risk 4). — unchanged, verified no removal needed.
- [x] 5.5 Update `tests/test_context_assembler.py` and any chat tests asserting NER sources; add an assertion that no response `sources` entry has `source_type == "ner"` (verification row 38). — `TestEmptySourceDegradation::test_no_ner_block_ever_rendered`; API-level assertion added in `tests/test_chat_api_rag.py` (group 9).
- [x] 5.6 Grep `src/` for `ner_entities`, `ner_client`, `source_type="ner"`; confirm only ingestion-path NER remains (verification row 54). — clean.

## 6. Remove the legacy path and feature flags

- [x] 6.1 Delete `RAGOrchestrator._execute_legacy` and `_vector_source`; make `execute` graph-only (verification row 62).
- [x] 6.2 Remove `chat_use_graph`, `chat_agentic_retrieval`, `agentic_max_iterations`, `agentic_max_iterations_complex`, `agentic_observation_char_limit` from `src/shared/config.py`.
- [x] 6.3 Add `orchestrator_max_invocations` (default 3); rename `agentic_deadline_seconds` to `retrieval_deadline_seconds` (default 8.0); keep `retrieval_top_k` as the `max_top_k` source.
- [ ] 6.4 Remove the retired env vars from compose files, `.env` examples, and deployment docs. — deferred: grep (task 6.5) found no `NER_CHAT_USE_GRAPH` / `NER_CHAT_AGENTIC_RETRIEVAL` / `NER_AGENTIC_*` references in `docker-compose.yml` or env examples; nothing to remove there. Confirm no deployment doc mentions them before archive.
- [x] 6.5 Grep `src/`, `tests/`, and compose/env files for `chat_use_graph`, `chat_agentic_retrieval`, `agentic_`; confirm hits exist only inside archived changes (verification rows 3, 62; risk 6).
- [x] 6.6 Update `tests/test_langgraph_parity.py` and `tests/test_chat_api_rag.py` for the single path, or delete the parity suite if it exists only to compare the removed paths. — deleted `test_langgraph_parity.py` (see 4.7); `test_chat_api_rag.py` NER-source assertion added in group 9.

## 7. Eval harness retarget

- [x] 7.1 Update `src/shared/retrieval/eval/runner.py` to invoke `semantic_retrieval` for baseline configurations (verification row 56).
- [x] 7.2 Replace the agentic configuration runner with an orchestrated configuration that calls `plan_retrieval` + `execute_plan` (via `orchestrate_retrieval`) and scores the accumulated evidence with the existing metric functions (verification rows 58–59).
- [x] 7.3 Update `MatrixConfiguration` in `src/shared/retrieval/eval/runner.py` (there is no separate `eval/config.py` — `MatrixConfiguration` lives in `runner.py`): replace `is_agentic`/`max_iterations`/`max_tool_calls`/`observation_char_limit` with `is_orchestrated`/`max_invocations` (verification row 60).
- [x] 7.4 Ensure per-query failures — capability errors and planning errors — are recorded rather than aborting the run (verification rows 57, 59).
- [x] 7.5 Update `tests/test_retrieval_eval_runner.py` for the renamed capability, the orchestrated configuration, and the configuration field set (verification rows 56–60). — 12 passed.
- [ ] 7.6 Regenerate the golden-set baseline report; record orchestrated vs. baseline `recall@5` and `nDCG@5`, and note the capability rename in the report metadata. — requires a live LLM credential and the golden-set fixture corpus; not run in this session. Flagged as outstanding functional evidence for verification.md § Evidence Requirements.

## 8. Downstream and cross-cutting

- [x] 8.1 Audit `src/portal/src/components/chat/CitationChips.tsx`, `CitationCard.tsx`, `MessageThread.tsx`, and other `source_type` references in the portal for `source_type === 'ner'` branches. Result: none of them branch on `source_type` at all — every field (`entity_type`, `entity_value`, `confidence`, `relevance_score`, `context_snippet`) renders generically regardless of source type, and `document_id`/label fallbacks are equally generic. No embeddable-widget-specific citation renderer exists outside these shared components. No code change needed; stored historical `ner` messages will continue to render exactly as before.
- [ ] 8.2 Record the superseding ADR for ADR-007 (live NER removed as a retrieval source; complexity limits replaced by orchestrator budgets; guardrail redefined as a domain filter; orchestration centralised). Preserve all other ADR-007 compliance items. — not yet drafted; required before archive per design.md Open Questions.
- [ ] 8.3 Measure P95 latency for a representative query set and compare against the pre-change flag-off path and the 10s ADR-007 target (verification: functional evidence, last item). — requires a live LLM credential and representative traffic; not run in this session.
- [x] 8.4 Confirm ADR-001 compliance: run `assert_no_tenancy_params` over the registry, and verify every `ToolContext` construction sources `tenant_id`/`schema` from authenticated request state (verification rows 17–19). — `ToolRegistry.register` calls `assert_no_tenancy_params` for every registration (enforced by `tests/test_retrieval_tools.py::TestNoTenancyParams`); `orchestrator_node`/`retrieval_execution_node` build `ToolContext` from `ChatState["tenant_id"]`/`["schema"]` only.
- [x] 8.5 Confirm ADR-005 compliance: grep `src/shared/` for `src.chat_api` imports — zero hits.

## 9. Verification & Evidence

- [ ] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. — 56 of 62 rows have passing automated tests written this session (see per-group notes for artifact names); rows 54–55, 61–62 (removal scenarios) are covered by grep audits plus green test runs rather than dedicated test functions. Rows depending on 7.6/8.2/8.3 (baseline regeneration, superseding ADR, P95 measurement) are NOT yet executed — outstanding.
- [ ] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. — not yet transcribed into the Evidence Log table; test output exists (this session's tool transcript) but the human-reviewer-facing log is still blank.
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. — risks 1–2 verified by dedicated tests (`test_orchestrator_integration.py`, `test_retrieval_tools_integration.py`); risks 3–7 verified by targeted unit tests and greps during groups 3–4; a human reviewer should still independently re-check per the gate's intent.
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance. — ADR-001, 003, 004, 005 verified this session (see tasks 8.4–8.5); ADR-007's superseding record (task 8.2) is outstanding, which blocks this row.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate redesign-retrieval-orchestration --type change --strict` and confirm it exits clean before archive. — "Change 'redesign-retrieval-orchestration' is valid".
