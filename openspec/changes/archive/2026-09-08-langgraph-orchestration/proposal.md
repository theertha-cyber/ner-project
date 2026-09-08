## Why

`RAGOrchestrator.execute` (`src/chat_api/services/rag_orchestrator.py`) is a single 100-line async method that hard-codes the entire chat flow: guardrail gate, parallel SQL + vector fan-out, NER enrichment, citation enrichment, prompt assembly, LLM call. Every future capability on the roadmap — agentic RAG, multi-step reasoning, tool calling, durable memory, human-in-the-loop, branching — requires control flow that a straight-line method cannot express without being rewritten. Introducing LangGraph now, while the flow is still linear and behaviour is frozen, is a low-risk port; introducing it after agentic features are hand-rolled is a rewrite.

Two defects found during audit make the current shape actively hostile to those features: the orchestrator is a module-level singleton (`chat.py:19`, `public.py:17`) whose per-request JWT is smuggled in by mutating `self.retriever.jwt_token` (`rag_orchestrator.py:158`) — a cross-tenant race under concurrency; and per-stage failures are swallowed into `[]` with no trace (`rag_orchestrator.py:160`), so retrieval quality cannot be observed. Both are fixed for free by making per-request data flow through explicit graph state.

## What Changes

- Add `langgraph` (and its `langchain-core` transitive dependency) to `pyproject.toml`. No LangChain model wrappers, no `langchain-openai` — existing `AsyncAzureOpenAI` clients are called directly from inside nodes.
- Add `src/chat_api/graph/` containing a `ChatState` TypedDict and a `StateGraph` whose nodes wrap the *existing* service objects. Nodes contain no new logic; each node body is lifted verbatim from a slice of `RAGOrchestrator.execute`.
- `RAGOrchestrator.execute` becomes a thin adapter: build initial state, `await graph.ainvoke(state)`, return `(reply, sources)`. Its signature and return type are unchanged, so `chat.py:81` and `public.py:179` are untouched.
- Per-request values (`jwt_token`, `tenant_id`, `schema`, `session`) move from instance attributes into graph state. `RerankingRetriever.jwt_token` mutation is removed; `jwt_token` is passed as a `rerank()` argument instead. Fixes the concurrency bug as a side effect.
- Node-level structured logging: each node logs entry, output cardinality, and duration. Replaces the current silent `except Exception: return []`.
- Behaviour is byte-identical: same guardrail decisions, same decline strings, same fan-out concurrency, same prompt text, same `ChatResponse` payload. Existing tests pass unmodified.
- No agentic behaviour. No conditional edges beyond the two that already exist implicitly (guardrail block → END, complexity > 3 → END). Graph is a fixed DAG in this change.

## Capabilities

### New Capabilities

- `chat-orchestration-graph`: LangGraph `StateGraph` as the execution framework for the chat RAG flow — state schema, node boundaries, edge topology, per-request state isolation, and node-level observability. Defines what the graph must guarantee (behavioural parity, no shared mutable per-request state, traceable stage outcomes).

### Modified Capabilities

- `chat-api`: no requirement changes to request/response contracts, but the spec gains a requirement that per-request authorization context must not be carried on shared service instances — currently violated. Delta spec covers that requirement only.

## Impact

**Code**
- `src/chat_api/services/rag_orchestrator.py` — reduced to an adapter over the graph.
- `src/chat_api/graph/` — new: `state.py`, `nodes.py`, `builder.py`.
- `src/shared/retrieval/retriever.py` — `RerankingRetriever.jwt_token` constructor/attribute removed; `jwt_token` threaded as a `retrieve()` argument. Touches `HybridRetriever`/`DenseRetriever`/`SparseRetriever` signatures only if the `Retriever` Protocol is extended; preferred alternative is passing `jwt_token` into `RerankingRetriever.retrieve` directly.
- `src/shared/retrieval/reranker.py` — `Reranker` Protocol updated to declare `jwt_token`, which `CrossEncoderReranker` already accepts. Protocol/implementation drift closed.
- `src/chat_api/api/v1/chat.py`, `public.py` — orchestrator instantiation only; call site unchanged.

**Unchanged by construction**: document ingestion, chunking, embedding generation, pgvector storage, `DenseRetriever`, `SparseRetriever`, `HybridRetriever`, `CrossEncoderReranker`, `model_serving`, Azure OpenAI chat, Azure embeddings, `SQLGenerator`, `GuardrailService`, `NERClient`, all HTTP contracts, all DB schemas.

**Dependencies**: `langgraph` added to the root `pyproject.toml`. It is imported only by `chat_api`; other services pay an install cost but no runtime cost. Adds `langchain-core` and `langgraph-checkpoint` to the dependency tree.

**Tests**: `tests/test_chat_api_rag.py`, `test_hybrid_retrieval.py`, `test_reranking_retriever.py`, `test_reranker_client.py` must pass unmodified. `test_reranking_retriever.py`'s `SpyReranker.rerank(..., jwt_token=None)` already matches the corrected Protocol.

**Not in scope**: LangGraph checkpointers / persistence. Chat history stays in `{schema}.chat_messages`, loaded by `chat.py:69-73` and passed in as `conversation_context` exactly as today. Migrating to a LangGraph checkpointer is a later phase.

## Open Questions

1. **Node granularity for the fan-out.** The current `asyncio.gather(sql_task, vector_task)` maps naturally to two parallel LangGraph nodes from a common entry. Confirm parallel-node execution is preferred over one node that internally keeps the `gather` — parallel nodes are more future-ready but change how a partial failure surfaces. Assumption: use parallel nodes, and reproduce `return_exceptions=True` semantics by having each node write its own error field to state.
2. **`AsyncSession` in graph state.** A live SQLAlchemy session is not serializable, which blocks any future checkpointer that persists state. Assumption for this phase: carry the session in a non-serializable `context` slot and accept that checkpointing requires excluding it. Alternative — nodes acquire their own sessions — changes transaction boundaries and is therefore out of scope here.
3. **Whether to fix the double-`Bearer` bug in this change.** `chat.py:81` passes the raw `Authorization` header value into a parameter that `reranker.py:35` and `ner_client.py:15` re-prefix with `Bearer `. Reranking and chat-path NER enrichment are therefore currently non-functional. Fixing it changes observable behaviour (reranking starts working), which conflicts with "behaviour identical". Assumption: fix it in a *separate* change immediately before or after this one, so parity testing has a stable baseline.
4. **Streaming.** LangGraph supports token streaming; the current `ChatResponse` is a single JSON body. Confirm streaming is out of scope for all phases described here.
