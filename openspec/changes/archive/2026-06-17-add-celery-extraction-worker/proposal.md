## Why

The extraction service's batch extraction endpoint (`POST /api/v1/extract-batch`) dispatches `run_batch_extraction` tasks to a dedicated `extraction` Celery queue, but no Celery worker is configured to consume that queue. Tasks sit in Redis indefinitely — batch extraction is effectively broken in any environment using docker-compose (development, CI). The training Celery worker (`celery -A src.training_service.celery_app`) is a separate Celery app with a different task registry and listens only on the default queue, so it cannot process extraction tasks.

## What Changes

- Add a new `celery_worker_extraction` service to `docker-compose.yml` that runs the extraction service's Celery app and listens on the `extraction` queue
- No code changes to the extraction service's worker or celery_app — the task implementation already exists and is correct
- No changes to the existing training `celery_worker` service

## Capabilities

### New Capabilities

- `extraction-worker-deployment`: Celery worker process for the extraction service's `extraction` queue, configured in docker-compose.yml

### Modified Capabilities

- *(none — this is purely a deployment configuration change, no spec-level requirement changes)*

## Impact

- **docker-compose.yml**: New `celery_worker_extraction` service with `command: celery -A src.extraction_service.celery_app worker -Q extraction --pool=solo --loglevel=info`
- **Existing services unaffected**: training `celery_worker`, `training_service`, `extraction_service`, `model_serving` — none need changes
- **Dependencies**: Reuses the same Redis broker as the training worker; needs `NER_DATABASE_URL_SYNC` for direct DB access (the extraction worker uses synchronous SQLAlchemy queries)

## Open Questions

- Should `--pool=solo` or `--pool=threads` be used? (`--pool=solo` is simplest for dev; `--pool=threads` if concurrent document processing is needed)
- Should the extraction worker use the same `Dockerfile` (training_service/Dockerfile) or a lighter one without ML dependencies? (The extraction worker only needs sqlalchemy, requests, celery — not torch/transformers)
