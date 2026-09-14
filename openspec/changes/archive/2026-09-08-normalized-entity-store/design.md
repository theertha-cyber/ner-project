## Context

Batch extraction (`src/extraction_service/worker.py`) tokenizes a document with `doc_text.split()` over its concatenated `document_text_spans`, POSTs the token list to model-serving `/internal/v1/infer`, and writes **one row per returned prediction** into `{tenant}.extracted_entities` with `entity_id = "B-PER"` and `value = "Arjun"`. There is no ordering column on those rows (`id` is a random UUID), no page number, and no character offsets.

Chat structured retrieval (`src/shared/retrieval/tools/entity_tools.py` → `ToolContext.sql_search` → `src/chat_api/services/sql_generator.py`) hands `extracted_entities` to an LLM as a whitelisted table. Any question about a real-world entity therefore requires the LLM to reassemble BIO sequences in SQL — which it cannot do reliably, and which no index can serve.

Two upstream facts shape this design:

1. **The ONNX path already collapses subwords.** `_infer_with_onnx` walks `encoding.word_ids(0)`, keeps the first sub-token per word, drops label id 0 (`O`), and emits `tokens[word_id]` — whole words, in order. WordPiece merging is therefore only needed for the base-model path.
2. **The base-model path destroys order and repeats.** `_infer_with_base_model` runs `pipeline("ner")` with no `aggregation_strategy` (so `##`-prefixed subwords are emitted) and then folds results into a dict keyed on word text, keeping the max-scoring entry. That loses token order and every repeated occurrence — BIO reconstruction is impossible on that output. This must be fixed for normalization to be well-defined on tenants with no promoted model, which is the default state (ADR-008).

The orchestrator (`src/shared/retrieval/orchestrator.py`) dispatches every plan entry concurrently through `asyncio.gather`, so candidate-document filtering — which needs structured results before semantic search runs — is a scheduling change inside `execute_plan`, not a graph topology change.

## Goals / Non-Goals

**Goals:**

- Reconstruct complete logical entities exactly once, at ingestion, and store them in a query-optimized per-tenant `document_entities` table.
- Keep `extracted_entities` byte-for-byte the source of truth for raw BIO predictions (annotation, review, analytics, confidence inspection).
- Point chat structured retrieval at `document_entities` so no generated SQL reconstructs BIO sequences.
- Let structured retrieval act as a candidate generator whose document IDs can narrow semantic search.

**Non-Goals:**

- Changing chunking, embeddings, the vector schema, hybrid fusion, or reranking.
- Changing LangGraph node topology, prompt assembly, generation, or the eval framework.
- Renaming the model's label vocabulary (`PER`/`ORG` stay as the model emits them; no `PERSON`/`COMPANY` mapping layer).
- Entity resolution across documents (no cross-document identity table); `normalized_value` is a matching key, not an entity ID.

## Currently-In-Force ADRs

Every ADR in `docs/adr/` carries **Status: Proposed**; ADR-008 partially supersedes ADR-002. Treating the non-superseded set as the live constraints:

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated in separate PostgreSQL schemas | `document_entities` is a per-tenant-schema table created on `tenant_template` and every existing `tenant_*` schema; all queries stay inside the caller's schema via `search_path` |
| ADR-002-base-model-strategy | Single curated base model, no BYOM | Normalizer must handle the base model's CoNLL label set (`PER`/`ORG`/`LOC`/`MISC`) as well as tenant `label_list` values |
| ADR-003-model-serving-topology | Per-tenant model serving with cached models | Normalization runs in the extraction worker, not in model-serving; the inference contract stays "tokens in, ordered predictions out" |
| ADR-004-openspec-governance | Spec-driven development | Behaviour lands as delta specs before code |
| ADR-006-training-infrastructure | Async workers for heavy work | Normalization and backfill run inside the existing Celery extraction worker, not in a request path |
| ADR-007-chatbot-architecture | Full RAG with controlled SQL generation and guardrails | The SQL whitelist/validation layer stays the only gate; swapping the whitelisted table must not weaken SELECT-only, LIMIT, UNION, or subquery rules |
| ADR-008-base-model-as-default | Base model (version 0) is the default inference model | The base-model path is the common case, so its ordering fix is required, not optional |

## Decisions

### Decision 1: Normalize in the worker from the in-memory prediction sequence

**Choice:** The Entity Normalizer consumes the ordered `predictions` list the worker already receives from `/internal/v1/infer`, in the same loop that writes raw rows, and writes both raw and normalized rows in one `engine.begin()` transaction.

**Rationale:** Order is the whole input to BIO reconstruction, and order exists only in memory — the persisted `extracted_entities` rows have no sequence column. A single transaction gives the "never normalized without raw" invariant for free.

**Alternatives considered:**
- Read back `extracted_entities` and reconstruct from the table — ruled out: no ordering column, so sequences are unrecoverable; adding one would modify the raw table, which the change forbids.
- Normalize inside model-serving and return entities instead of tokens — ruled out: breaks the token-level contract the annotation and evaluation paths depend on, and puts document-level logic in a stateless inference service (ADR-003).
- A separate post-ingestion Celery task — ruled out: two transactions, so a document can exist with raw rows and no normalized rows; no benefit since the data is already in hand.

### Decision 2: Pure-function normalizer, thin persistence layer

**Choice:** `src/extraction_service/services/entity_normalizer.py` exposes pure functions — `merge_wordpieces(predictions) -> predictions`, `reconstruct_entities(predictions) -> list[NormalizedEntity]`, `aggregate_confidence(scores) -> float`, `canonicalize(value) -> str` — with no DB or network dependency. `document_entity_store.py` holds the inserts.

**Rationale:** Every acceptance scenario in `specs/entity-normalization/spec.md` becomes a table-driven unit test with no fixtures, no DB, and no model. The alias map and the confidence strategy each live behind one function, so changing them is a one-line edit.

**Alternatives considered:**
- Inline the logic in `worker.py` — ruled out: only testable through Celery + DB + model-serving, which is why the current worker is effectively untested at this level.

### Decision 3: Minimum as the confidence aggregation strategy

**Choice:** `confidence = min(token confidences)`, implemented in `aggregate_confidence`.

**Rationale:** An entity is only as trustworthy as its weakest token — `Computer Science Engineering` where `Engineering` scored 0.41 should not present as 0.9 because two neighbours were confident. This keeps the existing confidence-threshold filtering (`extraction-service` post-processing) conservative rather than optimistic.

**Alternatives considered:**
- Mean — ruled out as the default: hides a weak boundary token, which is exactly where BIO errors concentrate. It stays a one-line swap.
- First-token (B- tag) confidence — ruled out: ignores the merge entirely.
- Store all three — ruled out: schema noise for a value nothing consumes yet.

### Decision 4: `normalized_value` = static alias map over a deterministic fallback

**Choice:** `canonicalize()` first applies deterministic normalization (NFKC, casefold, collapse internal whitespace, strip surrounding punctuation), then looks the result up in a static alias map (`react.js`/`reactjs`/`react js` → `react`, `amazon web services` → `aws`) and returns the alias when hit, the deterministic form otherwise.

**Rationale:** Deterministic-first means the map is keyed on already-normalized text, so one entry covers every casing/punctuation variant. No network call, no model, no per-document cost — normalization stays a pure function (Decision 2). The map is a plain module-level dict, extensible without a migration.

**Alternatives considered:**
- LLM canonicalization at ingestion — ruled out: non-deterministic, per-document cost, and makes the normalizer untestable offline.
- Embedding-based clustering of surface forms — ruled out: out of scope, and would need a resolution table (Non-Goals).
- Casefold only — ruled out: fails the `ReactJS`/`AWS` acceptance scenarios outright.

### Decision 5: Offsets by re-alignment, NULL on failure

**Choice:** The worker keeps the `(span_text, page_number, span_start_offset)` list it already fetches, tokenizes with offsets rather than bare `.split()`, and carries `(page_number, char_start, char_end)` alongside each token. An entity's `char_start` is its first token's start and `char_end` its last token's end. Any token that cannot be aligned yields NULL offsets for that entity; the document still persists.

**Rationale:** The proposal's "carry forward offsets from the BIO tokens" is not achievable as stated — nothing upstream produces offsets today. Re-alignment at tokenization time is the cheapest place to create them, since the worker already holds the spans. Degrading to NULL rather than failing keeps offsets a retrieval nicety, not an ingestion blocker.

**Alternatives considered:**
- Have model-serving return offsets — ruled out: it receives a pre-split token list, not the source text, so it cannot know document offsets (ADR-003 keeps it stateless).
- Fail the document when alignment fails — ruled out: turns a display-quality issue into data loss.
- Skip offsets entirely — ruled out: they are in the requested schema and enable citation-level attribution later.

### Decision 6: Whitelist swap, not dual exposure, in the SQL generator

**Choice:** `WHITELISTED_TABLES` in `sql_generator.py` gains `document_entities` and **drops** `extracted_entities`; the prompt's join hint changes to `document_entities.document_id → documents.id`. The validation layer itself (SELECT-only, LIMIT, UNION, subquery, timeout) is untouched.

**Rationale:** Leaving both tables whitelisted guarantees the planner keeps picking the token table for some questions, so runtime BIO reconstruction would not actually be eliminated — the stated acceptance criterion. Removing it from the whitelist makes the guarantee structural rather than promptual. Analytics, annotation, and the extraction API keep querying `extracted_entities` directly; only the chat SQL path loses access.

**Alternatives considered:**
- Whitelist both and instruct the prompt to prefer `document_entities` — ruled out: an instruction, not a guarantee.
- A SQL view named `extracted_entities` over `document_entities` — ruled out: silently changes meaning for every other consumer of that name.

### Decision 7: Candidate filtering as opt-in two-phase execution in `execute_plan`

**Choice:** `StructuredRetrievalTool` derives `candidate_document_ids` from the `document_id` column of the rows it returned and exposes it on `ToolResult`. Behind a config flag (default off initially), `execute_plan` runs structured entries first, collects the union of their candidate IDs, and injects `scope: {"type": "document", "document_ids": [...]}` into semantic entries that carry no explicit `scope` argument; then runs them. This matches `semantic_retrieval`'s existing args_schema (`scope.document_ids`, consumed by `_scope_to_metadata_filter`) rather than a bare top-level key, since `run_tool`'s `validate_args` would reject an unknown argument. Flag off ⇒ the current single `asyncio.gather` path is used unchanged.

**Rationale:** Sequencing is required by the feature and costs one extra round-trip of latency; a flag lets that be measured before it becomes default. Keeping it inside `execute_plan` satisfies "LangGraph topology unchanged" — nodes and edges are untouched.

**Alternatives considered:**
- Always sequence — ruled out: adds structured-retrieval latency to every semantic-only-relevant turn, and structured retrieval is the slowest source (LLM SQL generation + query).
- A new graph node for candidate generation — ruled out: explicitly out of scope.
- Planner-supplied candidate IDs — ruled out: the planner never sees results (`ORCHESTRATION_SYSTEM_PROMPT`).

### Decision 8: Backfill re-runs inference; un-backfilled documents degrade quietly

**Choice:** `scripts/backfill_document_entities.py` selects documents with `extracted_entities` rows but no `document_entities` rows, re-runs the normal extract-and-normalize path per document, and deletes-then-inserts that document's `document_entities` rows for idempotency. `extracted_entities` is never written.

**Rationale:** Reconstruction from stored rows is impossible (Decision 1). Re-running inference is the only faithful source. Delete-then-insert per document is simpler than an upsert key and matches "reprocessing replaces".

**Alternatives considered:**
- Best-effort reconstruction from stored rows using insertion order — ruled out: `id` is a random UUID, so row order is not prediction order; would produce plausible-looking wrong entities.
- Backfilling inside the migration — ruled out: needs model-serving and is unbounded in time; migrations must stay DDL.

## Risks / Trade-offs

- [Fixing `_infer_with_base_model` ordering changes what the Playground shows — repeated words now appear once per occurrence instead of collapsed] → Intended and specced; call it out in the change notes, and check `PlaygroundTab`/`EntityReviewTab` tests, which the in-flight `merge-bio-entity-display` change also touches.
- [Two changes now merge BIO tags: this one server-side, `merge-bio-entity-display` client-side] → They serve different surfaces (retrieval vs. display) and can coexist; the shared risk is divergent merge rules. Keep the server normalizer as the reference implementation and note the frontend as a future consolidation.
- [Removing `extracted_entities` from the chat SQL whitelist breaks any tuned prompt or saved question that names it] → Flagged **BREAKING** in the proposal; the raw table stays reachable from analytics and the extraction API.
- [Documents extracted before this change have no `document_entities` rows and silently vanish from structured retrieval] → Specced as acceptable (semantic path unaffected); ship the backfill utility in the same change and run it before flipping the whitelist in any environment with existing data.
- [Alias map is hand-maintained, so unknown variants (`k8s` vs `kubernetes`) miss] → Deterministic fallback still matches exact-form repeats; the map is a dict, extensible without migration. Log unmatched high-frequency values later if needed.
- [`min` confidence makes long entities systematically lower-confidence than short ones, interacting with the existing confidence threshold] → Threshold applies to raw extraction today; verify the normalized store is not double-filtered, and keep the strategy behind one function.
- [Two-phase execution adds structured-retrieval latency to the semantic source when the flag is on] → Default off; measure against `OrchestrationBudget.deadline` before enabling.
- [Tokenizing with offsets changes the token stream vs. `.split()`, which could shift predictions] → Keep whitespace splitting semantics identical; only attach offsets. Assert token-list equality against the old `.split()` output in a unit test.

## Migration Plan

1. Ship the Alembic migration creating `document_entities` (+ indexes on `document_id`, `entity_type`, `normalized_value`) on `tenant_template` and every existing `tenant_*` schema, following the established per-tenant DDL loop pattern. Idempotent (`IF NOT EXISTS`), with a downgrade that drops only the new table.
2. Ship the ordering fix in `_infer_with_base_model` and the normalizer module — both inert until wired.
3. Wire the worker to write `document_entities` alongside `extracted_entities` in the same transaction. From here every newly ingested document produces normalized entities.
4. Run `scripts/backfill_document_entities.py` per environment for already-extracted documents.
5. Swap the chat SQL whitelist to `document_entities`. This is the user-visible cutover, and step 4 should precede it wherever real data exists.
6. Land candidate filtering behind its flag, default off; enable after latency measurement.

**Rollback:** Steps 5 and 6 are config/whitelist-level and revert independently. Step 3 reverts by removing the normalized insert — `extracted_entities` is untouched throughout, so the raw path is never at risk. Step 1's downgrade drops `document_entities` only.

## Open Questions

- Should the existing extraction confidence threshold apply to normalized entities as well, or only to raw rows? Current assumption: raw-row filtering only, normalization sees what the worker persists.
- Should `document_entities` carry `run_id`/`model_version` so entities can be attributed to the model that produced them (useful for reprocessing and for A/B comparing extraction quality)? Not in the requested schema; cheap to add now, awkward later.
- Every ADR is still **Proposed**, not Accepted. This design assumes they are the live constraints. If ADR-007 (chatbot architecture) is meant to enumerate the retrieval sources, the whitelist swap may warrant a superseding ADR — flagged for the adr step rather than edited here.
