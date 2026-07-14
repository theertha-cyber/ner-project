# Model Registry — Delta

**Base spec**: `openspec/specs/model-registry/spec.md`

## Changes

### 1. List model versions — fix implementation to match spec

The spec already requires listing **all** model versions (Requirement: List model versions). The implementation uses MLflow's `latest_versions` which returns only 1 version per stage. This delta confirms the spec requirement is correct and the implementation must use `search_model_versions()` instead.

No requirement text changes — this is an implementation alignment fix.

### 2. New scenario: List models with mixed stages

Adds a scenario covering the actual bug case where all versions share the same stage.

#### Scenario: List all versions when multiple exist in same MLflow stage

- **GIVEN** a tenant with 3 registered model versions, all in MLflow stage `None`
- **WHEN** a Tenant Admin GETs `/api/v1/models`
- **THEN** the response SHALL contain all 3 versions
- **AND** each version SHALL include `version_number`, `status`, `training_job_id`, `created_at`, `metrics`, `mlflow_run_id`, and `mlflow_run_url`
