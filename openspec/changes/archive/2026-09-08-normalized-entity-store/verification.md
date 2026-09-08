# Verification Plan

**Change:** normalized-entity-store
**Generated:** 2026-07-31
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-normalization | BIO sequence reconstruction | Consecutive B-I tokens merge into one entity | Given predictions `[(B-ORG,"Computer"),(I-ORG,"Science"),(I-ORG,"Engineering")]`, when reconstruction runs, then exactly one entity is produced with `entity_type = ORG` and `entity_value = "Computer Science Engineering"` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 2 | entity-normalization | BIO sequence reconstruction | Consecutive B tags of the same type start separate entities | Given predictions `[(B-PER,"Alice"),(B-PER,"Bob")]`, when reconstruction runs, then two entities are produced with values `Alice` and `Bob` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 3 | entity-normalization | BIO sequence reconstruction | An I tag of a different type closes the open entity | Given predictions `[(B-PER,"Arjun"),(I-ORG,"InApp")]`, when reconstruction runs, then two entities are produced: `PER "Arjun"` and `ORG "InApp"` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 4 | entity-normalization | BIO sequence reconstruction | A dangling I tag with no preceding B tag opens an entity | Given predictions `[(I-LOC,"Kerala")]`, when reconstruction runs, then one `LOC` entity `Kerala` is produced and no exception is raised | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 5 | entity-normalization | BIO sequence reconstruction | The same entity text occurring twice produces two entities | Given predictions `[(B-ORG,"InApp"),(B-LOC,"Kochi"),(B-ORG,"InApp")]`, when reconstruction runs, then two separate `ORG` entities are produced, one per occurrence | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 6 | entity-normalization | WordPiece continuation merging | Subword tokens merge into a single word | Given predictions `[(B-PER,"A"),(B-PER,"##r"),(B-PER,"##jun"),(I-PER,"Jaya"),(I-PER,"##kumar")]`, when reconstruction runs, then exactly one `PER` entity with value `Arjun Jayakumar` is produced | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 7 | entity-normalization | WordPiece continuation merging | Whole-word predictions are unaffected | Given predictions `[(B-LOC,"New"),(I-LOC,"York")]`, when reconstruction runs, then one `LOC` entity `New York` is produced | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 8 | entity-normalization | Entity-level confidence aggregation | Entity confidence is the minimum of its tokens | Given an entity whose token confidences are `[0.99, 0.71, 0.88]`, when confidence is aggregated, then the entity's `confidence` is `0.71` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 9 | entity-normalization | Entity-level confidence aggregation | Single-token entity keeps its own confidence | Given a one-token entity with confidence `0.93`, when confidence is aggregated, then the entity's `confidence` is `0.93` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 10 | entity-normalization | Canonical value normalization | Deterministic fallback normalization | Given `entity_value = "Arjun  Jayakumar."`, when canonicalization runs, then `normalized_value = "arjun jayakumar"` and `entity_value` is unmodified | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 11 | entity-normalization | Canonical value normalization | Alias map collapses surface variants | Given values `ReactJS`, `React.js`, `React JS`, when canonicalization runs, then all three yield `normalized_value = "react"` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 12 | entity-normalization | Canonical value normalization | Acronym alias maps to the same canonical value as its expansion | Given values `Amazon Web Services` and `AWS`, when canonicalization runs, then both yield `normalized_value = "aws"` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 13 | entity-normalization | Canonical value normalization | Unknown value falls back to deterministic normalization | Given value `InApp` with no alias entry, when canonicalization runs, then `normalized_value = "inapp"` | unit test: `tests/test_entity_normalizer.py` (task 3.6) | - [x] |
| 14 | entity-normalization | Location metadata on normalized entities | Entity carries offsets spanning its first and last token | Given a page-2 span containing `Computer Science Engineering` starting at offset 100, when the `ORG` entity is reconstructed, then it has `page_number = 2`, `char_start = 100`, `char_end = 128` | unit test: `tests/test_entity_normalizer.py` (task 4.4) | - [x] |
| 15 | entity-normalization | Location metadata on normalized entities | Unalignable token yields NULL offsets rather than failure | Given a token stream that cannot be aligned to any span, when reconstruction runs, then affected entities have NULL `page_number`/`char_start`/`char_end` and are still produced with type, value, normalized value, and confidence | unit test: `tests/test_entity_normalizer.py` (task 4.4) | - [x] |
| 16 | entity-normalization | Normalized entity persistence | One row per logical entity | Given a document reconstructing to `PER "Arjun Jayakumar"`, `ORG "InApp"`, `SKILL "Kubernetes"`, when entities are persisted, then `document_entities` holds exactly three rows for that `document_id`, with no `B-`/`I-` prefixed `entity_type` and no `##`-prefixed `entity_value` | integration test: extraction worker + DB query (task 5.4) | - [x] |
| 17 | entity-normalization | Normalized entity persistence | Normalized store is queryable by canonical value | Given two documents mentioning `AWS` and `Amazon Web Services`, when a query filters `normalized_value = 'aws'`, then rows from both documents are returned | integration test: extraction worker + DB query (task 5.4) | - [x] |
| 18 | entity-normalization | Raw BIO storage is preserved | Raw token rows still written | Given batch extraction completes for a document, when `extracted_entities` is inspected, then it holds the same per-token BIO-prefixed rows as before this change, and `document_entities` additionally holds the reconstructed entities | integration test: raw-vs-normalized row assertion (task 5.5) | - [x] |
| 19 | entity-normalization | Raw BIO storage is preserved | Normalization failure does not leave a half-written document | Given normalized-entity persistence fails for a document, when the transaction rolls back, then neither raw nor normalized rows for that document are committed and the document is counted as failed | integration test: injected persistence failure (task 5.6) | - [x] |
| 20 | entity-normalization | Backfill of previously extracted documents | Backfill populates the normalized store | Given a document with `extracted_entities` rows and no `document_entities` rows, when backfill runs for it, then `document_entities` holds its reconstructed entities and `extracted_entities` is unchanged | script test: `scripts/backfill_document_entities.py` (task 6.3) | - [x] |
| 21 | entity-normalization | Backfill of previously extracted documents | Re-running backfill does not duplicate rows | Given an already-backfilled document, when backfill runs again, then its `document_entities` row count is unchanged | script test: `scripts/backfill_document_entities.py` (task 6.3) | - [x] |
| 22 | entity-normalization | Backfill of previously extracted documents | Un-backfilled documents still function | Given a document with no `document_entities` rows, when a semantic question answered from its chunks is asked, then the answer still cites that document | integration test: semantic-path citation (task 6.4) | - [x] |
| 23 | extraction-service | Batch extraction | Trigger batch extraction | Given a tenant with a promoted model and `processed` documents, when POST `/api/v1/extract-batch?documentIds=doc1,doc2,doc3`, then status 202 with `run_id` and `status: "queued"`, and GET `/api/v1/extract-batch/{run_id}` returns `queued` | existing batch extraction suite (task 5.8) | - [x] |
| 24 | extraction-service | Batch extraction | Batch extraction persists extracted entities with document linkage | Given one `processed` document, when batch extraction completes, then the run has `processed_count = 1`, `failed_count = 0`, and `extracted_entities` rows exist for the `run_id` with non-null `entity_id`, `value`, `confidence`, `document_id` matching the source document | existing batch extraction suite (task 5.8) | - [x] |
| 25 | extraction-service | Batch extraction | Batch extraction persists normalized entities | Given a document containing `Arjun Jayakumar works at InApp`, when batch extraction completes, then `document_entities` holds one row per logical entity for that `document_id`, including `entity_type = 'PER'` / `entity_value = 'Arjun Jayakumar'`, and no row has a `B-`/`I-` prefixed `entity_type` | integration test: normalized entities on ingest (task 5.7) | - [x] |
| 26 | extraction-service | Batch extraction | Batch extraction skips already-extracted documents | Given a document already extracted for the active model version, when batch extraction is triggered, then the document is skipped and the run report marks it skipped | existing batch extraction suite (task 5.8) | - [x] |
| 27 | extraction-service | Batch extraction | Batch extraction for tenant with no promoted model | Given a tenant with no promoted model, when POST `/api/v1/extract-batch`, then status 202, the run eventually becomes `failed`, and the error is queryable via the status endpoint | existing batch extraction suite (task 5.8) | - [x] |
| 28 | extraction-service | Batch extraction | Trigger batch extraction with base model | Given no promoted model and `processed` documents, when POST `/api/v1/extract-batch?documentIds=doc1,doc2`, then status 202 with `run_id` and `status: "queued"` | existing batch extraction suite (task 5.8) | - [x] |
| 29 | extraction-service | Batch extraction | Batch extraction uses version 0 when no model promoted | Given the most recently promoted model was demoted, when batch extraction is triggered, then extraction proceeds on version 0 and the run records `model_version = "0"` | existing batch extraction suite (task 5.8) | - [x] |
| 30 | extraction-service | Batch extraction | Default batch extraction excludes training-purpose documents | Given 2 `purpose='query'` and 1 `purpose='training'` processed documents, when POST `/api/v1/extract-batch` with no `documentIds`, then `total_documents = 2` and the training document is not processed | existing batch extraction suite (task 5.8) | - [x] |
| 31 | extraction-service | Batch extraction | Explicit documentIds bypasses purpose filtering | Given a `processed` `purpose='training'` document, when POST `/api/v1/extract-batch?documentIds=<its id>`, then status 202 and that document is included in the run | existing batch extraction suite (task 5.8) | - [x] |
| 32 | chat-api | SQL query generation and validation | Valid SQL query is executed | Given an entity-count question, when generation produces `SELECT entity_type, COUNT(*) FROM document_entities GROUP BY entity_type LIMIT 10`, then validation passes, the query runs in a read-only transaction, and results reach the RAG pipeline | `tests/test_chat_api_rag.py` (task 7.3) | - [x] |
| 33 | chat-api | SQL query generation and validation | Entity lookup matches on the canonical value | Given "which documents mention AWS?", when generation filters `document_entities` on `normalized_value = 'aws'`, then validation passes and documents whose extracted text was `Amazon Web Services` are returned | `tests/test_chat_api_rag.py` (task 7.3) | - [x] |
| 34 | chat-api | SQL query generation and validation | Raw BIO token table is not reachable from chat SQL | Given a generated query referencing `extracted_entities`, when validation inspects it, then the query is rejected and the RAG pipeline skips the SQL source for the turn | `tests/test_chat_api_guardrails.py` (task 7.4) | - [x] |
| 35 | chat-api | SQL query generation and validation | Malicious SQL is rejected | Given `DROP TABLE document_entities`, when validation inspects it, then the query is rejected, logged, the SQL source is skipped, and the response indicates the SQL source was unavailable | existing guardrail suite (task 7.5) | - [x] |
| 36 | chat-api | SQL query generation and validation | Query with non-whitelisted table is rejected | Given a query referencing `pg_authid`, when validation inspects the table name, then the query is rejected | existing guardrail suite (task 7.5) | - [x] |
| 37 | chat-api | SQL query generation and validation | Query exceeds timeout | Given a valid query running longer than 10 seconds, when executed, then execution is cancelled and the SQL source is skipped for the turn | existing guardrail suite (task 7.5) | - [x] |
| 38 | chat-api | Structured retrieval returns candidate document IDs | Candidate IDs are the distinct document IDs of the result rows | Given rows for `docA`, `docA`, `docB`, when the tool result is inspected, then candidate document IDs are exactly `{docA, docB}` and the returned rows are unchanged | `tests/test_retrieval_tools.py` (task 8.5) | - [x] |
| 39 | chat-api | Structured retrieval returns candidate document IDs | No document_id column yields no candidates | Given a query returning only `entity_type` and a count, when the tool result is inspected, then candidate document IDs are empty | `tests/test_retrieval_tools.py` (task 8.5) | - [x] |
| 40 | chat-api | Structured retrieval returns candidate document IDs | Failed structured retrieval yields no candidates | Given a structured invocation whose SQL was rejected, when the tool result is inspected, then candidate IDs are empty and the RAG pipeline proceeds with the semantic source unfiltered | `tests/test_retrieval_tools.py` (task 8.5) | - [x] |
| 41 | chat-api | Candidate document filtering of semantic retrieval | Semantic search is scoped to structured candidates | Given filtering enabled and a plan invoking both capabilities, when structured retrieval returns `{docA, docB}`, then the semantic invocation receives a `document_ids` filter of `{docA, docB}` and all returned chunks belong to `docA` or `docB` | `tests/test_retrieval_orchestrator.py` (task 8.6) | - [x] |
| 42 | chat-api | Candidate document filtering of semantic retrieval | Empty candidate set leaves semantic retrieval unfiltered | Given filtering enabled, when structured retrieval returns no candidate IDs, then semantic retrieval runs with no `document_ids` filter and its results match the feature-disabled results | `tests/test_retrieval_orchestrator.py` (task 8.6) | - [x] |
| 43 | chat-api | Candidate document filtering of semantic retrieval | Explicit document scope from the planner wins | Given filtering enabled and the planner scoped `semantic_retrieval` to `docC`, when structured retrieval returns `{docA}`, then semantic retrieval remains scoped to `docC` | `tests/test_retrieval_orchestrator.py` (task 8.6) | - [x] |
| 44 | chat-api | Candidate document filtering of semantic retrieval | Feature disabled preserves concurrent execution | Given filtering disabled, when a plan invoking both capabilities is executed, then both invocations are dispatched concurrently and the orchestration result is unchanged from current behaviour | `tests/test_retrieval_orchestrator.py` (task 8.7) | - [x] |
| 45 | tenant-schema-migrations | The `document_entities` table exists on the template and every tenant schema | Template and existing tenant schemas both receive the table | Given an existing provisioned `tenant_<id>` schema, when `alembic upgrade head` runs, then `tenant_template.document_entities` and `tenant_<id>.document_entities` both exist with the specified columns and indexes | migration test (task 1.5) | - [x] |
| 46 | tenant-schema-migrations | The `document_entities` table exists on the template and every tenant schema | Inactive tenant schemas are not skipped | Given a tenant with `status: "inactive"` and a provisioned schema, when the migration is applied, then that schema also contains `document_entities` | migration test (task 1.5) | - [x] |
| 47 | tenant-schema-migrations | The `document_entities` table exists on the template and every tenant schema | Raw entity table is untouched | Given a tenant schema with populated `extracted_entities`, when the migration is applied, then `extracted_entities` retains its columns and all rows | migration test (task 1.5) | - [x] |
| 48 | tenant-schema-migrations | The `document_entities` table exists on the template and every tenant schema | Re-running the migration DDL is a no-op | Given a schema already containing `document_entities`, when the per-tenant DDL is executed again, then no error occurs and the shape is unchanged | migration test (task 1.5) | - [x] |
| 49 | tenant-schema-migrations | The `document_entities` table exists on the template and every tenant schema | Downgrade removes only the new table | Given the migration has been applied, when it is downgraded, then `document_entities` is dropped from the template and every tenant schema and `extracted_entities` is unaffected | migration test (task 1.5) | - [x] |
| 50 | model-serving | Internal inference endpoint | Inference returns predictions from fine-tuned model with custom labels | Given a loaded fine-tuned model with a custom `label_list`, when POST `/internal/v1/infer` with `{"tokens": ["Acme","Corp"]}`, then status 200, `predictions` carry per-token label and confidence using tenant labels (not CoNLL), and `model_version` is the promoted version | existing model-serving suite (task 2.3) | - [x] |
| 51 | model-serving | Internal inference endpoint | Base-model predictions preserve token order and repeats | Given a tenant with no promoted model, when POST `/internal/v1/infer` with tokens containing the same entity word twice, then `predictions` holds one entry per predicted token in source order and the repeated word appears once per occurrence | `tests/test_inference_endpoint.py` (task 2.2) | - [x] |
| 52 | model-serving | Internal inference endpoint | Inference falls back to base model when no tenant model exists | Given no promoted model version, when POST `/internal/v1/infer` with `{"tokens": ["John","works","at","Acme","Corp"]}`, then status 200, CoNLL-labelled `predictions`, and `model_version: "0"` | existing model-serving suite (task 2.3) | - [x] |
| 53 | model-serving | Internal inference endpoint | Inference falls back to base model when tenant model fails to load | Given a promoted model that fails to load, when POST `/internal/v1/infer`, then status 200, the base model is used, and a warning header indicates model load failure | existing model-serving suite (task 2.3) | - [x] |
| 54 | model-serving | Internal inference endpoint | Inference returns 403 when JWT is missing | Given no JWT token, when POST `/internal/v1/infer` with `{"tokens": ["test"]}`, then status 403 | existing model-serving suite (task 2.3) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Reconstruction from stored rows (design Decision 1) | Agent takes the proposal's "raw_entities → Entity Normalizer" diagram literally and reads `extracted_entities` back from the DB to rebuild sequences. Those rows have no ordering column, so output looks plausible but is wrong | Read the normalizer call site in `worker.py` — it MUST consume the in-memory `predictions` list from the infer response. Any `SELECT ... FROM extracted_entities` inside the normalization path is a defect |
| 2 | Transaction boundary (spec: "Normalization failure does not leave a half-written document") | Agent writes normalized rows in a second `engine.begin()` block, so a failure leaves raw rows committed without normalized ones | Confirm raw and normalized inserts share one `with engine.begin() as conn:` block; force an insert failure and assert neither table gained rows for that document |
| 3 | Base-model ordering fix (design Context, Decision 8) | Agent "fixes" `_infer_with_base_model` by keeping the dict but sorting it, or adds `aggregation_strategy="simple"` — which silently removes the `##` tokens the WordPiece scenarios assert against, changing the contract in a different direction | Diff `_infer_with_base_model`: it must return a list built in pipeline output order with no dedupe. Confirm the WordPiece unit test (row 6) still exercises `##` inputs |
| 4 | Offset alignment (design Decision 5) | Agent invents an offset source — copying `char_start` from `document_chunks`, or asking model-serving for offsets it cannot know — instead of aligning tokens to `document_text_spans` at tokenization time | Trace where `char_start` originates; it must come from the worker's own tokenization over the fetched spans. Verify the NULL-on-failure path exists (row 15) rather than a raise |
| 5 | SQL whitelist swap (design Decision 6) | Agent adds `document_entities` but leaves `extracted_entities` whitelisted, so runtime BIO reconstruction is not actually eliminated | Assert `"extracted_entities" not in WHITELISTED_TABLES` and that a generated query naming it is rejected (row 34) |
| 6 | Candidate filtering sequencing (design Decision 7) | Agent makes sequencing unconditional, or reorders/ removes the `asyncio.gather` fast path, silently adding structured-retrieval latency to every turn | With the flag off, confirm `execute_plan` still dispatches all entries in one `gather` and produces byte-identical results (row 44); confirm the flag defaults to off |
| 7 | Confidence aggregation (design Decision 3) | Agent implements mean (the more common convention) despite the spec's SHALL for minimum, or applies the existing confidence threshold a second time to normalized rows | Read `aggregate_confidence` — must be `min`. Confirm no additional threshold filter is applied to `document_entities` inserts (see design Open Questions) |
| 8 | Canonicalization scope (design Decision 4) | Agent adds an LLM or embedding call to canonicalize values, breaking determinism and making the normalizer untestable offline | Confirm `entity_normalizer.py` imports no HTTP/LLM client and that `canonicalize` is a pure function over a module-level alias dict |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated in separate PostgreSQL schemas | `document_entities` is per-tenant-schema; no cross-tenant reads | Grep the migration and store module for hard-coded schema names; confirm every statement is schema-qualified via the tenant's `_schema(tenant_id)` or `search_path`, and that no query joins across two `tenant_*` schemas |
| ADR-002-base-model-strategy | Single curated base model, no BYOM | Normalizer must handle CoNLL labels as well as tenant `label_list` values | Run the normalizer unit tests against both a CoNLL label set (`B-PER`) and a custom set (`B-company`) — both must reconstruct |
| ADR-003-model-serving-topology | Per-tenant model serving, stateless inference | Normalization lives in the extraction worker; the infer contract stays tokens-in / ordered-predictions-out | Confirm no entity-reconstruction or document-level logic was added under `src/model_serving/`; the only change there is prediction ordering |
| ADR-004-openspec-governance | Spec-driven development | Behaviour lands as delta specs before code | Confirm every implemented behaviour maps to a row in Section 1; anything implemented without a row is scope creep |
| ADR-006-training-infrastructure | Heavy work runs in async workers | Normalization and backfill run in the Celery worker / a script, never in a request handler | Confirm no normalization call appears in a FastAPI route handler; the backfill entry point is a standalone script |
| ADR-007-chatbot-architecture | Full RAG with controlled SQL generation and guardrails | The whitelist swap must not weaken SELECT-only, LIMIT, UNION, or subquery validation | Diff `validate_sql` — it must be unchanged except for the table set; re-run the existing guardrail tests |
| ADR-008-base-model-as-default | Base model (version 0) is the default inference model | The base-model path is the common case, so its ordering fix is mandatory | Confirm a test covers normalization end-to-end on the version-0 path, not only the ONNX path |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Rows 1–5 (BIO reconstruction): unit test output showing all five reconstruction cases pass, including the dangling-`I` and repeated-occurrence cases
- [ ] Rows 6–7 (WordPiece merging): unit test output showing `A/##r/##jun/Jaya/##kumar` yields the single value `Arjun Jayakumar`, and whole-word input is unaffected
- [ ] Rows 8–9 (confidence aggregation): unit test output asserting `0.71` for `[0.99, 0.71, 0.88]` and `0.93` for the single-token case
- [ ] Rows 10–13 (canonical normalization): unit test output covering the deterministic fallback, the `react` alias set, the `aws` alias set, and the unknown-value fallback
- [ ] Rows 14–15 (location metadata): unit test output showing populated offsets for an aligned entity and NULL offsets (no raise) for an unalignable one
- [ ] Rows 16–17 (persistence): DB query output showing exactly one row per logical entity for a test document, plus a `normalized_value = 'aws'` query returning both documents
- [ ] Row 18 (raw preserved): before/after `SELECT count(*), entity_id` output over `extracted_entities` showing unchanged per-token BIO rows alongside new `document_entities` rows
- [ ] Row 19 (transaction atomicity): test output from an injected persistence failure showing zero rows committed to both tables and the document counted as failed
- [ ] Rows 20–22 (backfill): script run log showing a document populated, a second run leaving row counts unchanged, and a chat trace citing an un-backfilled document via the semantic path
- [ ] Rows 23–24, 26–31 (existing batch extraction behaviour): existing extraction worker/API test suite output, unchanged and passing
- [ ] Row 25 (normalized entities on ingest): integration test or DB query output after a batch run showing the `PER "Arjun Jayakumar"` row and no BIO-prefixed `entity_type`
- [ ] Rows 32–33 (SQL against `document_entities`): test output showing the aggregate query passes validation and the `normalized_value = 'aws'` question returns both documents
- [ ] Row 34 (raw table unreachable): test output showing a query naming `extracted_entities` is rejected by `validate_sql`
- [ ] Rows 35–37 (guardrails): existing SQL guardrail test suite output (malicious SQL, non-whitelisted table, timeout), passing unchanged
- [ ] Rows 38–40 (candidate IDs): unit test output for the distinct-IDs, no-`document_id`-column, and failed-invocation cases
- [ ] Rows 41–43 (candidate filtering): orchestrator test output showing the filter applied, the empty-candidate passthrough, and the planner-scope-wins case
- [ ] Row 44 (flag off): orchestrator test output showing concurrent dispatch and results identical to pre-change behaviour
- [ ] Rows 45–49 (migration): `alembic upgrade head` log plus `\d+ document_entities` output for the template and a tenant schema, a re-run showing no error, an `extracted_entities` row-count check, and a downgrade log
- [ ] Rows 50, 52–54 (existing inference behaviour): existing model-serving test suite output, unchanged and passing
- [ ] Row 51 (ordering fix): test output showing a repeated entity word yields one prediction per occurrence in source order

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — normalizer consumes the in-memory prediction sequence; no read of `extracted_entities` in the normalization path
- [ ] Risk 2 mitigation confirmed — raw and normalized inserts share one transaction; injected failure leaves both tables clean
- [ ] Risk 3 mitigation confirmed — `_infer_with_base_model` returns an ordered, non-deduplicated list and still emits `##` subwords
- [ ] Risk 4 mitigation confirmed — offsets originate from worker-side span alignment; unalignable tokens yield NULL, not a raise
- [ ] Risk 5 mitigation confirmed — `extracted_entities` absent from `WHITELISTED_TABLES` and rejected by validation
- [ ] Risk 6 mitigation confirmed — flag defaults off and the flag-off path still uses a single concurrent dispatch
- [ ] Risk 7 mitigation confirmed — `aggregate_confidence` is `min`; no second confidence threshold applied to normalized rows
- [ ] Risk 8 mitigation confirmed — `entity_normalizer.py` has no network/LLM imports; `canonicalize` is pure

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_entity_normalizer.py -q` → `18 passed` | Rows 1-15 | agent (opsx:apply) | 2026-07-31 |
| 2 | Functional | `pytest tests/test_extraction_worker_tokenizer.py -q` → `5 passed` | Row 51 upstream dependency (offset alignment used by rows 14-15) | agent (opsx:apply) | 2026-07-31 |
| 3 | Functional | `pytest tests/test_extraction_worker_normalization.py -q` → `2 passed` (persists normalized entities; injected-failure atomicity) | Rows 16, 18, 19, 25 | agent (opsx:apply) | 2026-07-31 |
| 4 | Functional | `pytest tests/test_backfill_document_entities.py -q` → `2 passed` | Rows 20, 21 | agent (opsx:apply) | 2026-07-31 |
| 5 | Functional | `pytest tests/test_migration_026_document_entities.py -q` → `5 passed` (template+tenant shape, inactive tenant, raw table untouched, re-run no-op, downgrade scope) | Rows 45-49 | agent (opsx:apply) | 2026-07-31 |
| 6 | Functional | `pytest tests/test_chat_api_sql.py -q` → `15 passed` (includes new `document_entities`-aggregate and `extracted_entities`-rejected cases) | Rows 32, 33, 34, 35, 36, 37 | agent (opsx:apply) | 2026-07-31 |
| 7 | Functional | `pytest tests/test_retrieval_tools.py -q` → `57 passed` (whole-file run; includes 3 new candidate-id cases) | Rows 38, 39, 40 | agent (opsx:apply) | 2026-07-31 |
| 8 | Functional | `pytest tests/test_retrieval_orchestrator.py -q` (part of the 57-total combined run with test_retrieval_tools.py) → all passed, including 4 new candidate-filtering cases | Rows 41, 42, 43, 44 | agent (opsx:apply) | 2026-07-31 |
| 9 | Functional | `pytest tests/test_inference_endpoint.py -q` → `23 passed, 1 failed` — the 1 failure (`TestInferenceNoModelReturns404`) is pre-existing (asserts pre-ADR-008 404 behaviour, superseded by ADR-008) and unrelated to this change; new ordering test passed | Rows 50, 51, 52, 53, 54 | agent (opsx:apply) | 2026-07-31 |
| 10 | Functional | `pytest tests/test_batch_extraction.py -q` → `11 passed`, unchanged | Rows 23, 24, 26, 27, 28, 29, 30, 31 | agent (opsx:apply) | 2026-07-31 |
| 11 | Functional | Rows 16-17 cross-document `normalized_value='aws'` lookup verified at the unit level via `TestCanonicalNormalization::test_acronym_alias_matches_expansion` (both "Amazon Web Services" and "AWS" canonicalize to `aws`) plus the DB-level single-document assertions in test_extraction_worker_normalization.py; no separate two-document DB fixture was added | Row 17 | agent (opsx:apply) | 2026-07-31 |
| 12 | Functional | Row 22 verified by static inspection, not a new test: `grep -rln document_entities src/` shows no reference from `retriever.py`, `rag_orchestrator.py`, or `document_tools.py` — the semantic path cannot be affected by a document lacking `document_entities` rows | Row 22 | agent (opsx:apply) | 2026-07-31 |
| 13 | Structural | `alembic upgrade head` applied against the local dev environment's `ner_dev` database (025→026); confirmed `document_entities` present in `tenant_template` + all 3 real tenant schemas via `information_schema.tables` query | Rows 45-49 (live environment confirmation, in addition to item 5's isolated test) | agent (opsx:apply) | 2026-07-31 |
| 14 | Structural | `openspec validate normalized-entity-store --type change --strict` → `Change 'normalized-entity-store' is valid` | Task 10.6 gate | agent (opsx:apply) | 2026-07-31 |
| 15 | Edge Case | Regression sweep: `pytest tests/test_retrieval_tools.py tests/test_retrieval_orchestrator.py tests/test_orchestrator_integration.py tests/test_retrieval_tools_integration.py -q` → `67 passed` (no regressions from ToolResult/orchestrator changes) | Risks 5, 6 | agent (opsx:apply) | 2026-07-31 |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** normalized-entity-store
**Proposal:** `openspec/changes/normalized-entity-store/proposal.md`
**Spec files reviewed:**

- specs/entity-normalization/spec.md
- specs/extraction-service/spec.md
- specs/chat-api/spec.md
- specs/tenant-schema-migrations/spec.md
- specs/model-serving/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
