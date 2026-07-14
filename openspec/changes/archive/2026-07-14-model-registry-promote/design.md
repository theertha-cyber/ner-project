
# Design: Model Registry Promote

## Overview

Fixes two bugs that prevent the Model Registry from displaying all model versions and the training worker from completing successfully. No new capabilities — all changes are bugfixes that align existing behaviour with spec requirements.

---

## 1. Model Listing Returns Only 1 Version

### Current behaviour

`mlflow_registry.list_model_versions()` iterates over `mv.latest_versions`, which returns at most 1 version per MLflow stage (Staging, Production, Archived, or None). Since all model versions have `stage=None`, only the latest registered version is returned.

### Fix

Replace `mv.latest_versions` with `client.search_model_versions()`, which returns all versions regardless of stage.

**Before** (`mlflow_registry.py:108-132`):
```python
mv = client.get_registered_model(registered_model)
versions = []
for version in mv.latest_versions:       # ← 1 per stage
    run = client.get_run(version.run_id)
    ...
```

**After**:
```python
all_versions = client.search_model_versions(f"name='{registered_model}'")
versions = []
for version in all_versions:              # ← all versions
    run = client.get_run(version.run_id)
    ...
```

### Impact

- API shape unchanged (still returns `ModelVersionListResponse`)
- DB cache writes will now cache all versions, not just the latest per stage
- No frontend changes needed

---

## 2. `_update_job_progress` Crashes on Dict

### Current behaviour

At `worker.py:401-409`, `_update_job_progress()` is called with `metrics=json.dumps(metrics)` — this should work. But the error message shows the SQL failed with `can't adapt type 'dict'`.

Investigation reveals the problem: `_update_job_progress` uses `**fields` to build dynamic SQL. If any caller passes `metrics` as a raw dict (not JSON-string), psycopg2 can't adapt it. Currently the only call site that passes `metrics` is at line 401 which does use `json.dumps`. However, the error trace indicates the dict is reaching psycopg2, suggesting that between the `json.dumps` call and the SQL execution, the value is being modified or a different code path is involved.

### Fix

Move the JSON serialization INTO `_update_job_progress` itself so it always serializes dict-type metrics regardless of caller:

```python
def _update_job_progress(tenant_id: str, job_id: str, **fields):
    engine = _get_sync_engine()
    schema = _schema(tenant_id)
    set_clauses = []
    params = {"id": job_id}
    for key, val in fields.items():
        if isinstance(val, dict):
            val = json.dumps(val)        # ← serialize dicts automatically
        set_clauses.append(f"{key} = :{key}")
        params[key] = val
    ...
```

### Impact

- All callers of `_update_job_progress` are protected from the same bug
- No schema change — `training_jobs.metrics` is already JSONB

---

## 3. `model_versions` Status Hardcoded to `completed`

### Current behaviour

At `worker.py:380-399`, the `model_versions` INSERT hardcodes `status='completed'`. If `_update_job_progress` or `mlflow.end_run` subsequently fails, the model_versions row remains `completed` even though the training_jobs record shows `failed`.

### Fix

Insert `model_versions` with `status='training'` and update it to `status='completed'` only after `_update_job_progress` succeeds:

```python
# INSERT with status='training' instead of 'completed'
conn.execute(text(f"""
    INSERT INTO {schema}.model_versions
        (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, created_at, mlflow_run_id)
    VALUES (:id, :tenant_id,
        (SELECT COALESCE(MAX(version_number), 0) + 1 FROM {schema}.model_versions WHERE tenant_id = :tenant_id2),
        :training_job_id, 'training', CAST(:metrics AS jsonb), :artifact_path, :now, :mlflow_run_id)
"""), {...})

# After _update_job_progress succeeds, update to 'completed'
conn.execute(text(f"""
    UPDATE {schema}.model_versions SET status = 'completed'
    WHERE id = :id AND tenant_id = :tenant_id
"""), {"id": version_id, "tenant_id": tenant_id})
```

In the exception handler, if the model_versions row exists, update it to `status='failed'`.

### Impact

- Aligns `model_versions.status` with actual training outcome
- Training jobs that fail after model registration will show `failed` in both tables
- Existing rows with incorrect `completed` status will not be backfilled (minor inconsistency for past failed runs)

---

## Files Changed

| File | Change |
|---|---|
| `src/training_service/infra/mlflow_registry.py` | `list_model_versions()`: replace `latest_versions` with `search_model_versions()` |
| `src/training_service/worker.py` | `_update_job_progress()`: auto-serialize dict params; `fine_tune_model()`: fix `model_versions` status lifecycle |
