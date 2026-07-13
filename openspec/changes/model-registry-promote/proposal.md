## Why

The Model Registry displays only 1 model version instead of all available versions, and the training worker crashes when saving completed job metrics because `_update_job_progress` passes a raw dict to psycopg2. These two bugs prevent tenant admins from seeing their trained models and promoting them to production.

## What Changes

1. **Fix model listing API** — Replace `mv.latest_versions` (returns 1 per MLflow stage) with `client.search_model_versions()` to return ALL registered model versions.
2. **Fix `_update_job_progress` JSON serialization** — Serialize the `metrics` dict to JSON before passing it to the SQL UPDATE in the training worker, preventing the `can't adapt type 'dict'` crash.
3. **Fix worker status assignment** — The `model_versions` INSERT hardcodes `status='completed'` even when the job later fails. Change to insert with `status='training'` and update to `'completed'` only after `_update_job_progress` succeeds.

## Capabilities

### Modified Capabilities

- `model-registry`: Model listing must return all versions, not just the latest per MLflow stage. Promote/demote lifecycle is unchanged.
- `training-worker`: `_update_job_progress` must JSON-serialize the `metrics` parameter. `model_versions` status must not be hardcoded to `'completed'` before the job fully succeeds.

## Impact

- **`src/training_service/infra/mlflow_registry.py`**: `list_model_versions()` — replace `mv.latest_versions` with `client.search_model_versions()`
- **`src/training_service/worker.py`**: `_update_job_progress` call at line 401 and the `model_versions` INSERT at line 380 — fix JSON serialization and status assignment order
- **`src/training_service/api/v1/models.py`**: No changes needed (API shape unchanged)
- **Frontend**: No changes needed (already handles multiple versions)

## Open Questions

- None identified. Both bugs are confirmed in the running system.
