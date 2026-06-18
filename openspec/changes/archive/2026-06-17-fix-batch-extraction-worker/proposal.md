## Why

Batch extraction is completely non-functional: the Celery worker attempts to fetch document text via an HTTP endpoint that does not exist in the document service, causing every document to fail silently. Additionally, the idempotency check always returns an empty set because it queries a column that is always NULL for batch runs, and extracted entities cannot be queried by document because there is no link from an entity back to the document it came from.

## What Changes

- Replace the non-existent HTTP call to `/api/v1/tenants/{tid}/documents/{doc_id}/text` with a direct SQL query against `document_text_spans`
- Add `document_id` column to `extracted_entities` table (new Alembic migration) so entities know which document they came from
- Fix `_get_already_extracted` in `worker.py` to check `extracted_entities.document_id` (not `extraction_runs.document_id`, which is NULL for batch runs)
- Populate `document_id` in every `extracted_entities` INSERT in the worker
- Remove now-unused `requests` HTTP call, JWT token generation for document fetch, and `document_service_url` dependency inside the worker loop

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `extraction-service`: Batch extraction requirement gains new observable behaviours — entity rows SHALL be linked to their source document, and idempotency SHALL skip documents whose entities are already present for the active model version

## Impact

- **`src/extraction_service/worker.py`**: remove HTTP text fetch, add DB query for spans, fix idempotency check, populate `document_id` on INSERT
- **`alembic/versions/`**: new migration adding `document_id` column to `extracted_entities` in `tenant_template` and all existing tenant schemas
- **No API contract changes** — all existing endpoints are unaffected
- **`entity_store.py`**: `query_entities` filter by `document_id` will work correctly after the migration with no code change required (it already queries through `extraction_runs.document_id`, but see Open Questions)

## Open Questions

1. `query_entities` in `entity_store.py` filters by document via `extraction_runs.document_id`, which is still NULL for batch runs. Should we also update `query_entities` to filter directly on `extracted_entities.document_id` instead? (**Assumed yes** — adding `document_id` to `extracted_entities` makes this the natural and correct path.)
2. Should `document_id` be NOT NULL in `extracted_entities`? Single-document runs via `extraction_engine.py` do not currently write to `extracted_entities`, so making it NOT NULL would only affect the worker. (**Assumed nullable** — keeps the column additive and non-breaking for any future single-doc path.)
