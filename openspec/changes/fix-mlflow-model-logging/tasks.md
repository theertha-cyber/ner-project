## 1. Dependencies & Configuration

- [x] 1.1 Pin MLflow in `pyproject.toml` to `>=2.20.0,<3.0.0` to match the v2.20.0 MLflow server
- [x] 1.2 ~~Add `optimum>=2.0.0` to `pyproject.toml` dependencies for ONNX export~~ — added then reverted 2026-07-08: no `optimum`/`optimum-onnx` release supports `transformers>=5.11.0` (this project's pin), so `poetry lock` failed. See design.md Decision 2 and Open Question 1. ONNX export uses `torch.onnx.export()` directly instead; `optimum` is not a dependency.
- [x] 1.3 Rebuild the Docker image and verify `pip list` shows mlflow 2.x installed (manual ops task) — verified 2026-07-08: `docker compose exec celery_worker pip show onnxruntime mlflow` confirms onnxruntime 1.27.0, mlflow 2.22.5. Previously checked off without a rebuild; the stale image caused a `ModuleNotFoundError: No module named 'optimum'` failure in production during a real training run before this was corrected — then a second real run surfaced the transformers-version conflict above (`ModuleNotFoundError: No module named 'optimum.onnxruntime'`), which led to dropping `optimum` entirely.

## 2. Retry Guard (Job Status Pre-Check)

- [x] 2.1 Add a DB status check at the top of `fine_tune_model` in `src/training_service/worker.py` — query `training_jobs.status` and return early if status is `completed`, `failed`, or `cancelled`
- [x] 2.2 Add unit test: invoke `fine_tune_model` with a job whose DB status is `completed` — verify it logs a warning and returns without training
- [x] 2.3 Add unit test: invoke `fine_tune_model` with a job whose DB status is `failed` — verify it logs a warning and returns without training
- [x] 2.4 Add unit test: invoke `fine_tune_model` with a job whose DB status is `approved` — verify it proceeds to training

## 3. ONNX Conversion

- [x] 3.1 Add ONNX export step in `worker.py` after `trainer.save_model()` and before `_save_artifacts()` — revised 2026-07-08: use `torch.onnx.export()` directly (not `optimum.onnx.export_onnx()` — see design.md Decision 2) with the BERT tokenizer config and dynamic axes for variable-length input
- [x] 3.2 Export the ONNX model to the same temp directory (`model_dir`) as the PyTorch files so `_save_artifacts()` picks it up automatically
- [x] 3.3 Add unit test: given a small trained BERT model, verify `torch.onnx.export()` produces a `model.onnx` file with the correct input/output shapes
- [x] 3.4 Add integration test: train a tiny model, export to ONNX, load it with `onnxruntime.InferenceSession`, and verify inference produces valid predictions

## 4. MLflow Model Logging Fix

- [x] 4.1 Verify that `mlflow.transformers.log_model()` succeeds with the pinned mlflow 2.x client against the v2.20 server (the 404 should no longer occur)
- [x] 4.2 Add integration test: create an MLflow run, train a small model, call `mlflow.transformers.log_model()` with `registered_model_name`, and confirm the model appears in MLflow Model Registry
- [x] 4.3 Add `pip_requirements=["torch"]` to `mlflow.transformers.log_model()` to prevent auto-inference of tensorflow dependency — MLflow's `get_default_pip_requirements()` adds both torch and tensorflow when it cannot determine the execution engine, then fails with `ModuleNotFoundError: No module named 'tensorflow'`
- [x] 4.4 Add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, and `MLFLOW_S3_ENDPOINT_URL` to the celery_worker service environment in docker-compose.yml — MLflow's S3 artifact repo needs these to upload model artifacts to MinIO
- [x] 4.5 Create and run alembic migration 018 to add `version_number`, `artifact_path`, and `mlflow_run_id` columns to existing tenant `model_versions` tables — migration 002 created them as `version`/`artifact_uri` but migration 005/006 only updated `tenant_template`, not existing tenants

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (requires DB + services infrastructure)
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log (incomplete, needs human reviewer)
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 5.6 Run `openspec validate fix-mlflow-model-logging --type change --strict` and confirm it exits clean before archive
