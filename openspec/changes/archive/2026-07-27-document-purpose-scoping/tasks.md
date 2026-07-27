## 1. Database Migration

- [x] 1.1 Create a new alembic migration (revision number assigned at implementation time, following whatever is head): add `purpose VARCHAR(20) NOT NULL DEFAULT 'query'` to `tenant_template.documents` and `tenant_template.document_chunks`
- [x] 1.2 Loop the same two `ADD COLUMN IF NOT EXISTS purpose` statements over every existing `tenant_%` schema, following migration 010/021's `DO $$` pattern
- [x] 1.3 In the same migration, per schema, backfill: `UPDATE {schema}.documents SET purpose = 'training' WHERE id IN (SELECT document_id FROM {schema}.annotation_tasks)`
- [x] 1.4 Write `downgrade()` dropping both `purpose` columns from `tenant_template` and every `tenant_%` schema
- [x] 1.5 Run the migration against a live Postgres instance; confirm idempotency by running twice; confirm backfill correctness against seeded demo data (some documents have existing annotation tasks) (covers Hallucination Risk 6)

## 2. Upload Endpoint

- [x] 2.1 Add an optional `purpose: str = Form("query")` field to `upload_document` in `src/document_service/api/v1/documents.py`; validate it's one of `{"query", "training"}`, returning 422 with a clear message otherwise
- [x] 2.2 Persist `purpose` on the `INSERT INTO {schema}.documents` statement
- [x] 2.3 Test: upload with no `purpose` field, assert stored `purpose == "query"` (covers scenario 4)
- [x] 2.4 Test: upload with `purpose=training`, assert stored `purpose == "training"` (covers scenario 5)
- [x] 2.5 Test: upload with `purpose=invalid-value`, assert 422 (covers scenario 6)
- [x] 2.6 Regression test: existing upload scenarios (PDF success, unsupported type, size limit) still pass unchanged (covers scenarios 1, 2, 3)

## 3. Ingestion Denormalization

- [x] 3.1 Update `process_document` in `src/document_service/services/ocr_worker.py` to fetch the document's `purpose` alongside its status update, and thread it through to `_store_chunks`
- [x] 3.2 Update `_store_chunks` to persist `purpose` on every `document_chunks` row it inserts
- [x] 3.3 Test: ingest a `purpose='training'` document, assert its resulting `document_chunks` rows all have `purpose='training'` (and same for `query`) (covers Hallucination Risk 2)

## 4. Retriever Purpose Filtering

- [x] 4.1 Update `DenseRetriever.retrieve`'s SQL in `src/shared/retrieval/retriever.py` to add an unconditional `AND purpose = 'query'` clause (literal, not parameterized/optional)
- [x] 4.2 If `SparseRetriever`/`HybridRetriever` exist at implementation time (from `hybrid-retrieval-hnsw`, in-flight independently), add the same unconditional clause to each; if they don't exist yet, this task is satisfied by `DenseRetriever` alone and the clause must be added to the others when they're written
- [x] 4.3 Live pgvector test: seed a `purpose='training'` document's chunks and a `purpose='query'` document's chunks, both matching a query; assert only `query`-purpose chunks are returned (covers scenario 9)
- [x] 4.4 Test: confirm no parameter or call path allows a caller to retrieve `purpose='training'` chunks via the chat-facing retriever (covers scenario 10, Hallucination Risk 1)
- [x] 4.5 Regression test: `DenseRetriever` parity tests from `retrieval-foundation`/`hybrid-retrieval-hnsw` still pass with the new clause added (covers scenarios 7, 8)

## 5. Annotation Task Purpose Enforcement

- [x] 5.1 Update `create_task` in `src/annotation_service/api/v1/tasks.py` to query the target document's `purpose` before creating the task; return 422 if not `training` (or 404 if the document doesn't exist)
- [x] 5.2 Test: create a task for a `purpose='training'` document, assert success (covers scenario 11)
- [x] 5.3 Test: create a task for a `purpose='query'` document, assert 422 (covers scenario 17)
- [x] 5.4 Regression tests: existing annotation-task scenarios (409 conflict, status filter list, status update, complete-with-spans, complete-without-spans-422) still pass (covers scenarios 12, 13, 14, 15, 16)

## 6. Document Picker Scoping

- [x] 6.1 Add a `purpose` query parameter to `GET /api/v1/documents` (`list_documents` in `src/document_service/api/v1/documents.py`), filtering results when provided
- [x] 6.2 Update `AssignTaskForm.tsx` to request `GET /api/v1/documents?purpose=training&...` instead of the unfiltered list
- [x] 6.3 Test: seed 2 `training` and 3 `query` documents, assert `AssignTaskForm`'s document fetch with `purpose=training` returns only the 2 training documents (covers scenario 18)

## 7. Batch Extraction Purpose Scoping

- [x] 7.1 Update `trigger_batch_extraction`'s "no explicit documentIds" branch in `src/extraction_service/api/v1/extraction.py` to add `AND purpose = 'query'` to the eligible-documents query
- [x] 7.2 Confirm the explicit-`documentIds` branch is unchanged (no purpose filter added there)
- [x] 7.3 Test: seed 2 `query` and 1 `training` processed documents, trigger batch extraction with no `documentIds`, assert `total_documents == 2` and the training document isn't processed (covers scenario 25)
- [x] 7.4 Test: trigger batch extraction with explicit `documentIds` naming a `training`-purpose document, assert it's included (covers scenario 26, Hallucination Risk 5)
- [x] 7.5 Regression tests: existing batch extraction scenarios (trigger, entity persistence, skip-already-extracted, no-promoted-model, base-model, version-0) still pass (covers scenarios 19, 20, 21, 22, 23, 24)

## 8. Frontend Upload Purpose Selection

- [x] 8.1 Add a `purpose` parameter to `useUpload()`'s `upload(file, purpose?)` in `src/portal/src/hooks/use-upload.ts`, appended to the `FormData`, defaulting to `"query"`
- [x] 8.2 Add a purpose toggle/radio to the Documents page's upload UI (query vs. training), wired to the new `upload()` parameter

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate document-purpose-scoping --type change --strict` and confirm it exits clean before archive.
