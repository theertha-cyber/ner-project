# Verification: Model Registry Promote

## AC Verification Matrix

| AC | Verification Artifact | Type | Fails When |
|---|---|---|---|
| Model listing returns all versions (not just latest per stage) | `tests/test_model_registry.py` — add test case using monkeypatched MLflow with 3 versions in same stage | Python test | Listing returns < 3 versions |
| Model listing from DB cache fallback returns all versions | Existing `test_mlflow_registry.py` test with MLflow unavailable | Python test | DB cache query returns wrong count |
| `_update_job_progress` accepts dict metrics | Unit test calling `_update_job_progress(metrics={"f1": 0.5})` | Python test | Crashes with `ProgrammingError` |
| `model_versions` inserted as `training`, updated to `completed` | Integration test: mock training completion, verify status transitions | Python test | Status is `completed` before `_update_job_progress` succeeds |
| Failed job sets `model_versions` status to `failed` | Integration test: force failure after model registration, verify `model_versions.status = 'failed'` | Python test | Row remains `completed` |
| Promote/demote unchanged | Existing promote/demote tests still pass | Python test | Previous test assertions fail |

## Test Harness Notes

- All tests in `tests/test_mlflow_registry.py` and `tests/test_model_registry.py` use monkeypatched MLflow client — no live MLflow or MinIO needed
- For `_update_job_progress` tests, use a real or in-memory SQLite/Postgres connection (sync engine)
- Existing `test_dashboard_summary.py` seeds model_versions — verify no regression

## Risks

- **Low**: MLflow `search_model_versions` API differs slightly across MLflow 2.x versions. Pin the MLflow version in tests.
- **Low**: Existing model_versions rows with incorrect `completed` status are not backfilled — acceptable for dev data.
