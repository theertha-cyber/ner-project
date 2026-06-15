## Why

The platform currently plans a fully custom experiment tracking and model registry — hand-rolled metrics persistence in the training worker, a custom Model Registry service for version management, no experiment comparison capability, and no standardized model packaging. MLflow is the de-facto standard in the ML ecosystem; adopting it eliminates re-inventing the wheel, provides a rich run comparison UI out of the box, standardizes model packaging format, and simplifies future integration with the broader ML toolchain (e.g., hyperparameter tuning, model serving).

## What Changes

- **Training Worker**: Add MLflow Tracking integration — log hyperparameters, per-epoch metrics, and model artifacts to the MLflow server during fine-tuning. The existing DB persistence becomes secondary; MLflow becomes the primary metrics store.
- **Model Registry Service**: Replace the planned custom DB-backed model versioning with the MLflow Model Registry. The custom FastAPI endpoints become a thin proxy over the MLflow Registry API. Internal version states (completed/promoted/archived) map to MLflow stages (None/Staging/Production/Archived).
- **New MLflow Infrastructure**: Deploy an MLflow Tracking Server with PostgreSQL backend store and S3 artifact store. Add to `docker-compose.yml` for local dev. Add to K8s manifests for production.
- **Tenant Isolation Model**: Use MLflow naming conventions (`experiment: tenant_{tid}`, `registered_model: tenant_{tid}_ner_model`) instead of separate MLflow instances per tenant. Tenant-scoped access enforced at the proxy layer.
- **BREAKING**: The `model-registry` spec's current approach (fully custom DB tables for version lifecycle) is replaced. The `model_versions` DB table may be deprecated in favour of MLflow's registered model schema.

## Capabilities

### New Capabilities

- `mlflow-infrastructure`: MLflow Tracking Server deployment, backend store configuration (PostgreSQL + S3), Docker Compose and K8s manifests, tenant isolation naming convention, service health checks.

### Modified Capabilities

- `training-worker`: Add MLflow experiment tracking (autolog or manual `log_params`/`log_metrics`/`log_model`). Log dataset version, base model hash, per-epoch metrics. Store `mlflow_run_id` in the training job record.
- `model-registry`: Transition from custom DB-backed model version CRUD to MLflow Registry API. Keep the same external API contracts (`GET/POST /models`, `/promote`, `/demote`, `/active`) but implement them as a thin proxy over MLflow's registered model and stage APIs. Map custom statuses to MLflow stages.

## Impact

| Area | Impact |
|---|---|
| `training-worker/spec.md` | Add MLflow Tracking; metrics still written to DB but MLflow becomes primary |
| `model-registry/spec.md` | **BREAKING** — replace internal implementation, keep external API surface |
| `pyproject.toml` | Add `mlflow` dependency (with `[extras]` for tracking server) |
| `docker-compose.yml` | Add MLflow Tracking Server service |
| K8s manifests | Add MLflow server Deployment + Service + PVC |
| Model Serving Layer | No change — still loads from artifact URIs (now managed by MLflow) |
| Training Jobs API | Add `mlflow_run_id` and `mlflow_run_url` to job responses |
| Docs | New ADR capturing MLflow tenant isolation approach |

## Open Questions

- Should the custom `model_versions` DB table be fully removed or kept as a read-through cache for the MLflow Registry?
- MLflow autolog vs manual logging for the HuggingFace Trainer — autolog is simpler but gives less control over logged metrics.
- Should the MLflow Tracking Server be exposed externally (with auth) or kept as an internal-only service?
- For the MVP, is a separate MLflow deployment worth the operational cost vs using the fully custom approach and deferring MLflow?
