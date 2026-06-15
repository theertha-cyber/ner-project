## 1. Setup & Dependencies

- [x] 1.1 Add `mlflow[postgresql,s3]` to `pyproject.toml` dependencies
- [x] 1.2 Add `MLFLOW_TRACKING_URI` to `.env.example` and document in PROJECT.md
- [x] 1.3 Add MLflow Tracking Server service to `docker-compose.yml` with PostgreSQL backend and MinIO artifact store configuration
- [x] 1.4 Verify MLflow creates its PostgreSQL tables on startup (no Alembic migration needed — MLflow manages its own schema)
- [x] 1.5 Add MLflow S3/MinIO artifact store bucket configuration to Docker Compose env vars

## 2. MLflow Infrastructure — Training Worker Integration

- [x] 2.1 Initialize MLflow run at start of `fine_tune_model` Celery task with experiment `tenant_{tid}`
- [x] 2.2 Log training hyperparameters (`learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`) via `mlflow.log_params()`
- [x] 2.3 Log training tags: `base_model`, `tenant_id`, `training_job_id`, `num_labels`
- [x] 2.4 Log per-epoch metrics via `MLflowCallback` + final metrics including per-entity-type scores
- [x] 2.5 Set MLflow run status to `FAILED` with `error_message` tag on training failure
- [x] 2.6 Log trained model artifacts via `mlflow.transformers.log_model()` with registered model name `tenant_{tid}_ner_model`
- [x] 2.7 Persist `mlflow_run_id` and `mlflow_run_url` to the `training_jobs` DB record after successful training
- [x] 2.8 Verify existing DB metrics persistence is preserved (dual-write, not replaced) — code review step

## 3. Model Registry — MLflow Proxy Implementation

- [x] 3.1 Implement MLflow client initialization in `mlflow_registry.py` using `settings.mlflow_tracking_uri`
- [x] 3.2 Implement status-to-stage mapping: `completed` → `Staging`, `promoted` → `Production`, `archived` → `Archived`
- [x] 3.3 Implement `GET /api/v1/models` via `mlflow_registry.list_model_versions()` with DB cache fallback and `X-Info` warning header
- [x] 3.4 Implement `POST /api/v1/models/{version_id}/promote` via `mlflow_registry.promote_model_version()` — transitions MLflow version to Production, archives previous
- [x] 3.5 Implement `POST /api/v1/models/{version_id}/demote` via `mlflow_registry.demote_model_version()` — transitions Production→Staging
- [x] 3.6 Implement `GET /api/v1/models/active` via `mlflow_registry.get_active_model()` with DB cache fallback and warning header
- [x] 3.7 Tenant-scoped filtering via `_registered_model_name(tenant_id)` = `tenant_{tid}_ner_model`
- [x] 3.8 Local DB cache via `_cache_model_version()` / `_read_cache_model_versions()` with `ON CONFLICT` upsert

## 4. MLflow Infrastructure — Deployment

- [x] 4.1 MLflow Tracking Server provides native `/health` endpoint — no wrapper needed
- [x] 4.2 Create K8s Deployment manifest at `deploy/k8s/mlflow/deployment.yaml` with PostgreSQL and S3 env vars
- [x] 4.3 Create K8s Service manifest at `deploy/k8s/mlflow/service.yaml` exposing port 5000 as ClusterIP
- [x] 4.4 Liveness probe (path: `/health`, initialDelay: 30s) and readiness probe (path: `/health`, initialDelay: 15s) configured
- [x] 4.5 Deployment documentation updated in PROJECT.md § Tech Stack and docker-compose.yml

## 5. Testing

- [x] 5.1 Unit test: Naming conventions (`_registered_model_name`, `_experiment_name`) in `tests/test_mlflow_registry.py`
- [x] 5.2 Unit test: Status-to-stage mapping roundtrip (`STATUS_TO_STAGE` ↔ `STAGE_TO_STATUS`) in `tests/test_mlflow_registry.py`
- [x] 5.3 Unit test: Promote returns None when no registered model exists (mocked) in `tests/test_mlflow_registry.py`
- [x] 5.4 Unit test: Demote returns None when no registered model exists (mocked) in `tests/test_mlflow_registry.py`
- [x] 5.5 Unit test: Cache fallback when MLflow raises exception (mocked) — list and active endpoints
- [x] 5.6 Unit test: Tenant-scoped filtering enforced by `_registered_model_name(tenant_id)` — naming convention covers isolation
- [x] 5.7 Integration test: Training Worker — MLflow run created with correct params, tags, and metrics (MLflow server running @ localhost:5000) — `test_mlflow_integration_live.py::test_create_run_with_params_tags` PASSED
- [x] 5.8 Integration test: Training Worker — model logged to registered model `tenant_{tid}_ner_model` (MLflow server running) — `test_register_and_list_model` PASSED
- [x] 5.9 Integration test: Training Worker — failure sets MLflow run status to FAILED (MLflow server running) — `test_run_failure_status` PASSED
- [x] 5.10 Integration test: Full pipeline — training job → MLflow run → promote → resolve active model (MLflow server + DB) — `test_promote_and_get_active`, `test_promote_archives_previous`, `test_demote_active` all PASSED

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests — 29 tests pass (mlflow_registry: 10, model_registry: 10, training_worker: 7, env_config: 2)
- [x] 6.2 Collect functional evidence — 9 entries in Evidence Log § 5 (unit tests, integration tests, code review, config review, MLflow server check)
- [x] 6.3 Confirm all Hallucination Risk mitigation steps — all 6 risks verified with mitigation evidence
- [x] 6.4 Confirm all ADR compliance steps — ADR-001/002/003/006 confirmed in verification.md § 3
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 6.6 Run `openspec validate mlflow-integration --type change --strict` — exits clean ✓
