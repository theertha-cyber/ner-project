## Context

The batch extraction Celery worker (`src/extraction_service/worker.py`) was written with three incorrect assumptions:

1. **Document text is available via HTTP** — the worker calls `GET /api/v1/tenants/{tid}/documents/{doc_id}/text`, which does not exist. The document service has no text endpoint; text is stored in the `document_text_spans` table, written there by the OCR worker.

2. **Idempotency can be checked via `extraction_runs.document_id`** — the worker queries `extraction_runs WHERE document_id IN (...)` to skip already-extracted documents. But the batch API endpoint inserts `extraction_runs` rows with `document_id = NULL` (by design, since one run covers many documents). The check always returns empty, so every document is always re-processed.

3. **Entities are findable by document** — `extracted_entities` has no `document_id` column. The entity query path in `entity_store.py` tries to reach entities via `extraction_runs.document_id`, which is NULL for batch runs. Queries by `documentId` return nothing.

This change fixes all three by: reading text from the DB, adding `document_id` to `extracted_entities`, checking idempotency against that column, and updating `query_entities` to filter directly on `extracted_entities.document_id`.

## Goals / Non-Goals

**Goals:**
- Make batch extraction actually produce entity rows in the database
- Make `GET /api/v1/entities?documentId=X` return results for batch-extracted documents
- Make re-running batch extraction on already-processed documents a no-op (idempotency)
- Remove the spurious `requests` HTTP call and JWT token generation for document text fetch

**Non-Goals:**
- Changing the batch API contract (202 response, run_id/status payload unchanged)
- Fixing `extraction_runs.document_id = NULL` for batch runs (intentional design — one run, many documents)
- Any change to the single-document real-time extraction path (`/api/v1/extract`)
- Optimising the sync engine connection pattern (separate concern)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | All tenant data lives in per-tenant schemas (`tenant_{id}`) | All SQL must use schema-qualified table names; no cross-tenant joins |
| ADR-003-model-serving-topology | Worker communicates with model serving via internal HTTP | The inference call stays as HTTP — only the document text fetch moves to DB |

## Decisions

### Decision 1: Read document text from `document_text_spans` directly in the worker

**Choice:** Replace the HTTP call with a synchronous SQL query: `SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id ORDER BY span_index NULLS LAST`. Concatenate spans with a space separator to reconstruct the full document text.

**Rationale:** The worker already uses a sync SQLAlchemy engine for all other DB operations (`_get_documents_to_process`, `_get_already_extracted`, entity INSERT). Adding one more query follows the established pattern. The HTTP call required creating an access token, managing a `requests` session, and handling HTTP errors — all of which can be removed.

**Alternatives considered:**
- Add a `/text` endpoint to the document service — adds an API surface and a network hop for something that's already in the shared DB; ruled out as unnecessary indirection
- Use an async HTTP call — adds complexity; the worker is already synchronous

### Decision 2: Add `document_id` to `extracted_entities` via Alembic migration

**Choice:** Add a nullable `VARCHAR` column `document_id` to `extracted_entities` in the tenant template and all existing tenant schemas. Populate it in the worker's INSERT statement.

**Rationale:** Entities need a direct path back to their source document for querying (`GET /entities?documentId=X`). The current indirection through `extraction_runs.document_id` is broken for batch runs. A direct column is the simplest and most queryable solution.

**Alternatives considered:**
- Fix the indirection — update the idempotency check to look at `extracted_entities` grouped by `document_id` — this still requires the column, so the migration is unavoidable
- Store `document_id` in a separate join table — unnecessary complexity; one column suffices

### Decision 3: Fix idempotency check against `extracted_entities.document_id`

**Choice:** Replace `_get_already_extracted` (which queries `extraction_runs`) with a query that checks `extracted_entities WHERE document_id IN (...) AND model_version = :version`. A document is "already extracted" if any entity row exists for it with the current model version.

**Rationale:** Once `document_id` is on `extracted_entities`, this is the natural, correct place to check. The `extraction_runs` table is a run-level aggregate; it is not the right place to track per-document completion state for batch runs.

**Alternatives considered:**
- Add a per-document status table — over-engineering for the current requirement
- Use `extraction_runs` with a per-document row — would require redesigning the batch run model

### Decision 4: Update `query_entities` to filter on `extracted_entities.document_id` directly

**Choice:** In `entity_store.py`, change the `document_id` filter from `e.run_id IN (SELECT id FROM extraction_runs WHERE document_id = ...)` to `e.document_id = :document_id`.

**Rationale:** Now that `document_id` is on the entity row itself, the subquery is unnecessary indirection. The direct filter is also more efficient (index on `document_id` rather than a correlated subquery).

## Risks / Trade-offs

- [Migration on existing tenant schemas may fail if a tenant schema was created before the template was updated] → Migration uses `ADD COLUMN IF NOT EXISTS` and a `DO $$ ... FOR EACH schema` loop, same pattern as migrations 003 and 007
- [Existing `extracted_entities` rows will have `document_id = NULL`] → Acceptable; those rows are from the (broken) pre-fix state. New extractions will populate the column correctly
- [Concatenating spans with space may produce slightly different token boundaries than the original OCR output] → Acceptable for NER tokenisation; word-boundary tokens are preserved

## Migration Plan

1. Run `alembic upgrade head` — adds `document_id` to `extracted_entities` in all schemas
2. Deploy updated worker image — new extractions immediately populate `document_id`
3. No rollback risk: the column is nullable and additive; downgrading the worker image restores the (broken) behaviour without data loss

## Open Questions

_(none — all open questions from proposal resolved in decisions above)_
