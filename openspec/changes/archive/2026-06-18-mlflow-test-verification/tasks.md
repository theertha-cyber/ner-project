## 1. Setup & Dependencies

- [x] 1.1 Add `@pytest.mark.verification` marker to `pytest.ini`
- [x] 1.2 Ensure `NER_MLFLOW_INTEGRATION_TESTS` env var gating is applied to the test class
- [x] 1.3 Confirm test preconditions documented: MLflow on :5000, PostgreSQL on 5432/54320

## 2. Infrastructure Health Tests

- [x] 2.1 `test_server_health` — GET /health returns 200 for MLflow server
- [x] 2.2 `test_create_experiment` — Create experiment `tenant_{tid}` and verify name

## 3. Experiment & Run Lifecycle Tests

- [x] 3.1 `test_create_run_with_params_tags` — Create run with `log_params()` (learning_rate, num_epochs, batch_size, max_seq_length) and `set_tags()` (base_model, tenant_id, training_job_id, num_labels); verify readback
- [x] 3.2 `test_log_metrics_per_step` — Log eval_f1 at steps 0 and 1; verify metric history
- [x] 3.3 `test_run_failure_status` — Set run to FAILED with error_message tag; verify status and tag

## 4. Model Registration Tests

- [x] 4.1 `test_register_model` — Create registered model `tenant_{tid}_ner_model` with version from a run; verify model exists and references correct run

## 5. Model Registry Proxy Tests

- [x] 5.1 `test_list_model_versions` — After registering a model, call `list_model_versions()`; verify response contains version_number, status, mlflow_run_id, mlflow_run_url
- [x] 5.2 `test_promote_model` — Promote a Staging version to Production; verify MLflow stage changed and `get_active_model()` returns it
- [x] 5.3 `test_promote_archives_previous` — With v1 in Production and v2 in Staging, promote v2; verify v2 is Production, v1 is Archived
- [x] 5.4 `test_demote_model` — Demote Production version back to Staging; verify no active model
- [x] 5.5 `test_list_empty_no_registered_model` — Call `list_model_versions()` for tenant with no model; verify empty list and no warning

## 6. Cache Fallback Tests (Monkeypatched MLflow)

- [x] 6.1 `test_cache_fallback_list` — Seed DB cache, monkeypatch MLflow to raise exception, call `list_model_versions()`; verify cached list returned with `mlflow-unavailable` warning
- [x] 6.2 `test_cache_fallback_active` — Seed promoted model in DB cache, monkeypatch MLflow exception, call `get_active_model()`; verify cached model with warning

## 7. Tenant Isolation Tests

- [x] 7.1 `test_tenant_isolation` — Register model for Tenant A; verify Tenant B's `list_model_versions()` does not include it; verify naming conventions differ

## 8. Status Mapping Tests

- [x] 8.1 `test_status_to_stage_mapping` — Verify `STATUS_TO_STAGE` and `STAGE_TO_STATUS` roundtrip: completed↔Staging, promoted↔Production, archived↔Archived

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass — 17/17 passed
- [x] 9.2 Collect functional evidence (test output) for each scenario — recorded in verification.md § Evidence Log
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 9.6 Run `openspec validate mlflow-test-verification --type change --strict` and confirm it exits clean before archive
