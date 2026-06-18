## Why

Batch extraction runs return `404` when queried because no `extraction_runs` row is ever persisted. The Celery worker never calls `_create_run`, and the table lacks columns (`completed_at`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`) that both the worker and the GET endpoint expect, so even a partial fix would fail at runtime.

## What Changes

- Call `_create_run` in the Celery worker **before** processing documents so a row exists immediately.
- Add a new Alembic migration that adds the missing columns to `extraction_runs`.
- Redesign the worker to create **one row per batch** (not one row per document) so `get_extraction_run` returns a complete status record.
- Optionally pre-create the run row synchronously in the POST handler to eliminate the race window between dispatch and worker pickup.

## Capabilities

### New Capabilities

- *(none — this is a bug fix for existing capabilities)*

### Modified Capabilities

- `extraction-service`: Batch extraction run persistence — the existing "Batch extraction" and "Get extraction run status" requirements are not met because run records are missing from the database. This change repairs that gap.

## Impact

| Area | Impact |
|------|--------|
| `src/extraction_service/worker.py` | Add `_create_run` call; change status-update flow to match single-row-per-batch model |
| `src/extraction_service/api/v1/extraction.py` | Optionally insert a run row synchronously on POST |
| `src/extraction_service/services/entity_store.py` | Adjust `get_extraction_run` if schema changes |
| Alembic migrations | New migration for missing columns |
| `extraction_runs` table schema | Adds `completed_at`, `total_documents`, `processed_count`, `skipped_count`, `failed_count` |
| Gateway proxy | No change — same API contract |

## Open Questions

1. Should the POST handler pre-insert the run row synchronously (`status: "queued"`) or should the Celery worker remain the sole writer? Pre-insertion eliminates the race window but adds a DB write to the request path.
2. Should `extracted_entities` rows link to the batch run or directly to the document? Currently they reference `run_id` — a single batch-run row would make that FK consistent.
