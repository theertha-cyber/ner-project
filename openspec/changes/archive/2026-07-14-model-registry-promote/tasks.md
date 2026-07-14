# Tasks: Model Registry Promote

## Pre-Flight

- [x] Load the relevant specs and code files for context

## Task 1: Fix `list_model_versions` to return all versions

**File**: `src/training_service/infra/mlflow_registry.py:103-139`

Replace `mv.latest_versions` with `client.search_model_versions()`:

```python
# Before
mv = client.get_registered_model(registered_model)
for version in mv.latest_versions:

# After
all_versions = client.search_model_versions(f"name='{registered_model}'")
for version in all_versions:
```

Keep the same response dict shape. The `get_registered_model` call is no longer needed for listing (remove it), but keep the outer try/except for MLflow unavailability fallback.

**Verification**: Run `pytest tests/test_mlflow_registry.py -v`. New test asserts 3 versions returned when MLflow has 3 versions in same stage.

## Task 2: Fix `_update_job_progress` to JSON-serialize dict values

**File**: `src/training_service/worker.py:120-133`

In `_update_job_progress()`, add `isinstance(val, dict)` check inside the loop to auto-serialize dict values:

```python
for key, val in fields.items():
    if isinstance(val, dict):
        val = json.dumps(val)
    set_clauses.append(f"{key} = :{key}")
    params[key] = val
```

**Verification**: Call `_update_job_progress(tenant_id, job_id, status="completed", metrics={"f1": 0.5})` without crashing. No SQL-level changes needed.

## Task 3: Fix `model_versions` status lifecycle in training worker

**File**: `src/training_service/worker.py:378-399`

1. Change INSERT to use `status='training'` instead of `status='completed'`
2. After `_update_job_progress` succeeds, add an UPDATE to set `model_versions.status = 'completed'`
3. In the exception handler (line 413-420), add an UPDATE to set `model_versions.status = 'failed'` (use try/except to handle case where INSERT hadn't run yet)

**Verification**: Integration test confirms:
- Row starts as `training`
- Becomes `completed` after successful job
- Becomes `failed` if `_update_job_progress` fails

## Task 4: Add verification tests

**File**: `tests/test_mlflow_registry.py`

Add test for `list_model_versions` returns all versions when MLflow has 3 versions in `None` stage:
- Monkeypatch MLflow client's `search_model_versions` to return 3 versions
- Assert `len(result) == 3`
- Assert each result has expected fields

**File**: `tests/test_model_registry.py` (or `tests/test_training_jobs.py`)

Add test for `_update_job_progress` with dict metrics:
- Call with `metrics={"f1": 0.5}`
- Assert no exception

Add test for `model_versions` status lifecycle:
- Call `fine_tune_model` with mocked training
- Assert status transitions: `'training'` → `'completed'`
- Force failure, assert `'failed'`

## Implementation Order

1. Task 1 (model listing fix) — self-contained, no deps
2. Task 2 (`_update_job_progress` fix) — self-contained, no deps
3. Task 3 (model_versions status lifecycle) — depends on Task 2
4. Task 4 (tests) — depends on Tasks 1-3

## Files to Modify

- `src/training_service/infra/mlflow_registry.py`
- `src/training_service/worker.py`
- `tests/test_mlflow_registry.py` (or create new test file)
