## 1. Training Worker — S3 Path Fix

- [x] 1.1 In `worker.py:_save_artifacts()`, change artifact_path from `f"tenants/{tenant_id}/models/v1/{version_id}/"` to `f"tenants/{tenant_id}/models/v{version_number}/"`. The function signature must accept `version_number: int` instead of `version_id: str`. (Already correct in current code — verified.)
- [x] 1.2 In `worker.py:fine_tune_model()`, compute `version_number` from `MAX(version_number) + 1` BEFORE calling `_save_artifacts()`, and pass `version_number` (not `version_id`) to `_save_artifacts()`. (Already correct in current code — verified.)
- [x] 1.3 Verify the INSERT statement at line 384 uses the same `version_number` for the `version_number` column and that `artifact_path` matches the new format.

## 2. Training Worker — label_list Persistence

- [x] 2.1 In `worker.py:fine_tune_model()`, add `"label_list": label_list` to the `metrics` dict (around line 355-360) BEFORE `json.dumps(metrics)` is called.
- [x] 2.2 Verify the label_list variable (from `_extract_label_set()` at line 216) is the same one added to metrics — it should be `["O"] + sorted(non-O labels)`.
- [x] 2.3 Write a unit test that trains a small model and asserts `model_versions.metrics` contains a `label_list` key with the expected BIO tags. (`tests/test_training_worker.py::TestLabelListPersistedInMetrics`, `@pytest.mark.slow`, real training run — passing.)

## 3. Model Serving — Loader Path Parameter

- [x] 3.1 In `model_loader.py:download_model_artifacts()`, add `artifact_path: str` parameter and remove the internal path construction (`artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"`).
- [x] 3.2 In `inference_service.py:_load_model_for_tenant()`, pass the `artifact_path` from `_resolve_active_version()` to `download_model_artifacts()`.
- [x] 3.3 In `inference_service.py:_infer_with_onnx()`, thread the `artifact_path` through to `_load_model_for_tenant()`.

## 4. Model Serving — label_list Resolution

- [x] 4.1 Verify `_resolve_label_list()` in `inference_service.py` reads `metrics.label_list` from the API response (already implemented at line 204-206).
- [x] 4.2 Verify `_infer_with_onnx()` uses the resolved `label_list` to map predicted IDs to label strings (already implemented at line 122-124, 138).
- [x] 4.3 Write a test that mocks the active model API to return a model with custom label_list, runs ONNX inference, and asserts the output labels are the custom labels (not CoNLL). (`tests/test_inference_endpoint.py::TestInferenceCustomLabelList` — passing.)
- [x] 4.4 (Added — not in original scope, required for 4.1/4.2 to actually work) Fixed `models.py:_row_to_response()` to read `label_list` from `metrics.label_list` instead of a nonexistent top-level `label_list` column, and fixed `mlflow_registry.py` (`get_active_model`, `list_model_versions`, `promote_model_version`, `demote_model_version`) to recover `label_list` from an MLflow run param (`mlflow.log_param("label_list", json.dumps(label_list))` in worker.py) since MLflow's numeric-only `log_metrics` cannot store it. See design.md addendum below.

## 5. Migration — Backfill label_list

- [x] 5.1 Create a new Alembic migration that queries all `model_versions` rows with `status IN ('completed', 'promoted')`.
- [x] 5.2 For each model version, join to the tenant's `entity_definitions` table to reconstruct the label list as `["O"] + sorted(["B-{entity}", "I-{entity}" for each entity])`.
- [x] 5.3 Update the `metrics` JSONB column to include `"label_list": [...]` for each affected row.
- [x] 5.4 Write a down migration that removes `label_list` from the metrics JSONB.
- [x] 5.5 Test the migration against a database with sample model_versions and entity_definitions rows. (Ran upgrade/downgrade/upgrade against local dev DB `ner_dev`; verified output for tenants with and without `entity_definitions`.)

## 6. Model Serving — Training Service URL Configuration

- [x] 6.1 Add `training_service_url: str = "http://localhost:8003"` to `Settings` in `src/shared/config.py`, following the existing `model_serving_url`/`extraction_service_url`/`document_service_url` pattern.
- [x] 6.2 In `inference_service.py:_resolve_active_version()`, replace the hardcoded `registry_url = f"http://training_service:8003/api/v1/models/active"` with `registry_url = f"{settings.training_service_url.rstrip('/')}/api/v1/models/active"`.
- [x] 6.3 In `inference_service.py:_resolve_label_list()`, apply the same fix (currently duplicates the same hardcoded literal at line 194).
- [x] 6.4 Add `NER_TRAINING_SERVICE_URL: "http://training_service:8000"` to the `model_serving` service block in `docker-compose.yml`.
- [x] 6.5 Write/update a test that mocks `training_service_url` pointing at a real port and asserts `_resolve_active_version()` successfully connects and parses the response (regression guard for the wrong-port bug). (`tests/test_inference_endpoint.py::TestResolveActiveVersionUsesConfiguredRegistryUrl` — 3 cases added; logic verified standalone since the repo's pytest DB fixture targets a separate test Postgres on port 54320 that isn't currently running — unrelated pre-existing gap, not part of this change.)

## 7. Docker Compose — Training Service Warmup Routing

- [x] 7.1 Add `NER_MODEL_SERVING_URL: "http://model_serving:8000"` to the `training_service` service block in `docker-compose.yml`, matching `gateway`, `chat_api`, and `extraction_service`.
- [x] 7.2 Manually verify: promote a completed model version via the portal or API, confirm the connection to model_serving succeeds. (Rebuilt and restarted `model_serving`/`training_service` with the fixes live; promoted tenant `4126ebb0-da07-4d09-bc46-df79c7c6933e`'s v5 via `POST /api/v1/models/5/promote` — confirmed `GET /api/v1/models/active` now arrives at training_service from model_serving's own container IP for the first time, and a direct authenticated call to `POST /api/v1/models/5/warmup` returns `{"status":"ok","version_number":5}`. Note: the success path logs via `logger.info(...)`, which the container's log level filters out — only the failure path (`logger.warning`) is visible in `docker logs`; confirmed success via the HTTP response and via `_resolve_active_version()`'s return value instead. This logging-level gap is a minor pre-existing observability issue, not fixed here.)
- [x] 7.3 Manually verify: after promotion, trigger an extraction request for that tenant and confirm the response uses the promoted model's custom labels, not CoNLL/`B-MISC`. (Initial attempt still returned `model_version: "0"` / base — traced to a fourth, independent bug: see section 9. After fixing section 9, `POST /internal/v1/infer` for this tenant returned `model_version: "5"` with no `x-model-source: base` header — confirmed the promoted model is now actually used.)

## 8. Model Serving — ONNX Input Signature Mismatch (found during 7.3 verification)

- [x] 8.1 In `inference_service.py:_infer_with_onnx()`, read `session.get_inputs()` and only add `token_type_ids` to the `session.run()` input dict when the session declares that input name — the training worker's ONNX export (`worker.py:342`) only declares `input_ids`/`attention_mask`, so every fine-tuned model previously raised `onnxruntime.InvalidArgument: Invalid input name: token_type_ids` on every inference call, silently falling back to the base model via `infer()`'s outer `except Exception`.
- [x] 8.2 Update the existing `FakeSession` in `tests/test_inference_endpoint.py::TestInferenceCustomLabelList` to implement `get_inputs()` (returning `input_ids`/`attention_mask` only), since the fix makes `_infer_with_onnx()` call it unconditionally.
- [x] 8.3 Add `tests/test_inference_endpoint.py::TestOnnxInputsMatchSessionSignature` with two cases: a 2-input session (asserts `token_type_ids` is NOT sent, matching the current export convention) and a 3-input session (asserts `token_type_ids` IS sent). Logic verified standalone against the real dev DB (same pre-existing port-54320 test-DB gap noted in section 6.5 applies to running these via pytest directly).
- [x] 8.4 Rebuild and restart `model_serving` with the fix; re-run the end-to-end check from 7.3 and confirm `model_version` matches the promoted version with real ONNX-backed predictions.

## 9. Training Service — Widen Warmup Timeout (found after user re-test with v8)

- [x] 9.1 In `training_service/api/v1/models.py:_warmup_model()`, change `httpx.AsyncClient(timeout=30)` to `httpx.AsyncClient(timeout=90)` — a cold model load (S3 download + ONNX session init) can exceed 30s under system load right after a training job finishes, even though model_serving's load continues and succeeds in the background regardless of the client giving up.
- [x] 9.2 Rebuild and restart `training_service` with the fix.
- [x] 9.3 Manually verify: promote a model version and confirm no regression (promote still returns 200, MLflow stage transitions correctly).
- [x] 9.4 Restore tenant `4126ebb0-da07-4d09-bc46-df79c7c6933e`'s model version 8 (MLflow numbering) to Production — it was inadvertently demoted by an agent reproduction step during this investigation that confused local `model_versions.version_number` with MLflow's own version numbering (offset by 2, not the same sequence). Confirmed via direct `/internal/v1/infer` call returning `model_version: "8"`.

## 10. Verification & Evidence

- [ ] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate fix-model-loading-and-label-mapping --type change --strict` and confirm it exits clean before archive. (Passed: "Change 'fix-model-loading-and-label-mapping' is valid".)
