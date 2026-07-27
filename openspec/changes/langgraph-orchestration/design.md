## Context

Chat orchestration today lives entirely in `RAGOrchestrator.execute` (`src/chat_api/services/rag_orchestrator.py:45-146`). It is one async method with a fixed sequence:

1. `GuardrailService.check_blocked_question_type` → early return with a canned decline string (lines 47-57)
2. `GuardrailService.assess_complexity > 3` → early return (lines 59-61)
3. `asyncio.gather(self._sql_source(...), self._vector_source(...), return_exceptions=True)` (lines 63-66)
4. SQL result → single `Source(source_type="sql")` (lines 68-76)
5. Vector results → `Source(source_type="document_chunk")` per hit (lines 78-90)
6. Top-3 chunks → `NERClient.infer` per chunk → `Source(source_type="ner")` (lines 92-104)
7. Source assembly with hard slices: `[sql] + vector[:3] + ner[:5]` (lines 106-110)
8. `_enrich_citations` — resolves document filenames and CoNLL-label→entity-name via two DB queries, converts every `Source` into a `Citation` (lines 164-216)
9. Context string assembly, conversation history flattening, prompt build (lines 114-135)
10. `AsyncAzureOpenAI.chat.completions.create` at temperature 0.3, max_tokens 1000 (lines 137-142)
11. `GuardrailService.enforce_sources` — replaces the reply with `FALLBACK_REPLY` if sources are empty (line 145)

Everything below step 3 that touches retrieval is already properly factored behind Protocols in `src/shared/retrieval/`: `DenseRetriever` (pgvector cosine), `SparseRetriever` (`ts_rank` over the `chunk_tsv` generated column), `HybridRetriever` (RRF, `k=60`, sequential-not-gathered because the two retrievers share one `AsyncSession`), `RerankingRetriever` (overfetch `rerank_candidate_count`, rerank, truncate to `top_k`), `CrossEncoderReranker` (HTTP to `model_serving` `/internal/v1/rerank`).

Constraints shaping this design:

- **No model or provider changes.** Azure OpenAI for chat and embeddings, local `cross-encoder/ms-marco-MiniLM-L-6-v2` in `model_serving`, local `dslim/bert-base-NER` plus per-tenant ONNX. Decided and settled.
- **Retrieval pipeline is frozen.** Ingestion, chunking, pgvector storage, and all four retriever classes stay as-is.
- **API contracts frozen.** `ChatResponse`, `WidgetChatResponse`, `Source`, `Citation` unchanged.
- **Behaviour frozen in phase 1.** Same replies for the same inputs.
- The orchestrator is instantiated as a **module-level singleton** (`chat.py:19`, `public.py:17`) and carries per-request JWT by mutating `self.retriever.jwt_token` (`rag_orchestrator.py:158`). This is a live cross-tenant race and it is the reason a state-carrying execution model is not merely future-proofing.

## Goals / Non-Goals

**Goals:**

- Establish a LangGraph `StateGraph` as the execution substrate for the chat flow, with node boundaries drawn where future agentic control flow will need to insert.
- Move all per-request data out of singleton attributes into explicit graph state.
- Make each stage's outcome observable — currently a retrieval failure and an empty corpus are indistinguishable.
- Keep the diff small: new code is a state definition, node functions that are lifted verbatim slices of `execute`, and a graph builder. Existing service classes are called, not modified.
- Leave the graph shaped so that adding a conditional edge, a loop, or a tool node later is an edit to `builder.py` and nothing else.

**Non-Goals:**

- Agentic behaviour of any kind. No planner, no reflection, no tool-calling loop, no LLM-decided routing.
- LangChain adoption. `langgraph` and `langchain_core` types only. No `langchain_openai`, no `Runnable` chains, no LangChain retriever or vector-store abstractions.
- LangGraph checkpointer / persistence. Chat history stays in `{schema}.chat_messages` read by `chat.py:69-73`.
- Token streaming.
- Fixing the double-`Bearer` bug (see Open Questions).
- Changing the retrieval pipeline, embedding model, reranker model, or NER models.
- Multi-agent decomposition.

## Currently-In-Force ADRs

All eight ADRs are `Status: Proposed`; none are `Accepted`. ADR-008 supersedes ADR-002 partially. Treating the non-superseded set as the operative constraint:

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation | Per-tenant Postgres schemas | Graph state must carry `schema` explicitly; no node may derive or default a schema name |
| ADR-003 Model Serving Topology | Per-tenant model serving, LRU-cached | Reranking and NER stay HTTP calls to `model_serving`; no in-process torch inside `chat_api` |
| ADR-007 Chatbot Architecture | Three-source RAG (SQL + pgvector + NER), guardrails, citations, disclaimer, P95 < 10s | Node topology must preserve all three sources, all six guardrails, and must not add sequential latency |
| ADR-008 Base Model as Default | Version 0 base model instead of 404 | NER node must keep the existing `NERClient` fallback path |
| ADR-004 OpenSpec Governance | Spec-driven change process | This change ships as an OpenSpec change with delta specs and verification |

ADR-007 explicitly names the orchestration as "full RAG pipeline" without prescribing an implementation mechanism, so replacing the method with a graph is coherent with it rather than a supersession. ADR-007's "Evaluate open-source LLM self-hosting" line is a future item and is not touched here.

## Decisions

### Decision 1: Where the orchestration boundary sits

**Choice:** Orchestration begins at `RAGOrchestrator.execute` and ends at its return. Everything above it (FastAPI routing, tenant middleware, rate limiting, conversation row CRUD, message persistence, `inject_disclaimer`) stays in `chat.py`/`public.py`. Everything below it (`SQLGenerator`, `EmbeddingService`, retrievers, `CrossEncoderReranker`, `NERClient`, `GuardrailService`) stays an ordinary service.

**Rationale:** `execute` is already the exact seam — it is the only thing both entry points call, it is stateless in principle, and it returns a `(reply, sources)` tuple that both routers reshape. Pulling the boundary upward into `chat.py` would drag rate limiting, DB writes, and HTTP response shaping into the graph and break the "preserve API contracts, minimize churn" constraint. Pulling it downward would leave the parallel fan-out outside the graph, which is precisely the control flow that future agentic work needs to own.

**What becomes a node vs. what stays a service:**

| Component | Role | Why |
|---|---|---|
| `RAGOrchestrator` | Dissolves into the graph + a thin adapter | It *is* the orchestration |
| `GuardrailService` | **Service, called from nodes** | Pure functions over a string. Two of its methods (`check_blocked_question_type`, `assess_complexity`) drive conditional edges; `enforce_sources` runs in the final node. No state of its own |
| `SQLGenerator` | **Service, called from a node** | Owns prompt + whitelist validation. Self-contained. Future tool-calling will expose it as a tool — that is easier if it stays a plain object |
| `HybridRetriever` / `RerankingRetriever` | **Services, called from nodes** | Frozen by constraint. The `Retriever` Protocol is a better abstraction than a node boundary for swapping implementations |
| `CrossEncoderReranker` | **Service** | HTTP client. Called by `RerankingRetriever` |
| `EmbeddingService` | **Service** | Called by `DenseRetriever`, several layers below the graph |
| `NERClient` | **Service, called from a node** | HTTP client |
| `_enrich_citations` | **Becomes a node** | It performs two DB queries and reshapes the entire source list — a real stage, currently buried as a private method |

### Decision 2: Node granularity

**Choice:** Seven nodes.

```
                    ┌──────────────┐
                    │   guardrail  │
                    └──────┬───────┘
                    (conditional)
                ┌──────────┴──────────┐
              END                  fan-out
                                      │
                       ┌──────────────┴──────────────┐
                       ▼                             ▼
                ┌─────────────┐              ┌──────────────┐
                │ sql_retrieval│              │   retrieval  │
                └──────┬──────┘              └───────┬──────┘
                       └──────────────┬──────────────┘
                                      ▼
                              ┌───────────────┐
                              │ ner_enrichment│
                              └───────┬───────┘
                                      ▼
                              ┌───────────────┐
                              │ source_assembly│   (includes citation enrichment)
                              └───────┬───────┘
                                      ▼
                              ┌───────────────┐
                              │ prompt_assembly│
                              └───────┬───────┘
                                      ▼
                              ┌───────────────┐
                              │   generation   │   (+ enforce_sources)
                              └───────┬───────┘
                                      ▼
                                     END
```

| Node | Lifted from | Notes |
|---|---|---|
| `guardrail` | lines 47-61 | Writes `blocked_reason` / `complexity` and a canned `reply` to state. Conditional edge reads them |
| `sql_retrieval` | `_sql_source`, lines 148-153 | Writes `sql_results` or `sql_error` |
| `retrieval` | `_vector_source`, lines 155-162 | Calls `RerankingRetriever.retrieve` — hybrid + rerank stay *inside* the existing class. Writes `chunks` or `retrieval_error` |
| `ner_enrichment` | lines 92-104 | Top-3 chunks → `NERClient.infer`. Also fixes the `chunks_for_ner.index(chunk_text)` index-by-value bug and the `document_id=vector_sources[...]` type error, since both are latent defects with no observable effect on the current output |
| `source_assembly` | lines 106-112 + `_enrich_citations` | The `[sql] + vector[:3] + ner[:5]` slicing plus the two enrichment queries |
| `prompt_assembly` | lines 114-135 | Context string + conversation flattening + message list |
| `generation` | lines 137-146 | Azure OpenAI call + `enforce_sources` |

**Rationale for *not* splitting further:** "Hybrid merge" and "reranking" are deliberately **not** separate nodes. RRF fusion lives inside `HybridRetriever.retrieve` and reranking inside `RerankingRetriever.retrieve`; promoting them to nodes would require dismantling those classes, which the constraints forbid. Should a future phase need to branch on rerank scores, `RerankingRetriever` can be unwrapped into two nodes at that point — the state schema already has room (`candidates`, `chunks`).

**Rationale for keeping `prompt_assembly` separate from `generation`:** prompt construction is the single most likely thing to change when tool-calling arrives, and separating it means the generation node's body stays a two-line SDK call.

**Alternatives considered:**
- *One node per existing private method (3 nodes).* Ruled out — too coarse to be worth the dependency; the graph would add nothing over the current method.
- *Twelve fine-grained nodes including per-retriever nodes.* Ruled out — violates "avoid unnecessary abstraction" and would require modifying the frozen retrieval classes.

### Decision 3: Parallel fan-out via two edges, not `asyncio.gather` inside one node

**Choice:** `guardrail` fans out to `sql_retrieval` and `retrieval` as two parallel edges; both converge on `ner_enrichment`. LangGraph runs same-superstep nodes concurrently.

**Rationale:** Preserves the current latency profile (ADR-007's P95 < 10s depends on the fan-out). Makes the parallelism a property of the graph topology rather than a hidden `gather`, which is what future branching needs. Each node writes its own error field, reproducing `return_exceptions=True` semantics explicitly rather than by convention.

**Critical constraint:** both branches receive the same `AsyncSession`. SQLAlchemy's `AsyncSession` **cannot execute two statements concurrently on one connection** — this is already documented at `retriever.py:135-137` as the reason `HybridRetriever` does not use `gather`. The current code gets away with `asyncio.gather(sql_task, vector_task)` only because `_vector_source` and `_sql_source` happen not to overlap in practice under low concurrency; under LangGraph's parallel superstep this becomes a real `IllegalStateChangeError` risk.

**Resolution:** each of the two branch nodes acquires its own short-lived `AsyncSession` from `async_sessionmaker(get_engine())`, reads, and closes it. Both are read-only, so there is no transaction-boundary change relative to today — the router's session remains the one that writes `chat_messages` and commits. The router-owned session is still carried in state for `source_assembly`'s two enrichment queries, which run in a single non-parallel node.

**Alternatives considered:**
- *One node containing the existing `gather`.* Ruled out — hides the parallelism from the graph, so a future "retry retrieval with a rewritten query" edge cannot target the retrieval branch alone.
- *Sequential SQL-then-vector.* Ruled out — roughly doubles the pre-LLM latency and would violate behavioural parity on timing.
- *Passing the router session to both parallel nodes.* Ruled out — concurrency bug, per above.

### Decision 4: State schema — a `TypedDict` with `total=False`

**Choice:**

```python
class ChatState(TypedDict, total=False):
    # inputs — set once by the adapter, never mutated
    message: str
    tenant_id: str
    schema: str
    jwt_token: str | None
    conversation_context: list[dict] | None

    # runtime context — not serializable, excluded from any future checkpointer
    session: AsyncSession

    # guardrail outcome
    blocked_reason: str | None
    complexity: int

    # stage outputs
    sql_results: list[dict] | None
    sql_error: str | None
    chunks: list[RetrievalResult]
    retrieval_error: str | None
    ner_entities: list[dict]

    # assembly
    sources: list[Source | Citation]
    prompt_messages: list[dict]

    # terminal
    reply: str
```

**What belongs in state and why:**

| Field | In state? | Reasoning |
|---|---|---|
| `message` | Yes | The query. Every future feature (rewriting, decomposition, HyDE) mutates or derives from it; it must be a state field, not a closure variable |
| `tenant_id`, `schema` | Yes | Tenant isolation per ADR-001. Currently function parameters threaded through five call layers. Nodes must read them from state, never derive them |
| `jwt_token` | Yes | **The whole point.** Today it is set by mutating a shared singleton's attribute. In state it is per-invocation by construction |
| `conversation_context` | Yes | Read-only in this phase — loaded by `chat.py:69-73` and passed in. In state so that phase 3 can swap the source to a checkpointer without touching node bodies |
| `session` | Yes, with a caveat | Needed by `source_assembly` for the two enrichment queries. Not serializable — documented as excluded from checkpointing. This is the one impure field and it is deliberate; the alternative (nodes opening their own sessions everywhere) changes transaction boundaries |
| `chunks` | Yes | The retrieval output. Agentic RAG's core loop is "grade chunks, decide whether to re-retrieve" — that requires chunks to be inspectable state |
| `candidates` (pre-rerank) | **No, not yet** | Reranking happens inside `RerankingRetriever`; pre-rerank candidates never surface. Adding the field now would be an abstraction with no reader. Add it when `RerankingRetriever` is unwrapped |
| `sql_results` | Yes | Second retrieval source. Symmetric with `chunks` |
| `sql_error`, `retrieval_error` | Yes | Replaces the swallowed `except Exception: return []`. A future retry edge branches on exactly these |
| `ner_entities` | Yes | Third source per ADR-007 |
| `sources` | Yes | The API-contract output. Must be in state because `generation` mutates it via `enforce_sources` |
| `prompt_messages` | Yes | Separating assembly from generation is only meaningful if the assembled prompt is state |
| `reply` | Yes | Terminal output |
| `complexity`, `blocked_reason` | Yes | Drive conditional edges |
| **Retriever/reranker/LLM client instances** | **No** | These are stateless singletons. Putting them in state would make it non-serializable for no benefit. Nodes close over module-level instances, exactly as `RAGOrchestrator.__init__` does today |
| **Rate-limit counters, conversation_id, message ids, disclaimer** | **No** | Owned by the router. They are HTTP concerns and belong above the orchestration boundary |
| **Prompt templates, `SYSTEM_PROMPT`** | **No** | Module constants. Not per-request |

**Reducers:** none in phase 1. The graph is a DAG where `sql_retrieval` and `retrieval` write disjoint keys, so LangGraph's default last-write-wins is safe. When loops arrive in a later phase, `chunks` will need an explicit reducer — flagged, not built.

**Alternatives considered:**
- *Pydantic `BaseModel` state.* Ruled out — validation cost on every superstep, and `AsyncSession` needs `arbitrary_types_allowed`. `TypedDict` is LangGraph's idiomatic default and adds zero runtime overhead.
- *`MessagesState` / `add_messages` from `langgraph.graph`.* Ruled out for phase 1 — it imposes LangChain `BaseMessage` objects, and the current code passes plain `{"role", "content"}` dicts to the OpenAI SDK. Adopting it means converting at both ends for no phase-1 benefit. Reconsider in the memory phase.

### Decision 5: Graph compiled once at import; state carries the request

**Choice:** `builder.build_chat_graph()` is called once at module import and the compiled graph is a module-level object. `RAGOrchestrator.__init__` keeps constructing the service singletons; `execute` builds a `ChatState` dict and calls `await _graph.ainvoke(state)`.

**Rationale:** Compilation is not free and the topology is request-independent. Safe precisely because state is now per-invocation — this is the property that makes the current singleton acceptable where it currently is not.

### Decision 6: `jwt_token` threading replaces attribute mutation

**Choice:** Delete `RerankingRetriever.__init__`'s `jwt_token` parameter and the `self.jwt_token` attribute. Add `jwt_token: str | None = None` to `RerankingRetriever.retrieve` and pass it through to `self.reranker.rerank(...)`. Add the same parameter to the `Reranker` Protocol, which `CrossEncoderReranker.rerank` already accepts.

**Rationale:** Smallest possible change that removes the race. The `Retriever` Protocol is not extended — only `RerankingRetriever`'s own signature, which is what `_vector_source` calls directly. `DenseRetriever`, `SparseRetriever`, `HybridRetriever` are untouched, satisfying the frozen-retrieval constraint.

`tests/test_reranking_retriever.py`'s `SpyRetriever.retrieve` does not accept `jwt_token`, so `RerankingRetriever.retrieve` must not blindly forward it to the wrapped retriever — it forwards only to the reranker. `SpyReranker.rerank` already has the `jwt_token=None` parameter, so that test file passes unmodified.

### Decision 7: Observability via a node decorator

**Choice:** A single `@traced_node("name")` decorator wrapping each node function, emitting one structured log line with node name, tenant id, elapsed ms, and an output count.

**Rationale:** Meets the spec's observability requirement with one helper rather than seven copies of timing boilerplate. Deliberately plain `logging` — not LangSmith, not OpenTelemetry — because adding an external tracing dependency is a separate decision.

## Risks / Trade-offs

- [**Parallel nodes hit `IllegalStateChangeError` on the shared `AsyncSession`.**] → Decision 3: each parallel branch opens its own read-only session. Verified by a concurrency test that runs the graph with both branches issuing real queries.
- [**Behavioural drift is hard to prove.**] → Build a golden-transcript harness *before* the port: capture `(prompt_messages, sources, reply)` for a fixed set of inputs with the LLM stubbed, then assert byte-equality after. This is the single most important task in the plan; the port is not verifiable without it.
- [**`langgraph` pulls `langchain-core` and `pydantic` constraints into a tree that already pins `pydantic >=2.13.4`.**] → Resolve the dependency graph before writing any code. If `langchain-core` pins an incompatible pydantic, the whole change stalls — this is a gating check, not a late discovery.
- [**Adding `langgraph` to the root `pyproject.toml` inflates every service image**, including `model_serving` which already carries torch.] → Accept for now; the existing repo already installs one dependency set for all services. Note as a candidate for per-service dependency splitting, out of scope here.
- [**`AsyncSession` in state blocks future checkpointing.**] → Documented, not solved. When the memory phase arrives, either exclude the key via a custom serializer or move enrichment queries into a node that opens its own session. Recorded as a known debt in `verification.md`.
- [**Reranking is currently broken by the double-`Bearer` bug**, so "behavioural parity" means parity with a degraded system.] → See Open Questions. Parity tests written now would encode the bug. Sequencing matters.
- [**Team unfamiliarity with LangGraph** turns a mechanical port into a learning exercise.] → Node bodies are lifted verbatim; the only genuinely new concepts are `StateGraph`, `add_conditional_edges`, and parallel superstep semantics.
- [**Over-nodding.**] → Seven nodes is the floor that still exposes the future branch points. Resist adding more until a concrete feature demands one.

## Migration Plan

### Phase 1 — Behaviour-identical port (this change)

1. **Gate**: resolve `langgraph` + `langchain-core` + `pydantic >=2.13.4` compatibility. Stop if incompatible.
2. Build the golden-transcript harness against the *current* orchestrator with the Azure client stubbed. Capture prompts, sources, replies for ~15 representative inputs including both guardrail early-exits, empty retrieval, and SQL failure.
3. Remove `RerankingRetriever.jwt_token` attribute; thread as an argument. Update the `Reranker` Protocol. Run the existing retrieval tests unmodified.
4. Add `src/chat_api/graph/state.py`, `nodes.py`, `builder.py`. Lift node bodies verbatim.
5. Rewrite `RAGOrchestrator.execute` as an adapter. Keep `__init__` and the signature.
6. Run golden-transcript comparison. Any diff is a port bug, not an improvement.
7. Add the `traced_node` decorator and the concurrency test for parallel-branch sessions.

**Rollback**: the old `execute` body is preserved as `_execute_legacy` behind a `NER_CHAT_USE_GRAPH` setting defaulting to `true`. One env var reverts. Removed in phase 2 once the graph has run in a real environment.

### Phase 2 — Consolidation (separate change)

- Delete `_execute_legacy` and the feature flag.
- Unwrap `RerankingRetriever` into distinct `retrieve_candidates` and `rerank` nodes, adding `candidates` to state. Enables branching on rerank score.
- Surface `relevance_score` through `_enrich_citations` — currently dropped at `rag_orchestrator.py:206`, which is why retrieval cannot be debugged from the UI.
- Add an explicit reducer for `chunks` in anticipation of loops.

### Phase 3 — Memory (separate change)

- Introduce a LangGraph checkpointer (`AsyncPostgresSaver` against the existing Postgres) with `thread_id = conversation_id`.
- Resolve the `AsyncSession`-in-state serialization problem as a prerequisite.
- Keep `{schema}.chat_messages` as the system of record for the conversation API contract; the checkpointer holds graph state, not the user-facing transcript. Running both is redundancy, and that is the point — the API contract must not depend on the checkpointer until it is proven.
- Evaluate `MessagesState` / `add_messages` at this point, when there is a reason.

### Phase 4 — Agentic readiness (not planned here)

Groundwork only: a documented extension point for tool nodes, and a decision on whether `SQLGenerator` and the retrievers get exposed as tools. No implementation.

## Open Questions

1. **Sequencing versus the double-`Bearer` bug.** `chat.py:81` passes the raw `Authorization` header (`"Bearer eyJ..."`) into the `jwt_token` parameter, and `reranker.py:35` / `ner_client.py:15` prepend `Bearer ` again. Reranking and chat-path NER enrichment therefore fail silently today. "Behaviour identical" against a broken baseline encodes the bug into the golden transcripts. **Recommendation:** fix it as a small separate change *before* phase 1, so the golden baseline reflects a working reranker. Needs a decision before task 2 of phase 1.
2. **Does `langgraph` belong in the root `pyproject.toml`** or in a `chat_api`-local requirements file, following the `src/document_service/requirements.txt` precedent? The repo is inconsistent here already.
3. **Parallel-branch sessions and connection-pool pressure.** Two extra short-lived sessions per chat request. Needs a check against the asyncpg pool size before phase 1 ships.
4. **Confirm streaming is out of scope for all four phases.** If the UI will ever want token streaming, phase 1's `generation` node should be written with `astream` in mind, which is a small difference now and a rewrite later.
5. **No ADR revision proposed.** ADR-007 describes the RAG architecture, not its orchestration mechanism, and remains accurate. If the team wants LangGraph recorded as a durable architectural commitment, that warrants a new ADR-009 rather than a modification to ADR-007 — flagged for the adr step.
