## Why

Retrieval currently returns whatever the vector index ranks highest by cosine similarity, and `RAGOrchestrator` feeds the top 3 straight into the LLM context. Bi-encoder embedding similarity is a coarse relevance signal — it compares a query embedding against chunk embeddings computed independently, with no cross-attention between the two. A cross-encoder reranker scores each (query, chunk) pair jointly and reorders them, and is the single highest-precision-per-unit-effort improvement available to this pipeline: it consistently lifts top-k precision well above what the retriever alone produces, without touching ingestion, embeddings, or the index. This matters more here than in a generic RAG system because the orchestrator truncates hard (`vector_sources[:3]`, `chunk_text[:500]`) — if the genuinely relevant chunk is ranked 4th by cosine similarity, it is silently discarded before the LLM ever sees it.

## What Changes

- Add a `POST /internal/v1/rerank` endpoint to the existing `model_serving` service that scores a query against a list of candidate texts using a cross-encoder model and returns them reordered with relevance scores.
- Load the reranker as a lazily-initialized module-level singleton (following the existing `_base_pipeline` precedent in `inference_service.py` for the tenant-agnostic base NER model), **not** via the per-tenant `ModelCache` — the reranker is one global model shared by all tenants, not a per-tenant artifact.
- Add a `Reranker` protocol and a `CrossEncoderReranker` implementation (an HTTP client to the endpoint above) to `src/shared/retrieval/`.
- Add a `RerankingRetriever` that wraps any existing `Retriever` (decorator pattern): it over-fetches candidates from the wrapped retriever, reranks them, and returns the top-k. Because it implements the `Retriever` protocol itself, `RAGOrchestrator._vector_source` requires no change beyond which retriever instance it holds.
- Add configuration: `reranker_enabled` (feature flag, default on), `reranker_model` (default `cross-encoder/ms-marco-MiniLM-L-6-v2`), `rerank_candidate_count` (how many to over-fetch before reranking, default 20).
- Reranking failures SHALL degrade gracefully — if the rerank call fails or times out, the wrapped retriever's original ordering is returned rather than failing the chat request.
- No new Python dependency: `torch` and `transformers` are already project dependencies.
- No database migration, no ingestion change, no embedding change, no API contract change on `/api/v1/chat`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `model-serving`: gains a new reranking endpoint requirement (additive — no existing inference/cache requirement changes).
- `retrieval-core`: gains a `Reranker` interface requirement and a reranking-composition requirement (additive — the existing `Retriever` interface requirement is unchanged, since `RerankingRetriever` implements that protocol rather than altering it).
- `chat-api`: gains a requirement that document context is reranked before being assembled into the LLM prompt.

## Impact

- `src/model_serving/api/v1/rerank.py` (new), `src/model_serving/api/v1/schemas.py`, `src/model_serving/main.py` (router registration), `src/model_serving/services/rerank_service.py` (new)
- `src/shared/retrieval/reranker.py` (new — `Reranker` protocol, `CrossEncoderReranker` HTTP client), `src/shared/retrieval/retriever.py` (new `RerankingRetriever`), `src/shared/retrieval/__init__.py` (exports)
- `src/shared/config.py` — `reranker_enabled`, `reranker_model`, `rerank_candidate_count`
- `src/chat_api/services/rag_orchestrator.py` — `self.retriever` becomes a `RerankingRetriever` wrapping whatever retriever it holds today
- First model download: the reranker model is pulled from the Hugging Face hub on first use, same as the existing base NER model — offline/air-gapped deployments need it pre-cached in the image or model volume

## Open Questions

- **Reranker model default under CPU-only deployment**: `settings.training_device` defaults to `cpu`, and `model_serving` has no GPU configured in the local docker-compose stack. A large reranker (e.g. `BAAI/bge-reranker-v2-m3`, ~568M params) would add seconds of latency per query on CPU and permanently occupy more memory than the entire 2 GB per-tenant model cache budget. This proposal defaults to the much smaller `cross-encoder/ms-marco-MiniLM-L-6-v2` and makes the model name configurable — confirm this trade-off (quality vs. CPU-viability) is the right default, and whether a GPU-backed deployment should override it.
- **Where reranking sits relative to the in-flight retrieval changes**: `hybrid-retrieval-hnsw` and `document-purpose-scoping` are both proposed-but-unapplied and both touch `src/shared/retrieval/retriever.py`. The decorator approach is deliberately insulated from both (it wraps whatever `Retriever` exists), but confirm the intended apply order — reranking is most valuable *after* hybrid retrieval, since it has more (and more diverse) candidates to reorder.
- **Should reranking apply to the SQL source too?** Currently only the vector/document source is reranked. The SQL source returns structured entity rows, which aren't natural cross-encoder inputs. Confirm reranking stays scoped to document chunks only.
