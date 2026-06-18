## Context

The extraction service (`src/extraction_service/`) has a fully implemented Celery worker (`worker.py`) and Celery app (`celery_app.py`) that processes batch extraction tasks from the `extraction` queue. The `POST /api/v1/extract-batch` endpoint dispatches `run_batch_extraction` tasks to this queue via Redis. However, no worker process is deployed to consume that queue — the only `celery_worker` service in `docker-compose.yml` runs the training service's Celery app (`src.training_service.celery_app`), which is a separate Celery instance with a different task registry (`fine_tune_model` only) and listens on the default queue.

The result: batch extraction tasks are sent to Redis but never processed. The extraction run stays in `"queued"` status permanently.

## Goals / Non-Goals

**Goals:**

- Add a Celery worker service to `docker-compose.yml` that runs the extraction service Celery app and consumes the `extraction` queue
- The worker must be able to connect to the same Redis broker, PostgreSQL database (with `search_path`/schema-qualified queries), and optionally the model-serving and document services
- Keep the existing training `celery_worker` unchanged

**Non-Goals:**

- No code changes to `src/extraction_service/worker.py` or `celery_app.py` — they are already correct
- No changes to the batch extraction API endpoint
- No changes to the training worker or its docker-compose service
- No production-grade worker management (Flower, autoscaling, etc.) — this is for dev/CI parity

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-006 | Training Infrastructure — Celery-based async GPU workers with RabbitMQ broker | MVP uses Redis broker (relaxed per SM-05 Decision 4). This change follows the same Redis approach. |
| ADR-003 | Model Serving Topology — Extraction Service routes inference through serving layer | Extraction worker must call model-serving at `{model_serving_url}/internal/v1/infer` (already implemented) |

## Decisions

### Decision 1: Separate worker service (not merging into existing celery_worker)

**Choice:** Add a new `celery_worker_extraction` service to `docker-compose.yml` with its own Celery app.

**Rationale:** The training and extraction Celery apps are separate `Celery()` instances with different task registries. Running both from a single worker would require either (a) sharing a common `celery_app` (refactoring both services), or (b) using `--include` to load extraction tasks into the training app — which fails because `@celery_app.task` decorates on the extraction app instance, not the training app. Two workers is the simplest correct approach.

**Alternatives considered:**
- Single worker with `--include src.extraction_service.worker` — task `run_batch_extraction` would be registered on `extraction_service.celery_app`, not `training_service.celery_app`, causing `KeyError` at runtime when the training-app-based worker tries to dispatch it
- Shared `celery_app` in `src/shared/` — architectural refactor that couples both services to a single Celery app, undermining the microservice pattern

### Decision 2: Reuse training_service Dockerfile (not a lighter image)

**Choice:** Use the same `src/training_service/Dockerfile` for the extraction worker.

**Rationale:** The training service Dockerfile installs all project dependencies (celery, sqlalchemy, requests, transformers, torch, etc.) in a single layer. The extraction worker only needs sqlalchemy and requests, but creating a separate Dockerfile with only those deps adds build complexity for marginal image size savings in dev. A lighter image can be created post-MVP if CI build times become a concern.

**Alternatives considered:**
- New `src/extraction_service/Dockerfile` with minimal deps — cleaner separation but more Dockerfiles to maintain; extraction service API already runs without Docker (uvicorn), the worker is the only process that needs containerization

### Decision 3: Use `--pool=solo` for Windows compatibility

**Choice:** Use `--pool=solo` in the worker command.

**Rationale:** The `prefork` pool (Celery default) uses `os.fork()` which is not available on Windows. The existing training worker does not set `--pool` because it runs inside a Linux Docker container. However, when running the worker directly on Windows for development (outside Docker), `--pool=solo` is required. Setting it in docker-compose ensures the command works identically inside and outside containers.

## Risks / Trade-offs

- [Worker crashes during batch processing without retries] → The task has `max_retries=0`. A crash mid-batch leaves the extraction run in "running" state with partial results. Mitigation: add retry logic or a reconciliation cron job in a future change.
- [Two workers compete for Redis broker connections] → Negligible for dev. In production, connection pooling can be tuned.
- [Dockerfile includes heavy ML deps (torch, transformers) unused by extraction worker] → ~2GB extra in the image. Acceptable for dev. A leaner Dockerfile can be created post-MVP.

## Migration Plan

1. Add `celery_worker_extraction` service to `docker-compose.yml` — mirror the existing `celery_worker` but with:
   - `command: celery -A src.extraction_service.celery_app worker -Q extraction --pool=solo --loglevel=info`
   - No `NER_TRAINING_DEVICE`, `NER_MINIO_ENDPOINT`, or `NER_MLFLOW_TRACKING_URI` env vars (unnecessary for extraction)
2. Verify: run `docker-compose up -d celery_worker_extraction` and confirm the worker connects to Redis and logs `ready`.
3. Verify: hit `POST /api/v1/extract-batch?documentIds=...` and confirm the worker picks up the task and processes documents.

Rollback: Remove or comment out the `celery_worker_extraction` service from docker-compose.yml.

## Open Questions

- None — the design is straightforward. The only open question (Dockerfile reuse vs. new lighter Dockerfile) is answered in Decision 2.
