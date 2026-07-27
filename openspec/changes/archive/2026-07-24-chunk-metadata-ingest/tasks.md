## 1. Database Migration

- [x] 1.1 Create `alembic/versions/021_document_chunks_page_metadata.py`: add `page_number INTEGER`, `char_start INTEGER`, `char_end INTEGER` (all nullable) to `tenant_template.document_chunks`, following migration 003's `ADD COLUMN IF NOT EXISTS` style
- [x] 1.2 In the same migration, loop over existing `tenant_%` schemas (excluding `tenant_template`) and apply the same three `ADD COLUMN IF NOT EXISTS`, following migration 010's `DO $$ ... FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%'` pattern
- [x] 1.3 Write `downgrade()` dropping the three columns from `tenant_template` and every `tenant_%` schema, matching migration 010's downgrade style
- [x] 1.4 Run the migration twice locally against a test database to confirm idempotency (covers Hallucination Risk 2) — ran via `alembic upgrade head`/`downgrade 020`/`upgrade head` in `ner-project-celery_worker-1` against `postgres-test`; also re-ran the raw upgrade SQL twice directly via psql (bypassing alembic's revision-skip) — clean `NOTICE: already exists, skipping` both times, no errors. **Found and fixed a real bug in the process**: the tenant-loop `ALTER TABLE` failed against `tenant_test_tenant` (a leftover schema from prior test runs with no `document_chunks` table — `conftest.py`'s tenant fixture doesn't create migration-010 chatbot tables) — changed `ALTER TABLE %I.document_chunks` to `ALTER TABLE IF EXISTS %I.document_chunks` in both upgrade and downgrade loops.

## 2. Domain Model & Chunking Changes

- [x] 2.1 Add `page_number: int | None = None`, `char_start: int | None = None`, `char_end: int | None = None` to `Chunk` in `src/shared/retrieval/models.py`
- [x] 2.2 Add the same three optional fields to `RetrievalResult` in the same file
- [x] 2.3 Update `chunk_text` in `src/shared/retrieval/chunking.py` to accept per-span metadata (`page_number`, `char_start` offset) and stamp it onto each produced `Chunk`; skip chunking entirely when the input text is empty/whitespace-only (covers scenario 8)
- [x] 2.4 Unit test: chunk a span with known `page_number=2`, `char_start=100`, `char_end=400`, assert every resulting `Chunk.page_number == 2` and `char_start`/`char_end` fall within `[100, 400]` (covers scenario 3) — `tests/test_chunk_metadata_ingest.py::TestChunkPageMetadata`
- [x] 2.5 Unit test: chunk an empty/whitespace-only span, assert zero chunks produced (covers scenario 8) — same class, `test_empty_span_produces_no_chunks`

## 3. Per-Span Ingestion in ocr_worker

- [x] 3.1 Update `src/document_service/services/ocr_worker.py::process_document` to chunk each span's text independently (via `chunk_text`) instead of joining all spans into one `full_text` before chunking; remove the `full_text` join used for chunking (the `document_text_spans` insertion logic itself is unchanged — only the chunking input changes)
- [x] 3.2 Update `_store_chunks` to persist `page_number`, `char_start`, `char_end` from each `Chunk` into the new `document_chunks` columns — **found and fixed a pre-existing bug while testing this against a live DB**: the embedding insert used `:embedding::vector`, which SQLAlchemy's `text()` never binds (its bind-param regex excludes `:name` immediately followed by `::`), so it was sent to Postgres as the literal string `:embedding::vector` and would always fail — this affected any real document ingestion, not just this change. Fixed to `CAST(:embedding AS vector)`.
- [x] 3.3 Unit/integration test: ingest a two-page document (two spans, page 0 and page 1), assert no resulting chunk contains text from both spans and each chunk's `page_number` matches its source span (covers scenario 7) — `tests/test_chunk_metadata_ingest.py::TestPerSpanIngestionChunkBoundary` — **PASSED** against live `postgres-test` (run via `ner-project-celery_worker-1`)
- [x] 3.4 grep test: confirm `document_text_spans` INSERT logic (columns, filtering) is byte-identical to before this change (covers Hallucination Risk 4) — `tests/test_chunk_metadata_ingest.py::TestOcrWorkerSpanInsertUnchanged`

## 4. DenseRetriever & Citation Wiring

- [x] 4.1 Update `DenseRetriever.retrieve`'s `SELECT` in `src/shared/retrieval/retriever.py` to include `page_number, char_start, char_end`, populating the new `RetrievalResult` fields; no other SQL clause changes
- [x] 4.2 Diff `DenseRetriever.retrieve`'s SQL against the `retrieval-foundation` version — confirm only the `SELECT` column list changed (covers Hallucination Risk 5) — `src/shared/retrieval` is uncommitted (no prior git revision to diff); `TestDenseRetrieverSqlDiff` instead asserts `WHERE`/`ORDER BY`/`LIMIT` clauses are unchanged and only `SELECT` gained columns
- [x] 4.3 Live pgvector test: insert a `document_chunks` row with `page_number=2, char_start=100, char_end=250`, retrieve it via `DenseRetriever`, assert `RetrievalResult` fields match (covers scenario 4) — `TestDenseRetrieverPageMetadata` — **PASSED** against live `postgres-test`
- [x] 4.4 Live pgvector test: insert a `document_chunks` row with `page_number`/`char_start`/`char_end` all `NULL`, retrieve it, assert `RetrievalResult` has `None` for all three and no exception (covers scenario 5) — same class — **PASSED**
- [x] 4.5 Update `RAGOrchestrator._enrich_citations` in `src/chat_api/services/rag_orchestrator.py` to populate `Citation.page_number` from the source `RetrievalResult`/`Source` when available
- [x] 4.6 Test: build a citation from a source with `page_number=3`, assert `Citation.page_number == 3` (covers scenario 11) — `TestCitationPageNumber::test_enrich_citations_populates_page_number_when_present`
- [x] 4.7 Test: build a citation from a source with no `page_number`, assert `Citation.page_number is None` and no exception (covers scenario 12) — same class, `test_enrich_citations_page_number_none_when_absent`

## 5. Regression Coverage

- [x] 5.1 Re-run `tests/test_retrieval_foundation.py` in full — confirm typed-model and single-chunking-implementation scenarios still pass (covers scenarios 1, 2, 6) — ran via `docker exec ner-project-celery_worker-1` against live `postgres-test`: all 9 tests PASSED (5 unrelated teardown-only errors from a pre-existing orphaned "Acme Corp" tenant referenced by `audit_events` — not touched, not this change's data, left alone; not a test-body failure). Required fixing `seeded_chunks` fixture's ad hoc `document_chunks` table to include the new nullable columns (DenseRetriever now selects them unconditionally).
- [x] 5.2 Re-run existing chat-api semantic search tests (`Semantic search returns relevant chunks`, `Semantic search with empty corpus`) — confirm unaffected by the new nullable columns (covers scenarios 9, 10) — covered by `TestDenseRetrieverParity` / `TestOrchestratorVectorSourceIntegration` in the same run above — PASSED

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. — 20/20 test assertions passed across `tests/test_chunk_metadata_ingest.py` + `tests/test_retrieval_foundation.py` against live `postgres-test` (see verification.md § Evidence Log for per-scenario mapping)
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. — populated with test run output; confirmed sufficient by human reviewer (Arjun, 2026-07-24)
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. — all 5 risks confirmed (1,3,4 via code review/grep; 2 via live migration run twice + raw-SQL re-run; 5 via SQL-clause assertion) — see verification.md
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance. — confirmed by human reviewer
- [x] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent). — signed by Arjun, 2026-07-24
- [x] 6.6 Run `openspec validate chunk-metadata-ingest --type change --strict` and confirm it exits clean before archive. — output: "Change 'chunk-metadata-ingest' is valid"
