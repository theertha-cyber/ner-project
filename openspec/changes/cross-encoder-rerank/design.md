## Context

`src/shared/retrieval/retriever.py` currently defines a `Retriever` protocol plus `DenseRetriever`, `SparseRetriever`, and `HybridRetriever` (the latter two landing via `hybrid-retrieval-hnsw`, in progress at the time of writing). `RAGOrchestrator._vector_source` calls whichever `Retriever` instance it holds and passes results into `execute`, which truncates to `vector_sources[:3]` and `chunk_text[:500]` before building the LLM prompt — so retrieval ordering directly determines what the model sees, and anything ranked 4th or lower is discarded regardless of actual relevance.

`model_serving` already hosts transformer models. Critically, it does so two different ways: per-tenant fine-tuned ONNX models go through `ModelCache` (LRU, 2 GB budget, keyed by model version, loaded from MinIO per tenant), while the **tenant-agnostic** base NER model is held as a plain lazily-initialized module-level singleton (`_base_pipeline` in `inference_service.py`, loaded from the Hugging Face hub by name). A cross-encoder reranker is tenant-agnostic — one model, shared by every tenant, never versioned per tenant — so it belongs in the second category, not the first.

In-force ADRs constraining this design (supersession graph checked: ADR-008 partially supersedes ADR-002 for base-model fallback behavior only; ADR-003 explicitly noted as unchanged by ADR-008; all others in force):
- **ADR-001** (tenant data isolation) — no cross-tenant data access.
- **ADR-003** (per-tenant model serving topology) — shared serving pool, per-tenant routing and version pinning for *tenant* models.
- **ADR-007** (chatbot architecture) — three-source RAG, citations required, graceful degradation when a RAG source is unavailable, P95 < 10s.

## Goals / Non-Goals

**Goals:**

- Cross-encoder reranking of retrieved document chunks, served from the existing `model_serving` service.
- A `Reranker` abstraction and a `RerankingRetriever` that composes with *any* `Retriever` without modifying the `Retriever` protocol or `RAGOrchestrator._vector_source`.
- Graceful degradation: reranker unavailable ⇒ original retrieval order, never a failed chat request.
- Feature-flagged so it can be disabled without a code change.

**Non-Goals:**

- No new microservice — reranking is an endpoint on existing `model_serving`, not a separate deployment.
- No per-tenant reranker models, no reranker fine-tuning, no reranker version pinning. The reranker is a single global model; if per-tenant rerankers are ever wanted, that's a substantially different change (it would need registry integration and `ModelCache` participation).
- No reranking of the SQL/structured-entity source or the NER source — document chunks only.
- No ONNX conversion of the reranker in this change (see Decisions).
- No changes to embeddings, chunking, indexing, or ingestion.

## Decisions

**Reranking is a decorator (`RerankingRetriever`) wrapping a `Retriever`, not a stage baked into `HybridRetriever` or an explicit step in `RAGOrchestrator`.**
`RerankingRetriever` implements the `Retriever` protocol itself: it over-fetches `rerank_candidate_count` results from the wrapped retriever, reranks them, truncates to `top_k`, and returns them. Consequences: `RAGOrchestrator._vector_source` needs no change beyond which instance `self.retriever` is; reranking composes with `DenseRetriever`, `SparseRetriever`, or `HybridRetriever` interchangeably; and it can be removed or disabled by simply not wrapping.
Alternatives considered: (a) fold reranking into `HybridRetriever` — rejected, conflates fusion with reranking and makes reranking unavailable to non-hybrid retrievers; (b) an explicit rerank step inside `RAGOrchestrator.execute` — rejected, forces the orchestrator to know about reranking, and the planned `context-assembly-pipeline` change would then have to re-plumb it.
This choice also insulates the change from the two other in-flight retrieval changes (`hybrid-retrieval-hnsw`, `document-purpose-scoping`), both of which modify the *inside* of the concrete retrievers while this change only wraps them from the outside.

**The reranker model is a module-level lazy singleton in `model_serving`, following the `_base_pipeline` precedent — explicitly NOT registered in `ModelCache`.**
`ModelCache` exists to arbitrate a fixed memory budget (`model_cache_memory_limit_gb`, default 2 GB) between *many* per-tenant models with LRU eviction. Putting one always-needed global model into that pool would let tenant NER models evict the reranker (causing a multi-second reload mid-query) and would consume tenant-model budget. The existing base NER model already establishes the correct pattern for a shared, always-available, hub-loaded model.
Trade-off accepted: a singleton is never evicted, so it permanently occupies memory. This is why the default model must be small (below).

**Default model: `cross-encoder/ms-marco-MiniLM-L-6-v2`; the model name is configurable via `NER_RERANKER_MODEL`.**
`settings.training_device` defaults to `cpu` and `model_serving` has no GPU configured in the local compose stack. On CPU, a ~22M-parameter MiniLM cross-encoder scores ~20 candidate pairs in roughly the low hundreds of milliseconds and resides in well under ~100 MB — acceptable both for ADR-007's P95 < 10s budget and as a permanent resident alongside the 2 GB tenant-model budget. `BAAI/bge-reranker-v2-m3` (~568M params) would score meaningfully better but on CPU would add seconds per query and permanently occupy more memory than the entire per-tenant cache allowance. Making the name configurable means a GPU-backed deployment can opt into the larger model without a code change.
This resolves the proposal's first open question, with the CPU-default constraint as the deciding factor rather than raw quality ranking.

**Load via `transformers.AutoModelForSequenceClassification` + `AutoTokenizer`, not ONNX Runtime.**
ADR-003 specifies ONNX Runtime for *tenant* models, where conversion is already part of the training/promotion pipeline (there is an `onnx-conversion` capability for exactly that). A stock off-the-shelf reranker has no such pipeline, and adding a conversion step for it would be new machinery for an optimization that isn't needed at the chosen model size. `transformers` and `torch` are already dependencies, so this adds no new package. ONNX conversion of the reranker remains available later as a pure optimization if reranking latency becomes a bottleneck — noted as a Non-Goal, not a rejected idea.

**Endpoint `POST /internal/v1/rerank` on `model_serving`, called via a `CrossEncoderReranker` HTTP client that mirrors the existing `NERClient`.**
Keeps model hosting in the one service that owns transformer models (and therefore the memory, warmup, and eventual GPU concerns), rather than loading a transformer inside `chat_api`. The client mirrors `src/chat_api/services/ner_client.py`'s shape — `httpx.AsyncClient`, bearer JWT forwarding, timeout, exception-to-`None` handling — so the failure semantics are already familiar in this codebase.
The endpoint sits behind the app-wide `TenantContextMiddleware` like every other `model_serving` route, so it still requires a valid JWT. **ADR-001 note:** although the reranker *model* is shared across tenants, the endpoint is stateless with respect to tenancy — it scores only the candidate texts supplied in the request body, which are the caller's own already-retrieved chunks. It reads no tenant storage and holds no cross-request state, so no cross-tenant data path is introduced.

**Graceful degradation: rerank failure returns the wrapped retriever's original ordering.**
ADR-007 mandates "fallback response if any RAG source is unavailable." `CrossEncoderReranker` returns `None` on transport error/timeout (mirroring `NERClient.infer`), and `RerankingRetriever` treats `None` as "keep original order, truncate to top_k." A reranker outage degrades result quality; it must never degrade availability. Chat requests continue to work with pre-rerank ordering.

**Over-fetch count (`rerank_candidate_count`, default 20) is bounded and independent of `top_k`.**
Reranking only helps if it is given more candidates than it returns. Requesting `rerank_candidate_count` from the wrapped retriever and returning `top_k` (default 5) gives the cross-encoder a real reordering opportunity while bounding both retrieval cost and the number of cross-encoder pairs scored per query. When reranking is disabled, the wrapped retriever is asked for `top_k` directly, so the disabled path costs exactly what it does today.

## Risks / Trade-offs

- **[Risk] Added per-query latency on the chat path, against ADR-007's P95 < 10s budget** → Mitigation: small CPU-viable default model; bounded candidate count (20); explicit timeout on the rerank HTTP call so a slow reranker degrades (falls back to original order) rather than consuming the whole latency budget; measure and record rerank latency during verification.
- **[Risk] First-request cold start — the reranker downloads from the Hugging Face hub and initializes on first use, adding significant one-time latency** → Mitigation: same characteristic the existing base NER model already has; the existing `warmup` router in `model_serving` is the natural place to pre-initialize it, and doing so is included in tasks.
- **[Risk] Reranking could *reduce* answer quality for queries where the bi-encoder ordering was already correct, since any reordering can demote a good chunk** → Mitigation: `reranker_enabled` flag allows instant rollback without redeploy; verification includes a scenario asserting a known-relevant chunk is promoted, and regression scenarios asserting existing retrieval behavior still holds when the flag is off.
- **[Risk] Permanent memory residency of a non-evictable singleton in the same process as the 2 GB tenant model cache** → Mitigation: small default model; the memory cost is fixed and known rather than variable; explicitly documented so a future larger-model swap is understood as a memory decision, not just a quality one.
- **[Risk] Three changes now touch the retrieval layer concurrently (`hybrid-retrieval-hnsw`, `document-purpose-scoping`, this one)** → Mitigation: the decorator only *wraps* retrievers and adds new files (`reranker.py`, `rerank_service.py`, `rerank.py`), so its overlap with the other two is limited to `__init__.py` exports and the one line in `RAGOrchestrator.__init__` that constructs the retriever; implementers must read the live state of `retriever.py` and `__init__.py` at apply time rather than assuming this design's snapshot.

## Migration Plan

Pure additive code change — no database migration, no data backfill, no re-ingestion, no API contract change. Deploy order: `model_serving` (endpoint must exist before clients call it), then `chat_api`. If `chat_api` ships first, `CrossEncoderReranker` gets connection errors and the graceful-degradation path returns unreranked results — degraded but functional, so the ordering is a preference rather than a hard requirement. Rollback: set `NER_RERANKER_ENABLED=false` (no redeploy needed), or revert the code (nothing persistent to unwind).

## Open Questions

- None of the in-force ADRs need revisiting. ADR-003 governs *per-tenant* model topology and is not contradicted by hosting an additional shared, tenant-agnostic model in the same service — the existing base NER model already does exactly this. If a future change introduces per-tenant rerankers, ADR-003's version-pinning and registry-resolution rules would then apply and that change should revisit this boundary.
- Resolved from proposal: reranker model default (`ms-marco-MiniLM-L-6-v2`, CPU-driven decision), and scope (document chunks only, not the SQL or NER sources).
- Still open for the reviewer: whether this change should be applied strictly after `hybrid-retrieval-hnsw` completes. Reranking functions correctly wrapping `DenseRetriever` alone, but delivers more value with hybrid candidates underneath it.
