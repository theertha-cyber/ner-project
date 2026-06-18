## 1. Schema Migration

- [x] 1.1 Create `alembic/versions/008_add_document_id_to_extracted_entities.py` — add nullable `document_id VARCHAR` column to `extracted_entities` in `tenant_template` schema
- [x] 1.2 In the same migration, add the `DO $$ ... FOR EACH schema LIKE 'tenant\_%'` loop to apply the column to all existing tenant schemas (same pattern as migrations 003 and 007)
- [x] 1.3 Run `alembic upgrade head` and confirm it completes without error

## 2. Worker — Replace HTTP Text Fetch with DB Query

- [x] 2.1 In `src/extraction_service/worker.py`, remove the `import requests` call, `create_access_token` call, `text_url` construction, `requests.get(...)` call, and the `if text_resp.status_code != 200` guard — all within the per-document loop
- [x] 2.2 Replace with a synchronous SQL query: `SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id ORDER BY span_index NULLS LAST` using the existing `_get_sync_engine()` pattern
- [x] 2.3 Concatenate spans with a space separator to form `doc_text`, then split to `tokens`
- [x] 2.4 Add guard: `if not tokens: failed += 1; continue` immediately after the span query

## 3. Worker — Fix Idempotency Check

- [x] 3.1 Replace `_get_already_extracted` to query `extracted_entities WHERE document_id IN (...) AND model_version = :model_version` instead of `extraction_runs WHERE document_id IN (...)` — implemented via JOIN on `extraction_runs` to access `model_version`
- [x] 3.2 Confirm the function still returns a `set[str]` of document IDs (interface unchanged, callers unaffected)

## 4. Worker — Populate `document_id` on Entity INSERT

- [x] 4.1 Add `document_id` to the column list in the `INSERT INTO {schema}.extracted_entities` statement in the worker loop
- [x] 4.2 Add `"document_id": doc_id` to the params dict for that INSERT
- [x] 4.3 Confirm the `serving_token` creation (second token for inference) is still present and unchanged — do not accidentally remove the inference HTTP call

## 5. Entity Store — Fix `query_entities` Document Filter

- [x] 5.1 In `src/extraction_service/services/entity_store.py`, change the `document_id` filter condition from `e.run_id IN (SELECT id FROM {schema}.extraction_runs WHERE document_id = :document_id)` to `e.document_id = :document_id`
- [x] 5.2 Confirm the `{schema}` replacement on `where_clause` still works correctly after the change (the old subquery contained `{schema}` inline; the new condition does not)

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.6 Run `openspec validate fix-batch-extraction-worker --type change --strict` and confirm it exits clean before archive.
