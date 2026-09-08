## Context

Today a chat turn can take one of four paths. `chat_use_graph=False` runs `RAGOrchestrator._execute_legacy`, a hand-rolled sequential pipeline. `chat_use_graph=True` compiles a LangGraph whose topology is itself chosen at build time by `chat_agentic_retrieval`: flag-off fans out to `sql_retrieval` and `retrieval` in parallel; flag-on runs `agentic_retrieval`, a bounded plan/observe loop that can itself fall back mid-turn to the flag-off nodes. Every path then passes through `ner_enrichment`, which calls model-serving once per chunk for the top three chunks.

Routing decisions are spread across three layers. `GuardrailService.assess_complexity` scores the query and, when the agentic flag is off, refuses anything over 3 — a routing decision dressed as a safety check. The build-time flag picks the retrieval strategy. Inside the agentic loop, a planner LLM picks tools. The tools it picks from are `search_documents`, `lookup_document`, and `search_entities`; the first two are the same retrieval against the same index, differing only in whether a `document_id` metadata filter is applied.

The constraints that shape this design: tenant isolation is schema-based and must never be reachable from model-supplied arguments (ADR-001); the chat pipeline must not adopt an agent framework (established in the agentic-retrieval-loop change and reaffirmed here); the compiled graph must stay acyclic; P95 latency target is under 10 seconds; every answer must carry citations.

## Goals / Non-Goals

**Goals:**

- One execution path for a chat turn. No runtime or build-time flag selects topology.
- One place that decides how retrieval happens: the Intent Orchestrator.
- A guardrail that answers exactly one question — is this query in the platform's domain?
- Two retrieval capabilities exposed to the orchestrator, named for retrieval intent rather than implementation.
- Retrieval-time NER gone; ingestion-time persistent NER untouched.
- Predictable per-turn cost: a fixed number of LLM calls, a bounded number of retrieval invocations.
- Source Assembly, Prompt Assembly, and Generation keep working on the same state keys they use today.

**Non-Goals:**

- Changing ingestion, chunking, embedding, extraction, or persistent NER.
- Changing the reranker, the hybrid retriever, or RRF fusion.
- Changing SQL generation or the SQL validation layer.
- Introducing a collection/folder concept. The scope shape is designed to admit one later; no such concept exists in the data model today.
- Re-planning after seeing results. Explicitly ruled out — see Decision 3.
- Caching, prompt-level cost optimisation, or streaming.

## Currently-In-Force ADRs

All ADRs in `docs/adr/` carry **Status: Proposed**; ADR-008 supersedes ADR-002 partially. None are superseded by a later ADR except ADR-002.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate PostgreSQL schemas | Schema selection MUST come from authenticated request state via `ToolContext`, never from planner output. Retrieval capabilities MUST NOT declare `schema`/`tenant_id`/`tenant`/`purpose` arguments. |
| ADR-003-model-serving-topology | Per-tenant model serving | Chat no longer calls model-serving at query time; ingestion-time NER continues to. No change to serving topology. |
| ADR-004-openspec-governance | Spec-driven change governance | This change ships as an OpenSpec change with deltas for every capability whose requirements move. |
| ADR-005-opencode-agent-boundaries | `src/shared` MUST NOT import service packages | The orchestrator planner lives in `src/shared/retrieval/`; entity search stays injected via `ToolContext.sql_search`. |
| ADR-007-chatbot-architecture | Full RAG over three sources (SQL, pgvector, live NER); guardrails include blocked question types and query complexity limits | **This design contradicts ADR-007 on two points**: live NER is removed as a retrieval source, and complexity limits are removed as a guardrail. Flagged under Open Questions for a superseding ADR. All other ADR-007 commitments — SQL validation, citation enforcement, tenant scoping, disclaimer, rate limiting, P95 < 10s — are preserved. |
| ADR-008-base-model-as-default | Base model is version 0 when no promoted model exists | Applies to ingestion-time NER only after this change. |

## Decisions

### Decision 1: Guardrail is an LLM domain classifier behind deterministic short-circuits

**Choice:** `GuardrailService` gains `classify_domain(message, conversation_context) -> "in_domain" | "out_of_domain"`, backed by a single LLM call with a fixed system prompt describing the platform's domain (the tenant's uploaded documents and the entities extracted from them) and a small set of labelled examples. Ahead of it, two cheap deterministic checks run first and skip the LLM call entirely: cross-tenant schema references, and requests for PII of the kind not present in extracted entities. `assess_complexity` and the existing `BLOCKED_PATTERNS` for classification/content-generation/summarization are deleted — those are domain judgements the classifier now makes. The classifier fails open: on any exception, the query proceeds, and the existing source-citation guardrail still prevents an unsourced answer.

**Rationale:** The rejection examples in the request ("Tell me a joke", "What's the weather today?") are open-domain; enumerating them in regex is a losing game, and the current regex set already misfires on legitimate queries ("summarize the findings in this contract" is in-domain but matches the summarization pattern). One classifier call is a fixed, small cost and runs before retrieval, so it saves the retrieval work it rejects. Failing open is correct here because the guardrail is a cost/scope filter, not a security boundary — tenant isolation is enforced structurally in `ToolContext`, and an unsourced answer is already blocked downstream.

**Alternatives considered:**
- Regex/keyword rules only — ruled out: cannot cover open-domain chit-chat, and the existing rules already produce false positives.
- Fold the domain check into the orchestrator as a "no retrieval needed" plan outcome — ruled out: re-couples filtering to routing, which is exactly what this change separates, and makes the decline path depend on a larger prompt.
- Fail closed on classifier error — ruled out: an LLM outage would turn every query into a decline; failing open degrades to today's behaviour instead.

### Decision 2: `semantic_retrieval` takes a structured `scope` object rather than separate tools

**Choice:** One capability with arguments `{query, top_k?, scope?}`, where `scope` is `{"type": "tenant"}` (default) or `{"type": "document", "document_ids": [...]}`. The capability translates `scope` into the retriever's existing `metadata_filter`. `_metadata_filter_clause` in `src/shared/retrieval/retriever.py` widens from `document_id = :mf_document_id` to `document_id = ANY(:mf_document_ids)`, still fully bound-parameterised. `search_entities` is renamed `structured_retrieval` with unchanged arguments and behaviour.

**Rationale:** The two existing tools call the same `_retrieve` helper with the only difference being one metadata filter key. Exposing that difference as two tool names makes the planner choose between implementations; a `scope` argument makes it express intent ("search inside these documents") instead. A structured object rather than a flat `document_id` argument leaves room for a future `collection` scope without a schema-breaking change or a new capability. Accepting a list of ids rather than one matches how a plan naturally forms — "check the two contracts we discussed" is a single retrieval intent.

**Alternatives considered:**
- Keep two tools, rename them — ruled out: does not reduce the surface the orchestrator reasons about.
- Flat optional `document_id` argument — ruled out: adding a second scope dimension later means either another flat argument or a breaking rename.
- Infer scope from conversation history inside the capability — ruled out: hides a routing decision inside the retrieval layer, the same mistake this change removes from the guardrail.

### Decision 3: Single-shot plan, then concurrent execution

**Choice:** The orchestrator makes exactly one LLM call, binding the two capability schemas via `ToolRegistry.export_schemas()` and the existing `AsyncOpenAI`/`AsyncAzureOpenAI` client with `tool_choice="auto"`, and reads the returned `tool_calls` as the plan. Every entry is validated against its capability's `args_schema`; invalid entries are discarded with a recorded reason. Surviving entries, capped at `orchestrator_max_invocations`, execute concurrently. Results never return to the planner. `run_agentic_loop` and `src/chat_api/graph/agentic.py` are deleted.

**Rationale:** The observe/re-plan cycle was the source of the loop's cost and latency variance — an unbounded-ish number of LLM calls per turn, each carrying growing observation text, against a 10s P95 budget. Fixing planning at one call makes per-turn cost a constant (guardrail classify + orchestrator plan + generation = 3 calls) and makes the turn's latency the sum of one planning call and the slowest retrieval. The capability the loop uniquely provided — refining a query after seeing weak results — is largely recovered by letting one plan contain several entries, which covers the common multi-hop case ("compare what contract A and contract B say about X"). Removing the loop also removes prompt-injection-via-observation as a class of concern: no retrieved text ever reaches the planner.

Concurrency uses `asyncio.gather` over entries, each with its **own** `AsyncSession` from `async_sessionmaker`. This is load-bearing: a single `AsyncSession` cannot run two statements concurrently (SQLAlchemy raises `IllegalStateChangeError`), which is why `HybridRetriever` runs its dense and sparse legs sequentially today. Entries must not share a session.

**Alternatives considered:**
- Keep the bounded agentic loop, retargeted to two capabilities — ruled out by the requester in favour of predictable cost; it also keeps the observation-injection surface.
- Plan + at most one refine round — ruled out for now: doubles worst-case planning cost for a case the multi-entry plan mostly covers. If eval shows a recall gap against the archived agentic numbers, this is the first thing to revisit.
- Deterministic planner (heuristics over the query) — ruled out: it is the complexity-scoring mistake again, in a new location.

### Decision 4: Orchestrator planning lives in `src/shared/retrieval/orchestrator.py`, node wiring stays in `src/chat_api`

**Choice:** A new `src/shared/retrieval/orchestrator.py` exposes `plan_retrieval(...) -> RetrievalPlan` and `execute_plan(plan, context, budget) -> OrchestrationResult`, with no `src.chat_api` imports. `src/chat_api/graph/nodes.py` builds `ToolContext` from `ChatState` and calls them. This mirrors how `agentic_loop.py` was placed and keeps the eval harness able to exercise the orchestrator without importing the chat service (ADR-005).

**Rationale:** The eval harness needs the same code path the chat pipeline runs; putting the planner in `src/shared` is the only arrangement that gives it that without a layering violation.

**Alternatives considered:**
- Put it in `src/chat_api/graph/` — ruled out: the eval harness would have to import the service package.

### Decision 5: Graph topology and state

**Choice:** Fixed topology, no conditional edges except the guardrail decline:

```
guardrail ──(declined)──> END
    └──(admitted)──> orchestrator ──> retrieval_execution ──> source_assembly ──> prompt_assembly ──> generation ──> END
```

Planning and execution are two nodes, not one, so the plan is visible in state between them and testable in isolation. `ChatState` drops `complexity`, `ner_entities`, `tool_trace`, `agentic_degraded`, `agentic_stop_reason`; it gains `retrieval_plan`, `plan_trace`, `orchestration_degraded`, `orchestration_stop_reason`. `chunks`, `sql_results`, `retrieval_error`, `sql_error`, `sources`, `document_names`, `prompt_messages`, `reply` are unchanged, so `source_assembly`, `prompt_assembly`, and `generation` change only by losing their NER inputs.

**Rationale:** Keeping the evidence keys stable is what makes this a routing change rather than a pipeline rewrite. Splitting plan from execution keeps each node's log line meaningful and lets tests assert on plans without stubbing retrieval.

**Alternatives considered:**
- One combined orchestrator node — ruled out: plan and execution failures become indistinguishable in traces.
- Keep `tool_trace` as the trace key name — ruled out: the shape changes (no iteration index, adds rejection reasons), so a rename avoids silently mismatched consumers.

### Decision 6: Delete the legacy path and both flags outright

**Choice:** Remove `chat_use_graph`, `chat_agentic_retrieval`, `agentic_max_iterations`, `agentic_max_iterations_complex`, `agentic_observation_char_limit` from settings, and delete `RAGOrchestrator._execute_legacy` and `_vector_source`. Add `orchestrator_max_invocations` (default 3) and reuse `agentic_deadline_seconds` renamed to `retrieval_deadline_seconds` (default 8.0). `RAGOrchestrator.execute` becomes graph-only.

**Rationale:** The legacy path has been dead in practice (`chat_use_graph` defaults True) and duplicates pipeline logic that then drifts — it still contains a latent bug where a NER source's `document_id` is assigned a `Source` object rather than an id. Keeping it as an escape hatch means maintaining two implementations of a pipeline this change is trying to reduce to one.

**Alternatives considered:**
- Gate the new orchestrator behind a new flag for rollout — ruled out: re-introduces the flag branching being removed, and the flag would have to be removed later anyway.
- Keep `chat_use_graph` — ruled out: the legacy path cannot express the new topology without being rewritten, at which point it is not a fallback.

### Decision 7: NER removal is a deletion, not a deprecation

**Choice:** Delete `ner_enrichment_node`, the `ner_entities` state key, `source_type="ner"` construction in `source_assembly_node`, the NER block in `ContextAssembler.assemble` (and its token accounting), and `RAGOrchestrator.ner_client`. `NERClient` itself is deleted only after confirming no other consumer; the `Source`/`Citation` schemas keep their `entity_type`/`confidence`/`value` fields, which structured retrieval and stored history still use.

**Rationale:** The enrichment ran up to three model-serving calls per turn to produce entity sources for text the LLM already had verbatim in its context. The same entity data, persisted at ingestion, is reachable through `structured_retrieval` with no per-turn inference. Keeping the schema fields means historical messages containing `ner` sources still deserialise and render.

**Alternatives considered:**
- Keep the node behind a flag — ruled out: flags are what this change removes.
- Strip `ner` sources at the API boundary but keep the node — ruled out: pays the latency without the benefit.

## Risks / Trade-offs

- [Guardrail classifier rejects legitimate in-domain queries, silently reducing usefulness] → Classifier prompt carries labelled in-domain examples including edge cases (summarise-this-document, compare-two-documents); every decline is logged with the query so false-positive rate is measurable; fail-open on error.
- [Two added LLM calls per turn push P95 past 10s] → Net call count is fixed at 3 versus today's 2–4 on the agentic path; the guardrail call runs before retrieval and short-circuits on cheap rules; deadline budget still bounds retrieval. Latency must be measured against the current flag-off path before rollout, not assumed.
- [Single-shot planning retrieves less than the agentic loop on multi-hop queries] → The eval harness runs the orchestrated configuration against the direct baseline on the golden set; if `nDCG@5` regresses against the archived agentic numbers, Decision 3's "plan + one refine" alternative is the pre-identified remedy.
- [Concurrent plan entries sharing an `AsyncSession` raise `IllegalStateChangeError` under load] → One session per entry, created from `async_sessionmaker`; an integration test executes a two-entry plan concurrently and asserts both complete.
- [Removing `ner` sources breaks portal or widget citation rendering] → Audit `CitationChips`, `MessageThread`, and the widget renderer for `source_type === 'ner'` branches before merge; stored history may still contain them, so the branches must be kept tolerant rather than deleted.
- [Deleting the legacy path removes the only non-graph fallback] → The graph path is the default today and is covered by the existing parity and RAG test suites; rollback is a deploy revert, not a flag flip. Accepted deliberately.
- [Renaming tool names breaks the eval harness's stored baselines] → Baseline reports are regenerated as part of this change; the regression gate compares against the regenerated baseline, and the rename is noted in the report metadata.
- [A plan entry's arguments echo attacker-controlled text from conversation history] → Arguments are validated against `args_schema`, tenancy keys are structurally absent, scope values are bound parameters, and the SQL validation layer still gates `structured_retrieval`. The blast radius of a hostile history turn is a wasted retrieval, not a scope escape.

## Migration Plan

1. Land the retrieval layer first: widen `_metadata_filter_clause` to a list, add `semantic_retrieval` with `scope`, rename `search_entities` to `structured_retrieval`, update `build_default_registry`. Old tool classes deleted in the same step — nothing outside the loop and the eval harness references them.
2. Add `src/shared/retrieval/orchestrator.py` (`plan_retrieval`, `execute_plan`) with unit tests using a scripted planner client, before wiring it into the graph.
3. Rewrite `GuardrailService`: delete `assess_complexity` and the blocked-type patterns, add short-circuits and `classify_domain`.
4. Rewire the graph: new node set, new state keys, delete `ner_enrichment`, `agentic_retrieval`, `sql_retrieval`, `retrieval` nodes and `src/chat_api/graph/agentic.py`, `src/shared/retrieval/agentic_loop.py`.
5. Strip NER from `source_assembly_node`, `ContextAssembler`, and `RAGOrchestrator`; delete `_execute_legacy` and `_vector_source`; delete `NERClient` if unreferenced.
6. Remove the retired settings; add `orchestrator_max_invocations` and `retrieval_deadline_seconds`. Deployments must drop `NER_CHAT_USE_GRAPH` and `NER_CHAT_AGENTIC_RETRIEVAL` env vars — unknown env vars are ignored by pydantic settings, so a stale var is inert rather than fatal, but it should be cleaned up.
7. Retarget the eval harness; regenerate baselines; record orchestrated-vs-baseline metrics in the change's verification.
8. Frontend audit for `source_type === 'ner'` tolerance.

**Rollback:** revert the deploy. There is no data migration and no persisted state shape change — stored conversation messages keep their existing `sources` payloads, including historical `ner` entries.

## Open Questions

- **ADR-007 needs superseding.** It commits the chatbot to a three-source RAG pipeline including live NER inference, and lists query complexity limits among the mandated guardrails. This design removes both. A new ADR should record: retrieval sources reduced to structured entity data and document search; orchestration centralised in a single planning agent; complexity limits replaced by orchestrator budgets; the guardrail redefined as a domain filter. All other ADR-007 compliance items stay in force.
- Which model/deployment backs the guardrail classifier — the main chat deployment, or a cheaper/faster one? Affects per-turn cost and the latency risk above. Defaulting to the main deployment unless a cheaper one is already provisioned.
- Should `orchestrator_max_invocations` differ from the retired `agentic_max_tool_calls` default of 6? Proposed 3, since there is no re-plan round to spend invocations on.
- Does `NERClient` have consumers outside `RAGOrchestrator`? Determines whether step 5 deletes the module or only the chat wiring.
- Do any persisted conversation messages in production carry `source_type="ner"` sources that the portal renders through a code path that would break if the field set changes? The schema is unchanged, so this is expected to be a non-issue, but it needs a look.
