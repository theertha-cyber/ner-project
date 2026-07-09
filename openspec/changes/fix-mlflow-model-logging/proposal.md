## Why

The training pipeline completes 20 epochs but fails at the final step when `mlflow.transformers.log_model()` tries to register the model. The MLflow server (v2.20) doesn't support the `/api/2.0/mlflow/logged-models` endpoint called by the MLflow client (3.x). After failure, the unacknowledged Celery task is redelivered, causing a second model load that triggers OOM (SIGKILL). Three interconnected bugs make the training pipeline non-functional end-to-end.

## What Changes

- **Fix MLflow server/client version mismatch**: Align the MLflow Docker image version with the Python client version so `mlflow.transformers.log_model()` succeeds.
- **Add ONNX conversion step in training worker**: The worker currently saves PyTorch format to MinIO, but model serving loads ONNX. Add a conversion step so fine-tuned models are actually usable at inference time.
- **Add retry guard against OOM death spiral**: The task has `task_acks_late=True` and `max_retries=0`, but worker SIGKILL causes infinite redelivery. Add a circuit breaker or poison-message detection so a failing job doesn't consume infinite GPU cycles.
- **Update verification.md with failure-path tests**: Cover the 404 scenario, ONNX conversion validation, and retry-guard behavior.

## Capabilities

### New Capabilities

- `onnx-conversion`: Convert trained PyTorch models to ONNX format after training completes, so model serving can load them.
- `training-retry-guard`: Detect and abort retries of jobs that have previously failed, preventing the OOM death spiral.

### Modified Capabilities

- `training-worker`: Update the `mlflow.transformers.log_model()` call and post-training artifact pipeline to include ONNX conversion.
- `mlflow-infrastructure`: Update the MLflow server Docker image version to match the client version constraint.
- `mlflow-verification-tests`: Add test scenarios for version alignment and ONNX artifact completeness.

## Impact

| Area | Impact |
|------|--------|
| `deploy/k8s/mlflow/Dockerfile` | Bump `ghcr.io/mlflow/mlflow` tag from v2.20.0 to match client version |
| `src/training_service/worker.py` | Add ONNX export step after training; add pre-execution failure check |
| `pyproject.toml` | Pin MLflow to a specific 3.x version instead of range (optional, for reproducibility) |
| `docker-compose.yml` | Possibly update MLflow service command if breaking changes between 2.x and 3.x |
| Celery worker | No new dependencies needed (ONNX export uses `transformers.onnx` or `optimum`) |

## Open Questions

1. **Which MLflow 3.x version?** `>=3.0.0,<4.0.0` currently — should we pin to a specific tested version (e.g., `3.2.0`)?
2. **ONNX export library**: `optimum-cli export onnx` or manual `torch.onnx.export()`? The model-serving spec expects ONNX, but there's no existing conversion infrastructure.
3. **Retry guard mechanism**: Detect by checking if `training_jobs` record already has `status=failed` before executing, or use Celery's `max_retries` + custom exception handling?
4. **Does the `colab-training-integration` change also need the ONNX step?** The colab path returns artifacts to the same MinIO paths, so it would inherit the fix.
