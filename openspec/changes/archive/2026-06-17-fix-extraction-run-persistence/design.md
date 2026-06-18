## Context

The batch extraction endpoint (`POST /extract-batch`) dispatches a Celery task and returns immediately with a `run_id`. The Celery worker (`run_batch_extraction` in `worker.py`) processes documents but **never calls `_create_run`** — so no row exists in `extraction_runs`. When the client calls `GET /extract-batch/{run_id}`, `get_extraction_run` returns `None` and the endpoint raises `404`.

Additionally, the `extraction_runs` table (created in migration 002) only has columns `id, tenant_id, document_id, model_version, status, started_at`. The worker calls `_update_run_status(..., completed_at=...)` which would fail because `completed_at` doesn't exist. The `BatchRunStatus` response model also expects `total_documents`, `processed_count`, `skipped_count`, `failed_count` — none of which exist in the table.

## Goals / Non-Goals

**Goals:**

- Extraction run rows are persisted in the database before or during Celery task execution.
- `GET /extract-batch/{run_id}` returns a proper `200` response with all expected fields (`status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `completed_at`, `started_at`, `model_version`).
- The `extraction_runs` table has all columns required by the worker and API.
- Existing Celery task failure handling (`_update_run_status("failed")`) works correctly.
- Minimize race window between POST dispatch and GET query.

**Non-Goals:**

- Changing the API contract or response schema for existing endpoints.
- Refactoring the per-document `extraction_runs` model to a separate batch-runs table (deferred).
- Adding new API capabilities beyond what the existing spec describes.
- Modifying `extracted_entities` FK constraints or data model.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Per-tenant PostgreSQL schema isolation (`tenant_<uuid>`) | All DB operations must use the `_schema(tenant_id)` pattern already in place |
| ADR-008 | Base model version "0" is the default when no promoted model exists | `_get_active_model_version` returning `"0"` is correct — `_create_run` should accept it |

All other ADRs (002-007) do not constrain this change.

## Decisions

### Decision 1: Pre-create the run row in the POST handler (synchronous insert)

**Choice:** Insert the `extraction_runs` row synchronously in `trigger_batch_extraction` before dispatching the Celery task, with `status: "queued"`, `total_documents` set to the count of provided document IDs, and `processed_count` / `skipped_count` / `failed_count` set to 0.

**Rationale:** Eliminates the race window entirely. The GET endpoint can immediately return `status: "queued"` with progress counts without waiting for the worker to start. Small latency cost on the POST path (one INSERT) is acceptable for correctness.

**Alternatives considered:**
- Insert in the Celery task right before `_update_run_status("running")` — simpler (no change to the API layer) but the race window between POST return and Celery pickup is unbounded (could be seconds in a backed-up queue). The GET would 404 during that window.
- Insert in the Celery task but return a pre-dispatch confirmation — requires a two-phase approach (POST creates `id` + registers intent, worker fills in details) which is over-engineered for this fix.

### Decision 2: Single row per batch run (not one per document)

**Choice:** Create ONE `extraction_runs` row per batch run, not one per document as the current schema and `_create_run` function imply. The `document_id` column becomes NULLABLE or we use a separate `batch_runs` table.

**Rationale:** The GET endpoint's `get_extraction_run` does a simple `SELECT * ... WHERE id = :id` and `fetchone()` — it expects exactly one row per run. Per-document rows would require aggregation logic (SUM over multiple rows) to compute `processed_count`, `skipped_count`, `failed_count`, which adds complexity and breaks the current simple implementation.

Note: This is a **data model change** from how `_create_run` was originally designed (it takes a `doc_id` parameter, implying per-document rows). We change the semantics: the batch run is a single aggregate row.

**Alternatives considered:**
- Keep per-document rows and aggregate — requires a new `batch_runs` parent table or computed columns. More work, more risk. The current code has no multi-row aggregation anywhere.
- Use a separate `batch_runs` table with `run_id` as FK from `extraction_runs` — cleaner but requires a migration to create a new table AND populate it. Over-engineered for this fix.

### Decision 3: New Alembic migration adding six columns

**Choice:** Create migration `007_add_extraction_run_columns.py` that adds `completed_at TIMESTAMPTZ`, `total_documents INTEGER NOT NULL DEFAULT 0`, `processed_count INTEGER NOT NULL DEFAULT 0`, `skipped_count INTEGER NOT NULL DEFAULT 0`, `failed_count INTEGER NOT NULL DEFAULT 0`, and makes `document_id` NULLABLE.

**Rationale:** The `document_id` column was designed for per-document rows. With the single-row-per-batch approach, it needs to be nullable (we won't populate it for the aggregate run row). The five numeric/count columns are required by the `BatchRunStatus` schema. The migration must apply to all existing tenant schemas (not just the template).

**Alternatives considered:**
- Drop `document_id` entirely — would break existing data references. Nullable is safer for backward compatibility.

## Risks / Trade-offs

- [Data migration complexity] → The migration script must iterate all tenant schemas and apply the ALTER TABLE. The `for_each_tenant_schema()` helper from prior migrations can be reused.
- [Extracted entities FK constraint on `run_id`] → The FK `REFERENCES tenant_template.extraction_runs(id) ON DELETE CASCADE` references the `extraction_runs` table which now has nullable `document_id`. This does not affect the FK since `run_id` is still the PK. No change needed.
- [Existing extraction_runs rows have document_id populated] → For any existing rows, `document_id` stays intact (column is now nullable, existing data unchanged). New batch runs will have `document_id = NULL`.
- [Celery worker may execute before migration is applied] → Deployment must run the migration before the new code is deployed. Use a two-step deploy: migration first, then code rollout.

## Migration Plan

1. Apply migration `007_add_extraction_run_columns.py` to all tenant schemas.
2. Deploy updated `worker.py` and `extraction.py` (post handler insert + worker `_create_run` call removal).
3. Verify: POST a batch extraction → GET returns 200 with `status: "queued"`.
4. Wait for Celery to complete → GET returns 200 with `status: "completed"`.

**Rollback:** Revert the code deploy, then downgrade migration 007. No data loss expected (nullable columns only, no destructive changes).

## Open Questions

None — all decisions are scoped to the implementation fix described above.
