# Verification Plan

**Change:** redesign-retrieval-orchestration
**Generated:** 2026-07-30
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | retrieval-orchestration | Intent Orchestrator is the single retrieval routing layer | Orchestrator decides retrieval for every non-declined turn | Given a query that passes the guardrail, when the turn runs, then the orchestrator node executes exactly once before any retrieval, and the capabilities invoked are exactly those named in the plan | graph test: `tests/test_chat_graph_topology.py::test_orchestrator_runs_once_before_retrieval` | - [ ] |
| 2 | retrieval-orchestration | Intent Orchestrator is the single retrieval routing layer | Orchestrator receives the declared capabilities and conversation history | Given a registry of two capabilities and a conversation with prior turns, when the planning call is made, then its `tools` argument equals `ToolRegistry.export_schemas()` and its messages contain the orchestration prompt, the recent turns, and the current query | unit test: `tests/test_retrieval_orchestrator.py::test_planner_inputs` | - [ ] |
| 3 | retrieval-orchestration | Intent Orchestrator is the single retrieval routing layer | No feature flag governs routing | Given the settings model, when inspected, then no setting selects between retrieval strategies or graph topologies, and the compiled graph has a single topology | unit test: `tests/test_chat_graph_topology.py::test_no_routing_flags` + grep audit (task 6.5) | - [ ] |
| 4 | retrieval-orchestration | Intent Orchestrator is the single retrieval routing layer | No agent framework is introduced | Given `src/chat_api/` and `src/shared/retrieval/`, when imports are inspected, then no module imports `langgraph.prebuilt`, `langchain.agents`, `langchain_openai`, or a LangChain ChatModel/retriever wrapper, and the compiled graph reports no cycle | import/acyclicity test: `tests/test_chat_graph_topology.py::test_no_agent_framework_and_acyclic` | - [ ] |
| 5 | retrieval-orchestration | Plan-then-execute with no re-planning cycle | Query needing only semantic retrieval | Given a plan with one `semantic_retrieval` entry, when the turn runs, then exactly one capability invocation occurs, no structured query is issued, and exactly one planning LLM call is made | unit test: `tests/test_retrieval_orchestrator.py::test_semantic_only_plan` | - [ ] |
| 6 | retrieval-orchestration | Plan-then-execute with no re-planning cycle | Query needing both capabilities | Given a plan with one semantic and one structured entry, when the turn runs, then both are invoked and both chunk evidence and entity rows reach the downstream nodes | unit test: `tests/test_retrieval_orchestrator.py::test_both_capabilities_plan`; integration: `tests/test_orchestrator_integration.py::test_concurrent_two_entry_plan` | - [ ] |
| 7 | retrieval-orchestration | Plan-then-execute with no re-planning cycle | Query needing multiple retrieval operations | Given a plan with two `semantic_retrieval` entries carrying different queries, when the turn runs, then both execute and evidence contains results from both | unit test: `tests/test_retrieval_orchestrator.py::test_multi_entry_same_capability` | - [ ] |
| 8 | retrieval-orchestration | Plan-then-execute with no re-planning cycle | Results are never fed back to the planner | Given any plan, when execution finishes, then exactly one planning LLM call was made and no retrieval result was sent to the planner | unit test: `tests/test_retrieval_orchestrator.py::test_exactly_one_planning_call` | - [ ] |
| 9 | retrieval-orchestration | Plan execution budgets | Invocation cap truncates an oversized plan | Given a cap of 3 and a 5-entry plan, when the plan executes, then at most 3 invocations are dispatched and the truncation appears in the plan trace | unit test: `tests/test_retrieval_orchestrator.py::test_invocation_cap_truncates` | - [ ] |
| 10 | retrieval-orchestration | Plan execution budgets | Deadline stops further dispatch | Given a deadline that elapses during the first invocation, when remaining entries are considered, then no further invocation is dispatched and the stop reason records deadline exhaustion | unit test: `tests/test_retrieval_orchestrator.py::test_deadline_halts_dispatch` | - [ ] |
| 11 | retrieval-orchestration | Plan execution budgets | Budget exhaustion still produces a normal answer | Given a truncated plan that retrieved two chunks, when the turn continues, then both chunks reach source assembly, the reply carries citations, and the HTTP response surfaces no error | API test: `tests/test_chat_api_rag.py::test_truncated_plan_still_answers` | - [ ] |
| 12 | retrieval-orchestration | Invalid plan entries are rejected without executing | Unknown capability name is discarded | Given a plan with one entry naming `lookup_document` and one valid semantic entry, when the plan executes, then the unknown entry is discarded unexecuted, the valid entry's chunks appear in evidence, and the trace records the rejection reason | unit test: `tests/test_retrieval_orchestrator.py::test_unknown_capability_discarded_sibling_survives` | - [ ] |
| 13 | retrieval-orchestration | Invalid plan entries are rejected without executing | Schema-invalid arguments are discarded | Given an entry whose arguments fail `args_schema` validation, when the plan executes, then no query is issued for it and the rejection reason names the offending argument | unit test: `tests/test_retrieval_orchestrator.py::test_invalid_arguments_rejected` | - [ ] |
| 14 | retrieval-orchestration | Planning failure degrades to both capabilities on the raw query | Planner LLM error falls back | Given a planner client that raises, when the turn runs, then both capabilities are invoked with the raw user query, the turn is marked degraded, and a reply is still generated from the retrieved evidence | unit test: `tests/test_retrieval_orchestrator.py::test_planner_error_fallback` | - [ ] |
| 15 | retrieval-orchestration | Planning failure degrades to both capabilities on the raw query | Planner returns no plan entries | Given a planner returning a message with no capability selections, when the turn runs, then the fallback plan executes and the turn is marked degraded with a stop reason distinct from planner error | unit test: `tests/test_retrieval_orchestrator.py::test_empty_plan_fallback` | - [ ] |
| 16 | retrieval-orchestration | Planning failure degrades to both capabilities on the raw query | Degradation is observable | Given a degraded turn, when logs are inspected, then a structured record states orchestration degraded and carries the reason | log capture test: `tests/test_retrieval_orchestrator.py::test_degradation_logged` | - [ ] |
| 17 | retrieval-orchestration | Tenant scope is unreachable from planner-supplied arguments | Planner attempts to supply a schema argument | Given a plan entry with arguments `{"query": "x", "schema": "tenant_other"}`, when the plan executes, then no query is issued for it, the rejection names the unknown argument, and the session stays scoped to the requesting tenant's schema | unit test: `tests/test_retrieval_orchestrator.py::test_schema_argument_rejected` | - [ ] |
| 18 | retrieval-orchestration | Tenant scope is unreachable from planner-supplied arguments | Conversation history cannot redirect scope | Given a history turn instructing a search of another tenant's schema, when the turn plans and executes, then every query runs against the requesting tenant's schema and no foreign-schema result appears in evidence | integration test: `tests/test_orchestrator_integration.py::test_hostile_history_cannot_cross_tenant` | - [ ] |
| 19 | retrieval-orchestration | Tenant scope is unreachable from planner-supplied arguments | Training-purpose documents remain invisible | Given a tenant schema holding `purpose='training'` and `purpose='query'` documents, when an orchestrated turn runs, then no training-purpose chunk appears in evidence | integration test: `tests/test_orchestrator_integration.py::test_training_purpose_excluded` | - [ ] |
| 20 | retrieval-orchestration | Evidence accumulation into existing state keys | Duplicate chunks are merged with the best score | Given two entries returning `(D1, 3)` with scores 0.6 and 0.8, when the plan finishes, then `chunks` holds exactly one `(D1, 3)` entry with score 0.8 | unit test: `tests/test_retrieval_orchestrator.py::test_dedupe_keeps_best_score` | - [ ] |
| 21 | retrieval-orchestration | Evidence accumulation into existing state keys | Accumulated chunks are ranked | Given entries returning chunks scored 0.4, 0.9, 0.7, when the plan finishes, then `chunks` is ordered 0.9, 0.7, 0.4 | unit test: `tests/test_retrieval_orchestrator.py::test_chunks_ranked` | - [ ] |
| 22 | retrieval-orchestration | Evidence accumulation into existing state keys | Partial failure is not reported as total failure | Given two semantic entries where the first errors and the second returns two chunks, when the plan finishes, then `chunks` holds those two chunks and `retrieval_error` is `None` | unit test: `tests/test_retrieval_orchestrator.py::test_partial_failure_no_error` | - [ ] |
| 23 | retrieval-orchestration | Evidence accumulation into existing state keys | Total failure is reported | Given every executed semantic entry errors, when the plan finishes, then `chunks` is empty and `retrieval_error` carries a value | unit test: `tests/test_retrieval_orchestrator.py::test_total_failure_sets_error` | - [ ] |
| 24 | retrieval-orchestration | Plan trace | Trace covers every plan entry | Given a 3-entry plan with one rejection, when the plan finishes, then the trace has three entries, the rejected one carries its reason and no positive result count, and each executed one carries capability name, result count, and latency | unit test: `tests/test_retrieval_orchestrator.py::test_trace_shape` | - [ ] |
| 25 | retrieval-orchestration | Plan trace | Reranker degradation is visible per entry | Given a semantic entry whose reranking fell back to unranked candidates, when its trace entry is inspected, then its `degraded` flag is true | unit test: `tests/test_retrieval_orchestrator.py::test_trace_degraded_flag` | - [ ] |
| 26 | retrieval-tools | Single semantic retrieval capability with internal scope | Tenant scope is the default | Given an invocation with only a `query`, when it executes, then the retriever is called with no metadata filter and results span the tenant's corpus | unit test: `tests/test_retrieval_tools.py::test_default_tenant_scope` | - [ ] |
| 27 | retrieval-tools | Single semantic retrieval capability with internal scope | Document scope restricts results | Given chunks in `D1` and `D2`, when invoked with `scope={"type":"document","document_ids":["D1"]}`, then every returned chunk has `document_id == "D1"` | unit test: `tests/test_retrieval_tools.py::test_document_scope_single` | - [ ] |
| 28 | retrieval-tools | Single semantic retrieval capability with internal scope | Document scope accepts multiple documents | Given chunks in `D1`, `D2`, `D3`, when invoked with `document_ids=["D1","D2"]`, then results come only from `D1` and `D2` and the ids are passed as bound parameters, never interpolated into SQL text | integration test: `tests/test_retrieval_tools_integration.py::test_document_scope_multiple_bound_params` | - [ ] |
| 29 | retrieval-tools | Single semantic retrieval capability with internal scope | Unknown scope type is rejected | Given `scope={"type":"galaxy"}`, when arguments are validated, then the invocation is rejected without a query and the error names the unsupported scope type | unit test: `tests/test_retrieval_tools.py::test_unknown_scope_type_rejected` | - [ ] |
| 30 | retrieval-tools | Single semantic retrieval capability with internal scope | top_k is clamped to the configured maximum | Given a configured maximum top-K, when invoked with a larger `top_k`, then the retriever is called with the configured maximum | unit test: `tests/test_retrieval_tools.py::test_top_k_clamped` | - [ ] |
| 31 | retrieval-tools | Single semantic retrieval capability with internal scope | Retriever failure returns an error result, not an exception | Given a retriever that raises, when invoked, then an error result carrying the failure message is returned and no exception reaches the orchestrator | unit test: `tests/test_retrieval_tools.py::test_retriever_failure_is_error_result` | - [ ] |
| 32 | retrieval-tools | Exactly two retrieval capabilities are exposed | Registry exposes two capabilities | Given the default registry, when its exported schemas are inspected, then the names are exactly `semantic_retrieval` and `structured_retrieval` | unit test: `tests/test_retrieval_tools.py::test_registry_exposes_two_capabilities` | - [ ] |
| 33 | retrieval-tools | Exactly two retrieval capabilities are exposed | Capability descriptions state retrieval intent | Given each exported schema, when its description is read, then it describes what information the capability retrieves and does not describe the underlying implementation or index | code review of capability descriptions (task 1.7) | - [ ] |
| 34 | retrieval-tools | REMOVED: Document retrieval tools | (removal) | Given the codebase and registry after this change, when searched, then no `search_documents` or `lookup_document` tool class, registration, or exported schema name remains | grep audit (task 1.10) | - [ ] |
| 35 | retrieval-tools | REMOVED: Entity retrieval tool | (removal) | Given the codebase after this change, when searched, then `search_entities` exists only under its new name `structured_retrieval`, with unchanged arguments and behaviour | grep audit (task 1.10) + `tests/test_retrieval_tools.py::test_registry_exposes_two_capabilities` | - [ ] |
| 36 | chat-api | RAG chat endpoint | Chat with simple entity count query | Given a tenant with ORG entities, when a Tenant Admin posts "How many organizations did we extract?", then status is 200 and the body carries `reply`, a non-empty `sources`, and `conversation_id` | API test: `tests/test_chat_api_rag.py::test_entity_count_query` | - [ ] |
| 37 | chat-api | RAG chat endpoint | Chat with document context query | Given a tenant with embedded chunks, when a document-content question is sent, then status is 200 and `sources` references relevant chunks, each with `document_id`, `chunk_index`, `relevance_score` | API test: `tests/test_chat_api_rag.py::test_document_context_query` | - [ ] |
| 38 | chat-api | RAG chat endpoint | Responses carry no live-NER sources | Given any successful turn, when `sources` is inspected, then no entry has `source_type` of `ner`, and entity information present came from structured retrieval over persisted extraction results | API test: `tests/test_chat_api_rag.py::test_no_ner_sources_in_response` | - [ ] |
| 39 | chat-api | RAG chat endpoint | Chat with existing conversation | Given conversation `conv-abc`, when a message is sent with that id, then status is 200, the message is appended, and the history context appears in the LLM prompt | API test: `tests/test_chat_api_conversations.py::test_existing_conversation_turn` | - [ ] |
| 40 | chat-api | RAG chat endpoint | Chat without authentication | Given no JWT, when POSTing `/api/v1/chat`, then status is 401 | API test: `tests/test_chat_api_rag.py::test_unauthenticated_401` | - [ ] |
| 41 | chat-api | Guardrail — blocked question types | Out-of-domain question returns graceful decline | Given "Who is the American president?", when processed, then status is 200, the reply is the domain decline message, `sources` is empty, and neither the orchestrator nor any retrieval capability was invoked | guardrail test: `tests/test_chat_api_guardrails.py::test_out_of_domain_declined_no_retrieval` | - [ ] |
| 42 | chat-api | Guardrail — blocked question types | Chit-chat and general-knowledge prompts are declined | Given "Tell me a joke." and "What's the weather today?", when each is processed, then each returns the domain decline message and triggers no retrieval | guardrail test (parametrised): `tests/test_chat_api_guardrails.py::test_chitchat_declined` | - [ ] |
| 43 | chat-api | Guardrail — blocked question types | In-domain question proceeds to orchestration | Given "Which contracts mention Acme Corp?", when the guardrail classifies it, then the query is admitted and the orchestrator runs | guardrail test: `tests/test_chat_api_guardrails.py::test_in_domain_admitted` | - [ ] |
| 44 | chat-api | Guardrail — blocked question types | Cross-tenant reference is short-circuited without an LLM call | Given a query naming another tenant's schema, when the guardrail processes it, then the query is declined and no classifier LLM call is made | guardrail test: `tests/test_chat_api_guardrails.py::test_cross_tenant_short_circuit_no_llm_call` | - [ ] |
| 45 | chat-api | Guardrail — blocked question types | Classifier failure fails open | Given a classifier call that raises, when an admitted-format query is processed, then the query proceeds to the orchestrator, the failure is logged, and an unsourced answer is still refused by the citation guardrail | guardrail test: `tests/test_chat_api_guardrails.py::test_classifier_failure_fails_open` | - [ ] |
| 46 | chat-api | Guardrail — blocked question types | Multi-lookup questions are no longer refused | Given a question requiring several distinct lookups, when processed, then it is not declined for complexity and the orchestrator decides how many retrieval operations to plan | guardrail test: `tests/test_chat_api_guardrails.py::test_multi_lookup_not_refused` | - [ ] |
| 47 | chat-api | Guardrail — source citation enforcement | Response without sources is rejected | Given a reply produced with no sources, when the guardrail inspects it, then the reply is replaced with "I couldn't find relevant information to answer that question." and the event is logged | guardrail test: `tests/test_chat_api_guardrails.py::test_no_sources_fallback` | - [ ] |
| 48 | chat-api | Guardrail — source citation enforcement | Domain decline keeps its message | Given an out-of-domain decline, when the response is returned, then `reply` is the domain decline message, not the no-sources fallback | guardrail test: `tests/test_chat_api_guardrails.py::test_domain_decline_survives_enforce_sources` | - [ ] |
| 49 | chat-api | pgvector semantic search | Semantic search returns relevant chunks | Given embedded chunks for a tenant, when the plan invokes `semantic_retrieval`, then top-K fused-ranked chunks are returned, each with `document_id`, `chunk_text`, `similarity_score` | integration test: `tests/test_retrieval_tools_integration.py::test_semantic_retrieval_returns_ranked_chunks` | - [ ] |
| 50 | chat-api | pgvector semantic search | Semantic search with empty corpus | Given a tenant with no chunks, when `semantic_retrieval` is invoked, then the turn produces no document chunk sources and does not raise | integration test: `tests/test_retrieval_tools_integration.py::test_empty_corpus` | - [ ] |
| 51 | chat-api | pgvector semantic search | Citation includes page number when the chunk has one | Given a chunk with `page_number=3`, when `_enrich_citations` builds its citation, then `Citation.page_number == 3` | unit test: `tests/test_chat_api_rag.py::test_citation_page_number_present` | - [ ] |
| 52 | chat-api | pgvector semantic search | Citation page number is null for chunks without metadata | Given a chunk with no `page_number`, when `_enrich_citations` runs, then `Citation.page_number` is `None` and no exception is raised | unit test: `tests/test_chat_api_rag.py::test_citation_page_number_absent` | - [ ] |
| 53 | chat-api | pgvector semantic search | Chat retrieves relevant document context for a lexical (exact-term) query | Given a chunk containing a specific identifier, when a question containing that exact term is asked, then the response cites that chunk even at low embedding similarity | integration test: `tests/test_retrieval_tools_integration.py::test_lexical_term_retrieval` | - [ ] |
| 54 | chat-api | REMOVED: NER inference for chat context | (removal) | Given the codebase after this change, when searched, then no `ner_enrichment` node, `ner_entities` state key, `source_type="ner"` construction, or NER block in prompt assembly remains, while ingestion-time persistent NER is unchanged | grep audit (task 5.6) + `tests/test_context_assembler.py` updated suite | - [ ] |
| 55 | chat-api | REMOVED: Guardrail — query complexity limits | (removal) | Given `GuardrailService` after this change, when inspected, then `assess_complexity` and the multi-lookup decline are absent and no caller references them | grep audit (task 3.1) + `tests/test_chat_api_guardrails.py::test_multi_lookup_not_refused` | - [ ] |
| 56 | retrieval-eval | Evaluation executes through the tool layer | Eval run invokes the capability layer | Given a run with a spy registry, when N golden queries are evaluated, then `semantic_retrieval` is invoked exactly N times per baseline configuration | unit test: `tests/test_retrieval_eval_runner.py::test_baseline_invokes_semantic_retrieval` | - [ ] |
| 57 | retrieval-eval | Evaluation executes through the tool layer | Capability errors are recorded, not fatal | Given N queries where one invocation returns an error, when the run completes, then the other N-1 are evaluated and the report lists the failed query with its error | unit test: `tests/test_retrieval_eval_runner.py::test_capability_error_recorded` | - [ ] |
| 58 | retrieval-eval | Orchestrated configuration is measured against the direct baseline | Orchestrated configuration appears in the report | Given a run including the orchestrated configuration, when the report is produced, then it carries `recall@5` and `nDCG@5` for it alongside the baselines, ranked by `nDCG@5` | unit test: `tests/test_retrieval_eval_runner.py::test_orchestrated_configuration_in_report` + regenerated baseline report (task 7.6) | - [ ] |
| 59 | retrieval-eval | Orchestrated configuration is measured against the direct baseline | Orchestration failures during eval do not abort the run | Given a run where one query's planning call errors, when the run completes, then remaining queries are scored and the failed query is recorded with its degraded status | unit test: `tests/test_retrieval_eval_runner.py::test_planning_error_recorded` | - [ ] |
| 60 | retrieval-eval | Orchestrated configuration is measured against the direct baseline | Configuration fields match the orchestrator's budgets | Given the matrix configuration model, when its orchestration fields are inspected, then they express the invocation cap and wall-clock deadline and express no loop iteration count or observation character limit | unit test: `tests/test_retrieval_eval_runner.py::test_configuration_fields` | - [ ] |
| 61 | agentic-retrieval | REMOVED: Bounded agentic retrieval loop (and its 9 dependent requirements) | (removal) | Given the codebase after this change, when searched, then `run_agentic_loop`, `src/chat_api/graph/agentic.py`, `src/shared/retrieval/agentic_loop.py`, and all `agentic_*` state keys are absent, and no test imports them | grep audit (task 6.5) + green test run after deletions (task 4.7) | - [ ] |
| 62 | agentic-retrieval | REMOVED: Feature flag and flag-off equivalence | (removal) | Given the settings model and `RAGOrchestrator`, when inspected, then `chat_use_graph`, `chat_agentic_retrieval`, `agentic_max_iterations`, `agentic_max_iterations_complex`, `agentic_observation_char_limit`, and `_execute_legacy` are absent | grep audit (task 6.5) + `tests/test_chat_graph_topology.py::test_no_routing_flags` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Concurrent plan execution and `AsyncSession` (design Decision 3) | Reusing one `AsyncSession` across `asyncio.gather`-ed plan entries, mirroring the node code that today creates one session per node. SQLAlchemy raises `IllegalStateChangeError` only under real concurrency, so single-entry plans and mocked tests pass while two-entry plans fail in production. | Read the execution path: confirm each entry obtains its own session from `async_sessionmaker`. Confirm an integration test executes a two-entry plan concurrently against a real database and both entries return results. `HybridRetriever`'s sequential dense/sparse comment in `retriever.py` states the same constraint — check it was not "optimised" into `gather` as collateral. |
| 2 | Scope-to-metadata-filter translation (design Decision 2) | Widening `_metadata_filter_clause` by string-interpolating the document id list into the SQL text instead of binding `= ANY(:mf_document_ids)`, or silently ignoring `scope` when the key is present but unrecognised (returning tenant-wide results for an invalid scope rather than rejecting). | Read `_metadata_filter_clause`: the value must appear only as a bound parameter. Confirm an unknown `scope.type` produces a rejection, not a silent fall-through to tenant scope — scenario 29 must fail if the guard is removed. |
| 3 | Guardrail fail-open vs. fail-closed (design Decision 1) | Implementing the classifier exception path as a decline, or wrapping it so broadly that a genuine in-domain query is declined when the LLM is slow. Both look like "safe" defaults and neither matches the spec. | Confirm the `except` path around `classify_domain` proceeds to the orchestrator and logs. Confirm scenario 45's test fails if that path is changed to a decline. |
| 4 | Removing NER without removing its consumers (design Decision 7) | Deleting `ner_enrichment_node` but leaving `ner_entities` reads in `source_assembly_node`, `ContextAssembler.assemble`'s signature, or its token accounting — producing an assembler that silently subtracts tokens for a block it never emits, or a `KeyError` on a state key nobody writes. | Grep for `ner_entities`, `ner_client`, `source_type="ner"`, `"ner"` across `src/`. Confirm `ContextAssembler.assemble`'s parameter list and its token budgeting no longer account for an NER block. Confirm `Source`/`Citation` schema fields were **not** deleted — historical messages need them. |
| 5 | Plan-entry rejection silently swallowing the whole plan (spec: Invalid plan entries) | Implementing rejection as an early `return` or an exception that aborts the remaining entries, so one bad entry loses good retrievals — an easy mistake when validation is hoisted into a loop preamble. | Confirm scenario 12's test has one invalid **and** one valid entry, and asserts the valid entry's chunks are present. Reject any implementation where validation runs as a plan-level all-or-nothing gate. |
| 6 | Fixed-topology claim vs. leftover branching (design Decisions 5 and 6) | Deleting the flags from `settings` but leaving `build_chat_graph` accepting a parameter, an `if` on a module constant, or a second `add_conditional_edges` — leaving two topologies with no way to reach one. | Read `build_chat_graph` end to end: the only conditional edge should be the guardrail decline. Grep for `chat_use_graph`, `chat_agentic_retrieval`, `agentic_` across `src/`, `tests/`, and compose/env files — hits outside archived changes are failures. |
| 7 | Trace field drift (spec: Plan trace) | Inventing trace fields (`iteration`, `tool_name`) carried over from the deleted loop trace, or omitting the rejection reason on discarded entries so scenario 24 is unverifiable. | Compare the emitted trace dict keys against the requirement's named fields. `iteration` must not appear. Confirm rejected entries carry a reason. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate PostgreSQL schemas | Schema/tenant selection comes only from authenticated request state via `ToolContext`; capabilities must not declare `schema`, `tenant_id`, `tenant`, or `purpose` arguments | Inspect both capabilities' `args_schema` for the forbidden keys and confirm `assert_no_tenancy_params` still runs at registration. Run the tests for rows 17–19. Confirm every `ToolContext` construction reads `tenant_id`/`schema` from `ChatState`, never from planner output. |
| ADR-003-model-serving-topology | Per-tenant model serving | Chat must no longer call model-serving at query time; ingestion-time NER unchanged | Grep chat request paths for model-serving calls — none should remain. Confirm ingestion-time extraction still calls it, unchanged. |
| ADR-004-openspec-governance | Spec-driven change governance | Every capability whose requirements move ships a delta spec in this change | Confirm `specs/` contains deltas for retrieval-orchestration, retrieval-tools, chat-api, agentic-retrieval, retrieval-eval, and that `openspec validate` passes. |
| ADR-005-opencode-agent-boundaries | `src/shared` must not import service packages | Orchestrator planner lives in `src/shared/retrieval/` with no `src.chat_api` imports; entity search stays injected via `ToolContext.sql_search` | Grep `src/shared/` for `from src.chat_api` / `import src.chat_api` — zero hits. Confirm `structured_retrieval` still reaches SQL only through `context.sql_search`. |
| ADR-007-chatbot-architecture | Full RAG over three sources including live NER; guardrails include complexity limits | **Contradicted on two points by this change** (live NER removed; complexity limits removed). All other commitments — SQL validation, citation enforcement, tenant scoping, disclaimer, rate limiting, P95 < 10s — remain in force | Confirm a superseding ADR was recorded before archive (see design Open Questions). Confirm the preserved commitments still hold: SQL validation layer still gates `structured_retrieval`, citation enforcement still runs (row 47), disclaimer still returned, rate limiting untouched, and P95 measured post-change against the 10s target. |
| ADR-008-base-model-as-default | Base model is version 0 when no promoted model exists | Applies to ingestion-time NER only after this change | Confirm no chat-path code references model version selection. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1.)*

- [ ] Rows 1–4 (orchestrator is the single routing layer): test output for the orchestrator-runs-once test, the planner-inputs assertion, a settings inspection showing no strategy flag, and an import/cycle check
- [ ] Rows 5–8 (plan-then-execute): test output for single-capability, both-capabilities, multi-entry, and exactly-one-planning-call assertions
- [ ] Rows 9–11 (budgets): test output showing plan truncation at the cap, dispatch halted at the deadline, and a truncated turn still returning a cited reply
- [ ] Rows 12–13 (invalid entries): test output showing an unknown capability discarded while a sibling entry still returns chunks, and a schema-invalid entry rejected by argument name
- [ ] Rows 14–16 (planning failure): test output for planner-raises and empty-plan fallbacks, plus a log excerpt carrying the degradation reason
- [ ] Rows 17–19 (tenant scope): test output for the schema-argument rejection, an integration run proving cross-schema queries never issue, and the training-purpose exclusion test
- [ ] Rows 20–23 (evidence accumulation): test output for dedupe-by-best-score, ranking order, partial-failure, and total-failure error semantics
- [ ] Rows 24–25 (plan trace): trace dump for a 3-entry plan with one rejection, and a trace entry showing `degraded=true` after reranker fallback
- [ ] Rows 26–31 (`semantic_retrieval` scope): test output for default tenant scope, single-document scope, multi-document scope with bound parameters, unknown-scope rejection, top_k clamping, and retriever-failure-as-error-result
- [ ] Rows 32–33 (two capabilities): exported-schema dump showing exactly the two names, and reviewer confirmation the descriptions state intent not implementation
- [ ] Rows 34–35 (tool removals): grep output showing no `search_documents` / `lookup_document` / `search_entities` references outside archived changes
- [ ] Rows 36–40 (chat endpoint): API traces or test output for the entity-count turn, document-context turn, a `sources` dump containing no `ner` entry, the existing-conversation turn, and the 401
- [ ] Rows 41–46 (guardrail as domain filter): test output for each of the three named out-of-domain prompts declining with no retrieval, an in-domain admission, the cross-tenant short-circuit with no classifier call, the fail-open path, and a multi-lookup question no longer refused
- [ ] Rows 47–48 (citation enforcement): test output for the no-sources fallback and the domain-decline message surviving it
- [ ] Rows 49–53 (semantic search behaviour): test output for top-K results, empty corpus, both page-number citation cases, and the lexical-term retrieval case
- [ ] Rows 54–55 (chat-api removals): grep output for `ner_enrichment` / `ner_entities` / `source_type="ner"` and for `assess_complexity`
- [ ] Rows 56–60 (eval harness): spy-registry invocation counts, a report with a failed query recorded, a report containing the orchestrated configuration ranked with the baselines, a degraded-query record, and the configuration model's field list
- [ ] Rows 61–62 (agentic and flag removals): grep output for `run_agentic_loop`, `agentic_`, `chat_use_graph`, `chat_agentic_retrieval`, `_execute_legacy`
- [ ] P95 latency measurement for a representative query set, compared against the pre-change flag-off path and the 10s ADR-007 target

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Superseding ADR for ADR-007 recorded and accepted
- [ ] Frontend audit completed — portal chat and embeddable widget render citation lists containing no `ner` sources, and still render stored historical messages that contain them

### Edge Case Evidence

- [ ] Risk 1 confirmed — each plan entry uses its own `AsyncSession`; a two-entry concurrent plan verified against a real database
- [ ] Risk 2 confirmed — document ids bound as parameters, unknown `scope.type` rejected rather than silently widened to tenant scope
- [ ] Risk 3 confirmed — classifier exception path proceeds to the orchestrator and logs; does not decline
- [ ] Risk 4 confirmed — no residual `ner_entities` reads or token accounting; `Source`/`Citation` entity fields retained
- [ ] Risk 5 confirmed — one invalid entry does not abort sibling entries
- [ ] Risk 6 confirmed — `build_chat_graph` has exactly one conditional edge; no flag references remain outside archived changes
- [ ] Risk 7 confirmed — trace keys match the specified field set; no `iteration` key; rejected entries carry reasons

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** redesign-retrieval-orchestration
**Proposal:** `openspec/changes/redesign-retrieval-orchestration/proposal.md`
**Spec files reviewed:**

- specs/retrieval-orchestration/spec.md
- specs/retrieval-tools/spec.md
- specs/chat-api/spec.md
- specs/agentic-retrieval/spec.md
- specs/retrieval-eval/spec.md

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
