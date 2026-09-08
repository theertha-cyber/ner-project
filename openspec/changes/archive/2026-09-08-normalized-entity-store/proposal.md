## Why

Batch extraction persists one `extracted_entities` row per **token** prediction — `entity_id` holds the raw BIO label (`B-PER`, `I-PER`) and `value` holds a single token (`src/extraction_service/worker.py:145-160`). Every structured-retrieval question ("which documents mention Arjun Jayakumar?", "count companies per document") therefore has to reconstruct multi-token entities inside LLM-generated SQL, which is unreliable, unindexable, and impossible to filter on exactly.

Reconstructing entities once at ingestion — into a table whose rows are complete logical entities — makes structured retrieval a plain indexed lookup, and lets structured retrieval double as a candidate-document generator that narrows semantic search.

## What Changes

- **New Entity Normalizer** in the extraction path: consumes the ordered token-prediction sequence returned by model-serving, merges BIO sequences (`B-ORG Computer` + `I-ORG Science` + `I-ORG Engineering` → `Computer Science Engineering`), merges WordPiece continuations (`A` + `##r` + `##jun` → `Arjun`), aggregates per-token confidence into one entity-level score, and computes a canonical `normalized_value` (`ReactJS`/`React.js`/`React JS` → `react`).
- **New `document_entities` table** per tenant schema: one row per complete logical entity, with `document_id`, `entity_type` (BIO prefix stripped), `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, `char_end`, indexed for structured retrieval and candidate-document lookup.
- **Ingestion writes both stores**: batch extraction keeps writing raw per-token rows to `extracted_entities` unchanged, and additionally writes normalized entities to `document_entities` in the same transaction.
- **`structured_retrieval` migrates to `document_entities`**: the SQL whitelist exposes `document_entities` and stops exposing `extracted_entities` to the SQL generator, so runtime BIO reconstruction disappears from generated SQL. **BREAKING** for any operator prompt or saved query that names `extracted_entities` through the chat SQL path — the raw table itself is untouched and still serves annotation, review, and analytics.
- **Candidate document filtering**: `structured_retrieval` additionally surfaces the distinct `document_id` set behind its matches, and the orchestrator may pass that set to `semantic_retrieval` as a `document_ids` metadata filter (already supported by `DenseRetriever`/`HybridRetriever`).
- **Backfill utility** (optional path): a script that regenerates `document_entities` for already-extracted documents, with a documented accuracy caveat (see Open Questions).
- **Base-model inference ordering fix**: `_infer_with_base_model` currently returns predictions keyed by a dict on word text (`src/model_serving/services/inference_service.py:154-161`), which drops duplicate words and destroys token order. BIO reconstruction requires ordered, non-deduplicated predictions, so this path must return an ordered sequence. **BREAKING** for consumers relying on the deduplicated shape (the Playground path shows every occurrence instead of one).

## Capabilities

### New Capabilities

- `entity-normalization`: BIO sequence reconstruction, WordPiece merging, confidence aggregation, canonical value normalization, and persistence of complete logical entities into `document_entities`, including the backfill path for previously extracted documents.

### Modified Capabilities

- `extraction-service`: batch extraction gains a mandatory normalization stage — every successfully extracted document SHALL produce `document_entities` rows in the same transaction as its raw token rows.
- `chat-api`: the SQL generation/validation requirement changes — the whitelist targets `document_entities` instead of `extracted_entities`, and structured retrieval SHALL be able to return candidate document IDs usable as a semantic-retrieval filter.
- `tenant-schema-migrations`: the tenant template and every existing tenant schema gain the `document_entities` table and its indexes.
- `model-serving`: base-model inference SHALL return one prediction per token in source order (no dedupe by word text), so downstream BIO reconstruction is well-defined.

## Impact

- `src/extraction_service/worker.py` — call normalizer after inference, insert `document_entities` rows.
- `src/extraction_service/services/` — new `entity_normalizer.py` (pure functions: reconstruct, merge, aggregate, canonicalize) and `document_entity_store.py` (persistence).
- `src/model_serving/services/inference_service.py` — `_infer_with_base_model` returns ordered list.
- `src/chat_api/services/sql_generator.py` — `WHITELISTED_TABLES` swap, prompt update, candidate-ID extraction.
- `src/shared/retrieval/tools/entity_tools.py` — `structured_retrieval` surfaces candidate document IDs alongside rows.
- `src/shared/retrieval/orchestrator.py` — optional structured→semantic sequencing to apply the candidate filter (today all plan entries run concurrently via `asyncio.gather`).
- `alembic/versions/` — new migration creating `document_entities` in `tenant_template` and every existing `tenant_*` schema.
- `scripts/` — backfill utility.
- Tests: `tests/test_entity_normalizer.py` (new), `tests/test_retrieval_tools.py`, `tests/test_chat_api_rag.py`, extraction worker tests.
- **Not touched**: chunking, embeddings, pgvector schema, reranking, LangGraph node topology, prompt assembly, generation, eval framework.

## Open Questions

- **Offsets are not available today.** The worker builds tokens with `doc_text.split()` over concatenated `document_text_spans` and never persists page or char offsets for entities, so `page_number`/`char_start`/`char_end` cannot be "carried forward" — they must be recomputed by re-aligning the token stream to the source spans. Assumption: implement alignment during normalization; if a token cannot be aligned, store NULL offsets rather than failing the document.
- **Confidence aggregation strategy**: assumption is **minimum** across the entity's tokens (most conservative, a weak token should not be hidden by strong neighbours). Mean is the alternative; decide and document in design.
- **Canonical normalization source**: `ReactJS → react` and `Amazon Web Services → aws` require an alias map, not just casefolding. Assumption: ship a small static alias table plus deterministic fallback (casefold, collapse whitespace/punctuation), with the map extensible later — not an LLM call at ingestion.
- **Backfill fidelity**: existing `extracted_entities` rows have no ordering column (`id` is a random UUID) and no offsets, so BIO sequences cannot be reliably reconstructed from the stored rows. Assumption: backfill re-runs inference rather than reading the old rows; documents not backfilled simply have no `document_entities` rows and fall out of structured retrieval until reprocessed.
- **Candidate-filter sequencing**: applying candidate document IDs to semantic retrieval requires running structured retrieval first, but the orchestrator currently dispatches all plan entries concurrently. Assumption: make the filter opt-in and confined to `execute_plan` (no graph topology change); confirm the added latency is acceptable.
- **Entity types**: `document_entities.entity_type` stores the BIO-stripped label (`PER`, `ORG`), while the request examples use `PERSON`/`COMPANY`/`SKILL`. Assumption: store the model's own label vocabulary unmapped; no renaming layer in this change.
