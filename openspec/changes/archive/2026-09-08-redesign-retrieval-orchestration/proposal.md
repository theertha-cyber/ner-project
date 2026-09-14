## Why

Retrieval strategy is currently decided in three disconnected places: the guardrail (complexity score gates multi-lookup questions), a runtime feature flag (`chat_agentic_retrieval` picks one-shot vs. agentic loop), and a legacy non-graph code path (`chat_use_graph`). The result is four possible pipelines to reason about, a guardrail that mixes domain filtering with routing, and two semantic retrieval tools that differ only in search scope. This change collapses routing into a single Intent Orchestrator, reduces the retrieval surface to two capabilities, and removes retrieval-time NER — establishing one pipeline as the long-term foundation.

## What Changes

- **Guardrail becomes a pure domain filter.** It answers one question: does this query belong to the platform's supported domain (tenant documents and extracted entities)? Out-of-domain prompts ("Who is the American president?", "Tell me a joke.", "What's the weather today?") are declined before retrieval. Decision is made by an LLM classifier, with cheap deterministic short-circuits (cross-tenant reference, PII request) kept ahead of it.
- **BREAKING:** Guardrail no longer performs complexity assessment or any routing. `assess_complexity` and the "That question requires multiple lookups" decline are removed. Multi-lookup questions are now handled by the orchestrator, not refused.
- **New Intent Orchestrator node** runs immediately after the guardrail. It receives the user query, recent conversation history, the available retrieval capabilities, and an orchestration prompt describing them, and emits a retrieval plan: which capabilities to invoke, with what arguments, in a single planning call. The plan is then executed (capabilities run concurrently), with no observe/re-plan cycle.
- **BREAKING:** `search_documents` and `lookup_document` are replaced by a single `semantic_retrieval` capability that takes an internal `scope` (`tenant` today, `document` with document ids; the shape is extensible to further scopes). `search_entities` is renamed to `structured_retrieval` to match the orchestration vocabulary. The orchestrator sees exactly two capabilities.
- **BREAKING:** The retrieval-time NER enrichment node is removed. `ner_enrichment` disappears from the graph, `ner_entities` from graph state, `source_type="ner"` sources from responses, and the "NER entities" block from assembled prompts. Ingestion-time persistent NER is untouched and continues to power structured retrieval.
- **BREAKING:** The bounded agentic loop (`run_agentic_loop`) and its observe/re-plan machinery are removed, along with the `chat_agentic_retrieval`, `chat_use_graph` feature flags and the legacy `RAGOrchestrator._execute_legacy` path. The compiled graph is the only execution path. Cost bounds (max capability invocations per turn, wall-clock deadline) are preserved on the new orchestrator.
- Source Assembly, Prompt Assembly, and LLM Generation keep their current behaviour, minus the NER inputs they no longer receive.
- The retrieval eval harness is retargeted from the agentic loop to the orchestrator plan-and-execute path, and from `search_documents` to `semantic_retrieval`.

## Capabilities

### New Capabilities

- `retrieval-orchestration`: The Intent Orchestrator — plan generation from query + history + capability descriptions, plan validation, concurrent plan execution, budget enforcement, result accumulation, and degradation behaviour when planning fails.

### Modified Capabilities

- `chat-api`: Guardrail requirements change from blocked-question-type + complexity limits to domain-membership filtering; the "NER inference for chat context" requirement is removed; the RAG chat endpoint's pipeline description changes to the new topology.
- `retrieval-tools`: The two semantic tools collapse into one scope-parameterised `semantic_retrieval` capability; `search_entities` becomes `structured_retrieval`. (Delta currently lives in the unarchived `retrieval-tools-and-eval` change; this change supersedes those tool definitions.)
- `agentic-retrieval`: Removed as a capability — superseded by `retrieval-orchestration`. (Currently defined in the unarchived `agentic-retrieval-loop` change.)
- `retrieval-eval`: Harness runs against orchestrator plans rather than the agentic loop; matrix configuration fields tied to loop iterations are replaced by plan-execution budgets.

## Impact

Code:
- `src/chat_api/graph/builder.py` — flag branching and `ner_enrichment` edges deleted; new `orchestrator` node between `guardrail` and the retrieval stage.
- `src/chat_api/graph/nodes.py` — `guardrail_node` rewritten; `sql_retrieval_node`, `retrieval_node`, `agentic_retrieval_node`, `ner_enrichment_node` removed and replaced by an orchestrator node plus a plan-execution node; `source_assembly_node` and `prompt_assembly_node` lose their NER inputs.
- `src/chat_api/graph/state.py` — `complexity`, `ner_entities`, `agentic_*` fields removed; `retrieval_plan` and `plan_trace` added.
- `src/chat_api/graph/agentic.py`, `src/shared/retrieval/agentic_loop.py` — deleted, replaced by an orchestrator planner module in `src/shared/retrieval/`.
- `src/chat_api/services/guardrails.py` — complexity assessment removed; LLM domain classifier added; `enforce_sources` unchanged.
- `src/chat_api/services/rag_orchestrator.py` — `_execute_legacy` and `_vector_source` deleted; `ner_client` dependency dropped.
- `src/chat_api/services/ner_client.py` — no longer used by chat; removed if it has no other consumer.
- `src/chat_api/services/context_assembler.py` — NER block dropped from assembly and token budgeting.
- `src/shared/retrieval/tools/document_tools.py`, `entity_tools.py`, `tools/__init__.py` — tool merge and rename; registry exports two capabilities.
- `src/shared/retrieval/retriever.py` — `metadata_filter` gains multi-document-id support to back the `document` scope.
- `src/shared/retrieval/eval/runner.py`, `config.py` — retargeted to the orchestrator.
- `src/shared/config.py` — `chat_use_graph`, `chat_agentic_retrieval`, `agentic_max_iterations`, `agentic_max_iterations_complex`, `agentic_observation_char_limit` removed; orchestrator budget settings added.

APIs / consumers:
- `POST /api/v1/chat` response `sources` no longer contains `source_type="ner"` entries. The portal chat UI and embeddable widget render citations from these; both must tolerate the absence.
- Out-of-domain queries now return a domain-decline reply instead of a blocked-type decline; decline copy changes.

Tests: `tests/test_agentic_loop.py`, `tests/test_agentic_loop_integration.py`, `tests/test_retrieval_tools.py`, `tests/test_retrieval_tools_integration.py`, `tests/test_retrieval_eval_runner.py`, and the chat graph/guardrail tests all need rework.

Ops: the guardrail classifier adds one LLM call per turn ahead of retrieval; the orchestrator adds one planning call. Net LLM calls per turn go from 1–2 (flag-off) or 2–4 (flag-on) to a fixed 3.

## Open Questions

- Guardrail classifier model and latency budget: reuse the main chat model or a cheaper/faster deployment? Affects per-turn cost and p95 latency.
- Should the guardrail classifier fail open (allow through to retrieval) or fail closed (decline) when the LLM call errors? Assumption: fail open, since retrieval and generation already refuse to answer without sources.
- Whether `document` scope should accept multiple document ids or exactly one. Assumption: a list, since the orchestrator may want several named documents in one plan; `_metadata_filter_clause` currently supports a single id and must be widened.
- Whether the orchestrator may emit the same capability more than once in a single plan (e.g. two semantic queries with different phrasings). Assumption: yes, bounded by a max-invocations budget.
- Whether removing `source_type="ner"` breaks any stored conversation history rendering in the portal. Needs a check against persisted message payloads.
- Whether `NERClient` has consumers outside chat before deleting it.
