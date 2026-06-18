## Why

Each of the six FastAPI backend services (`gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`) must be started manually with separate `uvicorn` commands, making local development painful and error-prone. Containerizing every service under a single `docker compose up` command eliminates the per-service startup burden and ensures all inter-service URLs resolve consistently.

## What Changes

- Add a shared root `Dockerfile` that installs all Python dependencies from `pyproject.toml` and can boot any service via an overridden `CMD`.
- Add Docker Compose service entries for the five services currently missing: `gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`.
- Update `celery_worker_extraction` to use Docker-internal service names (replacing `host.docker.internal` URLs).
- Update inter-service environment variables across all compose services to reference container service names instead of `localhost`.
- Remove the need to run `uvicorn` manually for any backend service.

## Capabilities

### New Capabilities

- `local-dev-stack`: A single `docker compose up` command starts the entire backend stack — all six FastAPI services, two Celery workers, PostgreSQL, Redis, MinIO, and MLflow — with correct inter-service networking.

### Modified Capabilities

- `env-config`: Inter-service URL env vars (`NER_DOCUMENT_SERVICE_URL`, `NER_MODEL_SERVING_URL`) change from `localhost` to Docker service names when running in-container.

## Impact

- **New files**: `Dockerfile` at project root (shared across all services).
- **Modified files**: `docker-compose.yml` — adds 5 new service blocks and updates env var URLs in existing Celery worker services.
- **No API changes**: All service behaviour is unchanged; only the launch mechanism changes.
- **Port mapping** (host → container): gateway `8000`, document_service `8001`, extraction_service `8002`, training_service `8003`, model_serving `8004`, annotation_service `8005`.

## Open Questions

- Should the root `Dockerfile` install the full dependency set (including `torch`, `transformers`, `mlflow`) for all services, or should lightweight services (gateway, document_service, annotation_service) get a slimmer image? 
Answer: Full deps 
- The `annotation_service` does not appear in `docker-compose.yml` yet — confirm it should be added on the same database/redis stack.
Answer: add annotation_service on the same db.
