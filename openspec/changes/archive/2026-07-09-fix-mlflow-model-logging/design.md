## Context

The training pipeline (`fine_tune_model` Celery task) completes fine-tuning successfully but fails during model registration. Three interconnected issues make the pipeline non-functional:

1. **MLflow version mismatch**: Server runs 2.20.0 (`ghcr.io/mlflow/mlflow:v2.20.0`), but the Python client installed from `pyproject.toml` is `>=3.0.0,<4.0.0`. MLflow 3.x calls the `/api/2.0/mlflow/logged-models` endpoint which doesn't exist on the 2.20 server → 404 → `mlflow.transformers.log_model()` fails.

2. **Missing ONNX conversion**: The worker saves PyTorch `.safetensors`/`.bin` to MinIO, but the model-serving layer loads ONNX `.onnx` files. Even if MLflow logging worked, the fine-tuned model would never be loadable by the inference service — it would silently fall back to `dslim/bert-base-NER`.

3. **Unbounded retry loop on failure**: `task_acks_late=True` combined with a worker crash (SIGKILL from OOM) causes the unacknowledged message to be redelivered. Each retry trains 20 epochs (96 minutes) before hitting the same 404 or OOM.

## Goals / Non-Goals

**Goals:**
- Make `mlflow.transformers.log_model()` succeed so models are registered in MLflow
- Produce ONNX model artifacts in blob storage that the model-serving layer can load
- Prevent the unbounded retry/OOM death spiral
- Keep the existing training pipeline architecture (Celery + HuggingFace Trainer + MLflow)

**Non-Goals:**
- Not upgrading to MLflow server 3.x — the existing 2.20 server works for tracking; only the model registration endpoint differs. Align the client to the server.
- Not changing the model-serving layer's ONNX expectation — it's already correct, the worker was missing the conversion step.
- Not addressing general data imbalance or model quality issues — those are separate improvements.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-002 | Single curated base model (`dslim/bert-base-NER`), no BYOM | Worker must continue using this base model |
| ADR-003 | Per-tenant model serving with shared pool, version pinning | ONNX model artifacts must integrate with existing serving topology |
| ADR-006 | Celery-based async GPU workers with Redis broker | Retry guard must work within Celery's acks_late model |
| ADR-008 | Base model (v0) is the default when no tenant model is promoted | ONNX conversion and model registration must not break the v0 fallback |

## Decisions

### Decision 1: Pin MLflow client to 2.x instead of upgrading server

**Choice:** Change `pyproject.toml` to `mlflow>=2.20.0,<3.0.0` and keep the MLflow server at v2.20.0.

**Rationale:**
- The 2.20 server is running stably for experiment tracking (runs, params, metrics, tags all work)
- Only `mlflow.transformers.log_model()` with `registered_model_name` is broken, because 3.x client calls the new `logged-models` endpoint
- In MLflow 2.20, model registration goes through `create_registered_model` + `create_model_version` — the same endpoint that the `mlflow_registry.py` module already uses successfully for promote/demote
- Upgrading the server to 3.x would require finding/testing a compatible Docker image, verifying no server-side command changes, and risks breaking the tracking functionality that already works
- Pinning the client is a one-line `pyproject.toml` change — lower risk, immediate payoff

**Alternatives considered:**
- Upgrade server to 3.x — more future-proof, but higher risk. No official 3.x Docker image tag was found on ghcr.io; would need to build custom or verify compatibility of the v2.20 image with a newer pip-installed server.
- Remove `registered_model_name` from `mlflow.transformers.log_model()` and register separately — doesn't fix the underlying version mismatch; the model still can't log.
- Use MLflow's `MlflowClient.create_registered_model()` + `create_model_version()` directly instead of `mlflow.transformers.log_model()` — alternative approach that works with both 2.x and 3.x, but bypasses the transformers flavor's built-in model packaging.

### Decision 2: Use `torch.onnx.export()` directly for ONNX conversion

**Choice (revised 2026-07-08):** Call `torch.onnx.export()` directly on the trained model after `trainer.save_model()`, with explicit `input_names`, `output_names=["logits"]`, and `dynamic_axes` for the batch/sequence dimensions. Write the output to `model_dir/model.onnx`.

**Originally chosen:** Add `optimum>=2.0.0` and use its ONNX export path (`optimum.onnxruntime.ORTModelForTokenClassification(..., export=True)`). **Reverted** — every published `optimum` release (1.x, which bundles `optimum.onnxruntime` directly, and 2.x, which requires the separate `optimum-onnx` package) caps `transformers` support at `<4.58.0`. This project pins `transformers>=5.11.0,<6.0.0` project-wide — that pin predates this change and the whole training pipeline (`AutoModelForTokenClassification`, `Trainer`, etc.) depends on it, so downgrading it to satisfy `optimum` was rejected as too broad a blast radius for one export step. `poetry lock` confirmed the dependency conflict is unresolvable as specified (see Open Question 1, which flagged this exact risk before implementation and wasn't checked before `optimum` was added).

**Rationale:**
- No version ceiling conflict — `torch.onnx.export()` has no dependency on `optimum`/`optimum-onnx`, so it's compatible with `transformers>=5.11.0`
- Model-serving (`src/model_serving/services/inference_service.py`) is already export-method-agnostic: it globs for any `*.onnx` file and calls `session.run(None, inputs)` with `input_ids`/`attention_mask`/optional `token_type_ids` — it doesn't depend on optimum-specific packaging, so no serving-side changes were needed
- `onnxruntime` is already a dependency, so the serving side is ready

**Alternatives considered:**
- `optimum` (originally chosen) — rejected due to the transformers version conflict above
- `transformers.onnx` (deprecated) — still works but deprecated; not worth adopting for a one-off export call when `torch.onnx.export()` is the underlying mechanism anyway

### Decision 3: Simple database pre-check as retry guard

**Choice:** At the start of `fine_tune_model`, query the `training_jobs` table. If the job's status is `completed`, `failed`, or `cancelled`, log a warning and return early (no-op) instead of re-executing.

**Rationale:**
- Dead-simple implementation — one DB query before any expensive operations
- Prevents the 96-minute waste cycle: if a previous run failed but the task is re-delivered, it sees `failed` status and exits immediately
- Doesn't require Celery config changes or external state machines
- Complements the existing `max_retries=0` — covers the case where the worker crashes before it can ack

**Alternatives considered:**
- Celery's `acks_late=False` — would ack before execution, but loses task guarantee on crash
- Redis-based idempotency lock — more robust against race conditions, but adds infrastructure coupling
- Custom Celery rejection with requeue prevention — complex, fragile across Celery versions

## Risks / Trade-offs

- **[DB pre-check races with concurrent celery workers]** → Currently `--concurrency=1` and training time >> DB query time, so a race between two workers processing the same job is practically impossible. If concurrency is increased later, add a Redis lock.
- **[ONNX export adds ~10s to training pipeline]** → Irrelevant compared to the 96-minute training time.
- **[2.x client won't have 3.x features]** → Acceptable: the 3.x features relevant to this project (transformers flavor improvements) are not critical, and the API we use works in 2.x.
- **[`mlflow_registry.py` uses `MlflowClient` which is 2.x/3.x compatible]** → Verified: the existing registry code works with 2.20 server because it uses the stable `create_registered_model` / `create_model_version` / `transition_model_version_stage` APIs.

## Migration Plan

1. Pin `mlflow` to `>=2.20.0,<3.0.0` in `pyproject.toml`
2. Rebuild the Docker image so the celery worker container has MLflow 2.x
3. ~~Add `optimum` to `pyproject.toml` dependencies~~ — reverted; no `optimum` dependency needed
4. Add ONNX export step in `worker.py` after `trainer.save_model()`, before artifact upload, via `torch.onnx.export()`
5. Add DB pre-check at the top of `fine_tune_model`
6. Update tests to verify ONNX file exists in artifacts and MLflow registration succeeds
7. `docker compose up --build celery_worker` to deploy

**Rollback:** Revert `pyproject.toml` dependency changes and worker code. The 2.20 server is unchanged, so rollback is a container rebuild.

## Open Questions

1. ~~**optimum version**: Pin to a specific range (e.g., `>=2.0.0,<3.0.0`)? Check compatibility with transformers 5.x.~~ — Resolved 2026-07-08: no version of `optimum`/`optimum-onnx` supports `transformers>=5.11.0`. Switched to `torch.onnx.export()` directly, which has no such constraint. This was flagged as an open question before `optimum` was added but wasn't checked; caused a production failure (`ModuleNotFoundError: No module named 'optimum.onnxruntime'`) before being caught.
2. **ONNX export with dynamic axes**: Resolved — `dynamic_axes={"input_ids": {0: "batch", 1: "sequence"}, "attention_mask": {...}, "logits": {...}}` configured directly in the `torch.onnx.export()` call in `worker.py`.
3. **File naming convention**: Resolved — export writes directly to `model_dir/model.onnx`, matching what the model-serving code's `*.onnx` glob expects.
4. **Does the colab-training-integration change also need ONNX?** The colab path returns artifacts to the same MinIO paths. If it saves PyTorch format, it has the same gap.
5. **ADR status**: All ADRs are "Proposed" — should this change's decisions be captured as a new ADR or can they stay in design.md?
