## Context

Two services touch retrieval today: `document_service/ocr_worker.py` (ingestion — extracts text, chunks it, embeds it, writes `document_chunks`) and `chat_api` (retrieval — `embedding_service.similarity_search`, `rag_orchestrator`). They independently reimplement chunking (`_chunk_text` in both, byte-identical) and both talk to `document_chunks` with raw SQL returning dicts. `rag_orchestrator.execute` fans out to `_sql_source` and `_vector_source` concurrently via `asyncio.gather`, then hand-assembles a context string. `_enrich_citations` (rag_orchestrator.py:157) calls `text(f"SELECT id, filename FROM {schema}.documents ...")` but the module never imports `sqlalchemy.text` — this raises `NameError` inside a `try/except Exception` that only logs a warning, so citation enrichment for document/NER sources silently no-ops in production today. `src/shared/config.py` is a single flat `pydantic-settings` `Settings` object, env-prefixed `NER_`, shared by every service.

ADR-007 (chatbot-architecture, in force, not superseded) fixes the three-source RAG shape (SQL + pgvector + NER), citation-required responses, and complexity limits — this change does not touch any of that; it only relocates *how* the pgvector source is implemented internally.

## Goals / Non-Goals

**Goals:**

- Typed `Chunk` and `RetrievalResult` models used by both services, replacing dict-in/dict-out at the `document_chunks` boundary.
- A `Retriever` protocol with one implementation (`DenseRetriever`) that is a drop-in, behavior-identical replacement for `EmbeddingService.similarity_search`.
- One chunking implementation, imported by both `document_service` and `chat_api`, deleting the duplicate.
- Fix the `_enrich_citations` `NameError` bug.
- One `RetrievalConfig` holding chunk size/overlap/top-k/embedding model, sourced from `src/shared/config.Settings`.

**Non-Goals:**

- No hybrid (dense+sparse) retrieval, no HNSW index change, no reranking, no new chunking strategy (structural/semantic), no query rewriting, no agentic loop. Those are later changes and must be addable behind the `Retriever` protocol without touching `rag_orchestrator`'s call sites again.
- No `document_chunks` schema/migration changes (chunk metadata such as page number lands in `chunk-metadata-ingest`).
- No change to the `/api/v1/chat` request/response contract or guardrail thresholds.

## Decisions

**Domain model location: `src/shared/retrieval/`, not `src/chat_api/domain/`.**
Both `document_service` (writer) and `chat_api` (reader) need `Chunk`/`RetrievalResult`. `src/shared` already holds cross-service types/config/db helpers, so this follows the existing pattern rather than creating a new cross-service import from `document_service` into `chat_api`.
Alternative considered: keep it in `chat_api` and have `document_service` depend on `chat_api` — rejected, wrong dependency direction (ingestion is upstream of chat).

**`Retriever` as `typing.Protocol`, not an ABC.**
A structural-typing protocol lets `DenseRetriever` (and later `SparseRetriever`, `HybridRetriever`) be swapped and composed without a common base-class constructor, and lets `retrieval-tools-and-eval` wrap any retriever as an LLM tool without inheritance gymnastics.
Alternative considered: ABC with `abstractmethod retrieve()` — works too, but Protocol matches this codebase's existing lightweight-class style (see `EmbeddingService`, `SQLGenerator` — no shared base class today).

```python
class Retriever(Protocol):
    async def retrieve(self, query: str, session: AsyncSession, schema: str, top_k: int) -> list[RetrievalResult]: ...
```

**`DenseRetriever` reproduces `similarity_search` exactly — same SQL, same `ivfflat` index, same cosine operator.**
This change is a refactor, not a retrieval-quality change. Index type (HNSW) and hybrid fusion are `hybrid-retrieval-hnsw`'s concern; changing both interface and algorithm in one step makes regressions hard to attribute.

**`RetrievalConfig` is a nested field on the existing `Settings` object, not a separate standalone config class.**
Every other cross-cutting setting (DB URL, model cache TTL, CORS) already lives on `Settings`, env-prefixed `NER_`. Adding `NER_CHUNK_SIZE`, `NER_CHUNK_OVERLAP`, `NER_RETRIEVAL_TOP_K`, `NER_EMBEDDING_MODEL` as flat fields (pydantic-settings doesn't need a nested model for 4 scalars) keeps one settings-loading path instead of two.
Resolves proposal's open question: config lives in `src/shared/config.py`; domain models live in `src/shared/retrieval/`.

**Chunking consolidation: `document_service` imports `src/shared/retrieval/chunking.py`; `chat_api/services/chunking_service.py` becomes a thin re-export or is deleted if nothing external still calls `chunk_and_embed_document`.**
Investigate at implementation time whether `chunking_service.chunk_and_embed_document` has any caller — grep showed only `ocr_worker.py`'s own private copy is actually invoked by `process_document`; `chunking_service.py`'s version appears unused. If confirmed dead, delete it rather than keep a second entry point.

## Risks / Trade-offs

- **[Risk] Refactor silently changes retrieval ranking or citation content despite "behavior-identical" intent** → Mitigation: capture a fixture of representative queries against a seeded tenant schema, snapshot `similarity_search` output (document_id, chunk_index, similarity_score, chunk_text) before the refactor, and diff against `DenseRetriever.retrieve()` output after — must be byte-identical for the same inputs.
- **[Risk] Fixing the citation-enrichment bug changes chat response `sources`/citations for real users who have been silently getting fewer citations** → Mitigation: this is a bug fix, not a scope change; document the before/after difference in verification evidence so it's visible at review, not a silent side effect.
- **[Risk] Moving chunking to `src/shared` couples `document_service` and `chat_api` to a shared internal module, increasing blast radius of future edits** → Mitigation: keep the shared surface minimal (models + `Retriever` protocol + chunking function + config), no service-specific logic (guardrails, SQL generation) moves to `shared`.
- **[Risk] `RetrievalConfig` fields on `Settings` need defaults matching current hardcoded literals (512/128/5/"text-embedding-3-small") exactly, or ingestion/retrieval silently change** → Mitigation: unit test asserts default config values match the literals being replaced.

## Migration Plan

Pure code refactor — no database migration, no data backfill. Deploy as a normal release. Rollback is a code revert (no schema/state to unwind). Sequencing within the change: (1) add domain models + config, (2) add `Retriever`/`DenseRetriever` alongside existing `similarity_search` without removing it, (3) switch `rag_orchestrator` to call `DenseRetriever`, (4) remove `EmbeddingService.similarity_search` and duplicate chunking once nothing calls them, (5) fix the citation bug last so its effect is isolated and easy to verify independently of the retrieval-plumbing change.

## Open Questions

- Confirm whether `chunking_service.chunk_and_embed_document` has any live caller before deleting it (grep at proposal time found none, but re-verify at implementation time — a background worker or script might call it).
- None of the in-force ADRs need revisiting; ADR-007's three-source shape and citation-required guardrail are unaffected.
