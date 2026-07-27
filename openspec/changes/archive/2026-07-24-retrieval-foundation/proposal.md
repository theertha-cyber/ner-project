## Why

The chat RAG pipeline (`src/chat_api`) works but has structural debt that will make every planned retrieval improvement (hybrid search, reranking, agentic tool loops) more expensive to build: chunking logic is duplicated across `document_service/ocr_worker.py` and `chat_api/services/chunking_service.py`, retrieval results flow through the system as untyped dicts, there is no interface separating "how we retrieve" from "how we answer," and `rag_orchestrator._enrich_citations` calls `text(...)` without importing `sqlalchemy.text` — a live bug that silently degrades citation enrichment (caught by the outer `except`) whenever a response has a `document_id` source. Before adding new retrieval strategies, we need one typed, testable retrieval core that today's behavior maps onto exactly, so later changes swap implementations instead of rewriting call sites.

## What Changes

- Add typed domain models (`Chunk`, `RetrievalResult`) used by ingestion and retrieval instead of raw dicts.
- Add a `Retriever` interface (protocol) with a `DenseRetriever` implementation that reproduces today's pgvector cosine top-k behavior exactly — no ranking or result changes.
- Consolidate the two duplicate chunking implementations into a single module; `document_service/ocr_worker.py` calls the shared implementation instead of maintaining its own copy.
- Fix the missing `sqlalchemy.text` import in `rag_orchestrator._enrich_citations` so citation enrichment executes instead of failing silently.
- Add a `RetrievalConfig` object centralizing chunk size, overlap, top-k, and embedding model name — currently hardcoded as separate literals in `chunking_service.py`, `ocr_worker.py`, and `embedding_service.py`.
- No change to the `/api/v1/chat` request/response contract, guardrail behavior, or SQL-generation path.

## Capabilities

### New Capabilities

- `retrieval-core`: typed chunk/result models, a `Retriever` interface, a single chunking implementation, and centralized retrieval configuration that later retrieval changes build on.

### Modified Capabilities

(none — this is a behavior-preserving refactor; `chat-api`'s existing requirements and scenarios continue to hold unchanged)

## Impact

- `src/chat_api/services/chunking_service.py`, `src/chat_api/services/embedding_service.py`, `src/chat_api/services/rag_orchestrator.py`
- `src/document_service/services/ocr_worker.py` (drops its private `_chunk_text`/`_embed_chunks`/`_store_chunks`, calls shared services instead)
- New: `src/chat_api/domain/` (or `src/shared/retrieval/`) for `Chunk`, `RetrievalResult`, `Retriever` protocol, `RetrievalConfig`
- No database migration — `document_chunks` schema is unchanged in this step (chunk metadata columns land in `chunk-metadata-ingest`)
- Downstream: `chunk-metadata-ingest`, `hybrid-retrieval-hnsw`, `cross-encoder-rerank`, `context-assembly-pipeline`, and `retrieval-tools-and-eval` all depend on the interfaces introduced here

## Open Questions

- Domain model location: `src/chat_api/domain/` (chat-api-local) vs `src/shared/retrieval/` (cross-service, since `document_service` also needs `Chunk`). Leaning `src/shared/retrieval/` since ingestion lives in a different service — confirm during design.
- Should `RetrievalConfig` be a new `pydantic-settings` sub-model under `src/shared/config.py` or a standalone config object constructed by callers? Affects how later changes (HNSW, reranking) add fields.
