## Context

The NER platform has six FastAPI services (`gateway`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`) plus two Celery workers. The existing `docker-compose.yml` containerises only `training_service` and its Celery workers, along with infrastructure dependencies (PostgreSQL, Redis, MinIO, MLflow). The remaining five services must be launched manually with individual `uvicorn` commands, and Celery workers reference those services via `host.docker.internal` URLs that only work on Docker Desktop (macOS/Windows) and break on Linux.

All Python dependencies live in a single `pyproject.toml` at the project root; the repo is a monorepo. The existing `src/training_service/Dockerfile` manually pip-installs a subset of packages instead of using `pyproject.toml`, making it drift-prone.

## Goals / Non-Goals

**Goals:**
- `docker compose up` starts every backend service (all six FastAPI apps + both Celery workers) with no manual steps.
- Replace `host.docker.internal` URL references with stable Docker service-name URLs.
- Consolidate dependency installation into a single root `Dockerfile` that reads from `pyproject.toml`.
- Preserve all existing port mappings: gateway `8000`, document_service `8001`, extraction_service `8002`, training_service `8003`, model_serving `8004`, annotation_service `8005` (all internally on `8000`).

**Non-Goals:**
- Production Kubernetes deployment; this targets local development only.
- Hot-reload / volume-mounted code in all services (kept only for Celery workers as today).
- Separate slim images per service (acceptable future optimization, not needed now).
- GPU support; CPU-only training as currently configured.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-003-model-serving-topology | Shared Model Serving Layer with per-tenant routing | `model_serving` must be reachable by `extraction_service` via a stable URL; docker service name satisfies this. |
| ADR-006-training-infrastructure | Celery-based async GPU workers | `celery_worker` and `celery_worker_extraction` must continue to run as separate Docker Compose services. |

## Decisions

### Decision 1: Single shared root Dockerfile for all services

**Choice:** Add a single `Dockerfile` at the project root that installs all dependencies via `pip install .` (using pyproject.toml's PEP 517 interface) plus torch separately, then copies the `src/` directory. Each compose service overrides `CMD` to boot its specific `uvicorn` entry point. Retire the drift-prone manual pip list in `src/training_service/Dockerfile`.

**Rationale:** The project is a monorepo with one `pyproject.toml`. A single build context keeps the dependency list authoritative in one place. For local development, a large image is acceptable; the build is cached after the first run.

**Alternatives considered:**
- *Per-service Dockerfiles with only required deps* — reduces image size and cold-start time in production, but adds six files to maintain and requires splitting pyproject.toml or building a custom installer. Out of scope for local dev.
- *Keep the existing training_service Dockerfile and add five more copies* — duplicates the manual pip list across six files, amplifying the existing drift problem.

### Decision 2: Internal port 8000 for every service; distinct host ports

**Choice:** Every service container listens on port `8000` internally (standard uvicorn default). Docker Compose maps each to a unique host port: `8000`, `8001`, `8002`, `8003`, `8004`, `8005` for gateway through annotation_service respectively. Inter-service communication uses service names and internal port `8000` (e.g., `http://model_serving:8000`).

**Rationale:** Uniform internal port simplifies the Dockerfile (one `EXPOSE 8000`) and is consistent with how `training_service` already works. Distinct host ports allow all services to be reached from the developer's machine simultaneously.

**Alternatives considered:**
- *Match host port to internal port (each service uses a unique port internally)* — requires per-service port config in shared config and more moving parts; no benefit for local dev.

### Decision 3: Update inter-service env vars to Docker service names

**Choice:** In `docker-compose.yml`, set `NER_DOCUMENT_SERVICE_URL=http://document_service:8000` and `NER_MODEL_SERVING_URL=http://model_serving:8000` for `celery_worker_extraction` and any service that calls them. Remove `extra_hosts: host.docker.internal` from `celery_worker_extraction`.

**Rationale:** Service-name resolution is Docker's built-in DNS on any platform. `host.docker.internal` only works reliably on Docker Desktop (macOS/Windows) and is unavailable on Linux without extra configuration.

**Alternatives considered:**
- *Keep host.docker.internal and add Linux workaround* — fragile, platform-specific.

## Risks / Trade-offs

- [Large image size due to torch/transformers in all services] → Acceptable for local dev; if image size becomes a problem, service groups can be split in a follow-up change.
- [First `docker compose build` is slow due to torch download] → Mitigated by Docker layer caching; subsequent builds reuse the installed-deps layer.
- [Alembic migrations not run automatically on startup] → Developers must still run `alembic upgrade head` manually or via a one-off compose run command; an `init-db` compose service can be added later.

## Migration Plan

1. Add root `Dockerfile` with full dep installation.
2. Update `docker-compose.yml`: add 5 new service entries, update Celery worker env vars, remove `host.docker.internal` references.
3. Retire `src/training_service/Dockerfile` — point the `training_service` compose entry at the root `Dockerfile`.
4. Developers run `docker compose build` once, then `docker compose up` to validate all services start and health-check endpoints respond.
5. Rollback: revert `docker-compose.yml` and restore `src/training_service/Dockerfile`; the old manual launch process still works.

## Open Questions

- Should `annotation_service` connect to the same PostgreSQL database as the other services, or does it need a separate schema? 
Answer: same DB, same schema.
- Should Alembic migrations run automatically as a `depends_on` init container in docker-compose? (Out of scope for this change, but worth a follow-up.)
