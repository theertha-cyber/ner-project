## Context

The chat flow is a fixed DAG compiled by `build_chat_graph` (`src/chat_api/graph/builder.py`): `guardrail` → (`sql_retrieval` ‖ `retrieval`) → `ner_enrichment` → `source_assembly` → `prompt_assembly` → `generation`. Both retrieval nodes fire exactly once, with the user's raw message as the query and `settings.retrieval_top_k` as the bound. There is no mechanism to issue a second, differently-phrased query, to scope a follow-up search to a document discovered in the first pass, or to consult entity data only when the first pass suggests it is needed.

Two prior changes built the substrate. `langgraph-orchestration` moved the flow into a `StateGraph` with per-request state (`ChatState`) and per-node structured logging, deliberately forbidding loops and tool-calling nodes so the migration could be proven behaviour-identical. `retrieval-tools-and-eval` added `src/shared/retrieval/tools/` — a `RetrievalTool` protocol, a `ToolContext` frozen dataclass carrying `tenant_id`/`schema`/`session`/`retriever`/`jwt_token`/`sql_search`, a `ToolResult` envelope with `latency_ms`/`degraded`/`error`, a `ToolRegistry` whose `export_schemas()` already emits `{"type": "function", "function": {...}}`, and three tools (`search_documents`, `lookup_document`, `search_entities`). It also added a golden-set eval harness with `recall@k`/`MRR@k`/`nDCG@k`/`precision@k` and a committed baseline. The tool layer has one consumer today: that harness.

Constraints shaping this design. Tenant isolation is schema-based and must remain unreachable from LLM-supplied arguments (ADR-001) — this is sharper here than in the eval harness, because tool arguments are now chosen by a model reading tenant document text. ADR-007 fixes the three-source RAG structure, mandates that SQL go through the validation layer, requires citation enforcement, and sets a P95 < 10s latency target that a multi-iteration loop directly threatens. The reranker is an HTTP hop into `model_serving` (ADR-003), so every extra retrieval call in a loop is another network round trip on CPU. And `RAGOrchestrator` is a module-level singleton in `chat.py` and `public.py`: nothing request-scoped may be stored on it.

## Goals / Non-Goals

**Goals:**

- Multi-step retrieval: the model can reformulate a query, follow a lead into a specific document, and consult entity data, within one chat turn.
- Hard bounds on iterations, tool calls, and wall-clock time, so the worst case stays inside the ADR-007 latency target.
- Zero disturbance to everything downstream of retrieval — NER enrichment, source assembly, citations, prompt assembly, generation, and both HTTP response contracts stay as they are.
- Reversible in production without a deploy, and identical to today's behaviour when off.
- Enabling the loop is a measured decision, scored on the existing golden set against the one-shot configuration.

**Non-Goals:**

- New retrieval strategies (HyDE, multi-query expansion, standalone query rewriting). The loop composes existing tools; it adds no ranking or fusion logic.
- Checkpointing, resumable runs, or human-in-the-loop interrupts.
- Streaming intermediate loop steps to the portal.
- Answer-quality / LLM-as-judge evaluation. This change is still measured on *retrieval* metrics.
- Replacing `_execute_legacy`, or any change to ingestion, chunking, or embeddings.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Per-tenant PostgreSQL schemas, `search_path` enforcement, prefix-isolated object storage | Tenant scope must stay in `ToolContext`, derived from authenticated request state. No loop-supplied argument may influence which schema is queried, even when the model was influenced by retrieved text. |
| ADR-003 Per-Tenant Model Serving Topology | Shared serving pool, tenant-aware routing, on-demand model loading | Reranking is an HTTP hop per retrieval call; N loop iterations mean N such hops. Budgets must be wall-clock, not just call-count, and reranker degradation must remain visible per call. |
| ADR-004 OpenSpec SDD Governance | Proposal → design → spec → tasks → evidence gates | Enabling the flag needs eval evidence, not argument. The loop's trace must be durable enough to serve as that evidence. |
| ADR-005 OpenCode Agent Permissions and Boundaries | Agent permission boundaries for repo automation | Concerns repo tooling, not runtime; no constraint on this design beyond keeping `src/shared` free of `src/chat_api` imports. |
| ADR-006 Training Infrastructure with Asynchronous GPU Workers | Async GPU training workers | No constraint — training path is untouched. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG (SQL + pgvector + NER), SQL validation layer, citation enforcement, P95 < 10s | The loop must not become a fourth source: it feeds the same `chunks` / `sql_results` state keys. `search_entities` must keep routing through the validated SQL path. The deadline budget must leave room for generation inside 10s. Guardrails still run before the loop and citations still run after it. |
| ADR-008 Base Model as Default Inference Model | Base model answers when no tenant model is promoted | No constraint — NER enrichment is unchanged. |

ADR-002 is partially superseded by ADR-008; neither constrains this design.

## Decisions

### Decision 1: One loop node, not a multi-node LangGraph cycle

**Choice:** The loop is a single node, `agentic_retrieval`, whose body runs the plan → dispatch → observe cycle internally. The graph gains one conditional edge after `guardrail` selecting between the loop node and today's parallel fan-out; the graph itself remains acyclic.

**Rationale:** A LangGraph cycle (`planner` → `tools` → conditional back to `planner`) would put loop bookkeeping — remaining budget, accumulated messages, dedup table — into `ChatState`, which is also the contract consumed by four downstream nodes and by every existing parity test. Keeping the cycle inside one node keeps `ChatState` additive-only (`tool_trace`, `agentic_degraded`, `agentic_stop_reason`) and keeps the flag-off topology provably identical to today's. The internal loop is a plain `for` over a bounded range — easier to test with a scripted fake client than a graph cycle, and the budget logic stays in one place.

**Alternatives considered:**
- True graph cycle with `planner`/`tools` nodes and a conditional edge — idiomatic LangGraph, but leaks loop state into the shared state contract and makes "flag off ⇒ identical topology" harder to assert. Revisit if checkpointing or interrupts are ever needed, which are explicit non-goals.
- A prebuilt agent executor (`langgraph.prebuilt.create_react_agent`) — brings an opinionated message/state schema and its own tool-binding path, conflicting with the in-force constraint that no LangChain model/retriever wrapper enters `src/chat_api`, and giving no control over budget semantics.

### Decision 2: The loop terminates on the first of four conditions, and budget exhaustion is a normal outcome

**Choice:** Stop when (a) the planner returns an assistant message with no tool calls, (b) the iteration count reaches `agentic_max_iterations`, (c) the cumulative tool-call count reaches `agentic_max_tool_calls`, or (d) `monotonic()` passes a deadline set at loop entry from `agentic_deadline_seconds`. The stop reason is recorded in `agentic_stop_reason`. In cases (b)–(d) the loop stops *without* a further planner call and hands the evidence collected so far to `ner_enrichment` unchanged.

**Rationale:** ADR-007's P95 < 10s is a wall-clock target, and neither iteration count nor tool count bounds wall-clock time — one reranked retrieval against a cold `model_serving` can dominate the whole budget. Checking the deadline before each planner call and before each tool dispatch bounds the overrun to one in-flight operation. Treating exhaustion as normal (not an error, not a fallback) matters because the downstream path already handles partial and empty evidence: `source_assembly` tolerates zero chunks, and `enforce_sources` already governs unsupported replies. A degraded-but-answered turn beats a failed turn.

**Alternatives considered:**
- Iteration cap only — unbounded latency under reranker slowness, in direct conflict with ADR-007.
- Asking the planner to "wrap up" when the budget runs low — an extra LLM call precisely when time is short.
- Hard-failing the turn on exhaustion — throws away usable evidence and produces a worse answer than the one-shot path it replaces.

### Decision 3: The loop writes the existing state keys; nothing downstream learns it exists

**Choice:** The accumulator merges every `search_documents` / `lookup_document` result into one `list[RetrievalResult]` deduplicated on `(document_id, chunk_index)` keeping the highest `similarity_score`, sorted descending, and writes it to `state["chunks"]`. `search_entities` rows are concatenated into `state["sql_results"]`. `retrieval_error` / `sql_error` are set only when *every* attempt of that kind errored.

**Rationale:** `ner_enrichment` (first 3 chunks), `source_assembly` (3 vector sources + 5 NER sources, then citation enrichment), `prompt_assembly`, and `generation` are all correct as written and are covered by tests that must keep passing. Reusing the keys means the entire citation pipeline — document-name resolution, entity-type mapping, `enforce_sources` — works with zero changes, and the loop is swappable against the one-shot path in eval by construction. Scores from different tool calls are comparable because every call goes through the same composed `Retriever` from `ToolContext`.

**Alternatives considered:**
- A new `evidence` state key with a richer per-item provenance record — forces rewrites of `source_assembly` and the citation logic, expanding the blast radius into the part of the system users see.
- Keeping per-iteration result lists un-merged and letting `prompt_assembly` flatten — pushes dedup into a node whose job is prompt formatting, and duplicated chunks would consume the top-3 source slots.

### Decision 4: Tenant scope stays in `ToolContext`; tool arguments are always validated and never trusted

**Choice:** The node builds `ToolContext` from `ChatState` (`tenant_id`, `schema`, a node-owned `AsyncSession`, `orchestrator.retriever`, `jwt_token`, `sql_search=orchestrator._sql_source`). Planner-produced arguments go through the existing `validate_args`, which rejects unknown keys; `assert_no_tenancy_params` already prevents any tool from declaring `schema`/`tenant_id`/`tenant`/`purpose`. Tool observations are appended as `role: "tool"` messages, and the planner system prompt states that observation content is evidence to be searched over, never instructions to follow.

**Rationale:** With a loop, retrieved tenant document text re-enters the model's context and can influence the *next* tool call — an injection path the one-shot pipeline does not have. Structural exclusion is the only durable defence: a `schema` parameter that does not exist in any `args_schema` cannot be injected regardless of what a document says. The `purpose = 'query'` filter already hard-coded in the retriever SQL is inherited unchanged, so training-purpose documents stay invisible to every iteration. Prompt-level instruction is defence in depth, not the boundary.

**Alternatives considered:**
- Allowing a `schema` argument validated against the JWT — one missed check is a cross-tenant leak, for no capability gain.
- Sanitizing chunk text before showing it to the planner — unreliable, and it would degrade the evidence the loop exists to gather.
- Constructing per-request tool objects bound to a schema — makes the registry request-scoped and schema export request-dependent, with no isolation benefit over context injection.

### Decision 5: Malformed tool calls get one corrective retry, then the loop degrades

**Choice:** An unknown tool name, unparseable arguments, or arguments failing validation produce an error `ToolResult` fed back to the planner as a `role: "tool"` observation, counting against the tool-call budget. If the immediately following planner turn produces another invalid call, the loop stops, sets `agentic_degraded`, and falls back to the one-shot path for that turn.

**Rationale:** `run_tool` already converts validation failures into error `ToolResult`s rather than raising, so a single correction is nearly free and models routinely self-correct on the next turn. Allowing unlimited retries turns a confused planner into a budget-consuming spin. Falling back rather than failing preserves the pre-change answer quality floor: with the loop broken, the turn is exactly as good as it is today.

**Alternatives considered:**
- Fail the turn on the first malformed call — a worse answer than the code we already ship.
- Unlimited retries within the tool budget — spends the entire budget on correction rounds with no retrieval.

### Decision 6: The complexity guardrail routes into the loop instead of declining, only when the flag is on

**Choice:** `guardrail_node` keeps blocked-question-type handling exactly as it is. For `assess_complexity(message) > 3`: with `chat_agentic_retrieval` off, the existing "please simplify" decline is returned unchanged; with it on, the turn proceeds into the loop and the complexity score raises the iteration budget to `agentic_max_iterations_complex`.

**Rationale:** The decline exists because one retrieval call cannot answer a multi-hop question — it encodes a limitation of the pipeline, not a policy. Once the pipeline can issue several calls, keeping the decline refuses exactly the questions the change was built for. Gating on the flag keeps flag-off behaviour bit-identical, which is what makes `tests/test_chat_api_guardrails.py` a meaningful regression check throughout.

**Alternatives considered:**
- Drop the complexity guardrail entirely — loses the flag-off safety property and the logged complexity signal.
- Keep the decline even with the loop on — leaves the loop only handling questions the one-shot path already handles, where its upside is smallest.

### Decision 7: The loop is scored on the existing golden set as another named configuration

**Choice:** `src/shared/retrieval/eval/runner.py` gains an `agentic` configuration that, per golden-set query, runs the loop against a scripted planner and scores the accumulated evidence with the same `recall@k` / `nDCG@k` functions used for one-shot configurations. The comparison against the best one-shot configuration is this change's exit criterion.

**Rationale:** The harness exists precisely so retrieval changes stop being justified by argument (ADR-004). The loop's output is a ranked chunk list over the same corpus, so it is directly commensurable with existing configurations at no metric cost. Making the loop's benefit visible as a number is also what makes the "ship it off, enable after evidence" rollout meaningful rather than ceremonial.

**Alternatives considered:**
- Judge the loop only on end-to-end answer quality — needs LLM-as-judge infrastructure that is an explicit non-goal, and would confound retrieval gains with generation behaviour.
- Skip eval and enable behind the flag with manual spot checks — the exact practice this project's eval harness was built to end.

## Risks / Trade-offs

- [Latency regression: N planner calls plus N reranked retrievals blow past the ADR-007 P95 < 10s target] → Wall-clock deadline checked before every planner call and every tool dispatch; defaults chosen so worst case leaves generation headroom; measure P95 with the flag on before enabling anywhere, and treat the flag as the rollback.
- [Token cost per turn grows roughly linearly with iterations, and every observation carries chunk text] → Cap observation size per tool call when rendering `ToolResult` into a message; cap tool calls, not just iterations; report per-turn planner token counts in the trace so cost is observable.
- [Prompt injection: a tenant document instructs the planner to call `lookup_document` on unrelated documents or to exfiltrate context] → Tenant scope is structurally absent from every `args_schema` (ADR-001 boundary holds regardless of planner behaviour); worst case is wasted budget inside the tenant's own corpus. Explicit injection-resistance scenarios in the spec and a test with a hostile chunk fixture.
- [The planner loops on near-identical queries, spending budget without new evidence] → Dedup by `(document_id, chunk_index)` makes repeats visibly unproductive in the trace; the tool-call cap bounds the waste; a repeated-identical-arguments check can be added if the trace shows it happening.
- [Fallback masks a systematically broken loop — degraded turns look fine to users while the loop never works] → `agentic_degraded` and `agentic_stop_reason` are in state and in the structured log, so degradation rate is measurable rather than silent.
- [Two flags (`chat_use_graph`, `chat_agentic_retrieval`) produce four combinations, only three of which are meaningful] → `chat_agentic_retrieval` is honoured only on the graph path; with `chat_use_graph` off, `_execute_legacy` runs unchanged and the loop flag has no effect. Asserted by test.
- [Nested LLM call: `search_entities` invokes SQL generation, so one tool call is itself a model round trip] → It counts against the tool-call budget and the deadline like any other call; the trace records its latency separately so its cost is attributable.
- [Session lifetime: the loop holds a database session across several LLM round trips] → The node opens its own session with `async_sessionmaker` as the existing retrieval nodes already do, and the deadline bounds how long it is held.

## Migration Plan

1. Ship with `chat_agentic_retrieval = false`. Verify `tests/test_langgraph_parity.py`, `tests/test_chat_api_rag.py`, and `tests/test_chat_api_guardrails.py` pass unmodified — flag-off behaviour is the current behaviour.
2. Run the retrieval eval matrix with the new `agentic` configuration against the committed baseline. Record `recall@5` / `nDCG@5` for the loop versus the best one-shot configuration in `verification.md`.
3. If the loop wins, enable in the local dev stack; measure P95 latency and per-turn planner token count over a realistic question set. Tune `agentic_max_iterations` / `agentic_deadline_seconds` from the measurement, not from the assumed defaults.
4. Enable per environment via the setting. Watch the degradation rate (`agentic_degraded`) and stop-reason distribution.
5. Rollback: set `chat_agentic_retrieval = false`. No migration, no data change, no redeploy required — the one-shot nodes are still present and are the fallback path.

## Open Questions

- Default budget values (`agentic_max_iterations`, `agentic_max_tool_calls`, `agentic_deadline_seconds`) are placeholders until step 3 of the migration plan measures them. The spec fixes the *semantics* of the budgets, not the numbers.
- Whether the planner should use a separate, cheaper deployment (`agentic_planner_model`) rather than `orchestrator.llm_model`. Deferred; adding the setting later is not a breaking change.
- Whether `search_entities` should be restricted to one call per turn given its nested LLM call. Left unrestricted initially so the trace can show whether the planner over-uses it.
- No in-force ADR needs revisiting for this change. ADR-007's P95 < 10s target is treated as binding and shapes the budget design rather than being relaxed. If step 3 shows the loop cannot meet it with useful budgets, that is the point to propose a superseding ADR — not before there is measurement.
