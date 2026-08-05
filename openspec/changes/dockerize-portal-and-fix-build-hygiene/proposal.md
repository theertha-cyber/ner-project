## Why

Docker setup has drifted from the `local-dev-stack` spec and has real gaps: portal (frontend) has no Dockerfile and isn't in `docker-compose.yml`, so `docker compose up` cannot run the full stack. Gateway hardcodes `host.docker.internal` for `NER_CHAT_API_URL`, violating the existing "Docker DNS, no host.docker.internal" requirement and breaking on non-Docker-Desktop hosts. No `.dockerignore` exists anywhere, so build context ships `.git`, `.env`, `node_modules`, `venv`, `__pycache__`, and large data files into every image build. A stale, diverging `src/training_service/Dockerfile` still exists despite the spec already saying no service should reference it. Two dead `requirements.txt` files sit unused next to the poetry-based root `Dockerfile`, confusing future contributors.

## What Changes

- Add multi-stage `src/portal/Dockerfile` (deps → build → minimal Node runtime) using the existing `output: "standalone"` Next.js build.
- Add `portal` service to `docker-compose.yml`.
- Fix `gateway`'s `NER_CHAT_API_URL` to use Docker service DNS (`http://chat_api:8000`) instead of `host.docker.internal`, and add `chat_api` to gateway's `depends_on`.
- Add root-level `.dockerignore` covering `.git`, `.env*`, `node_modules`, `**/__pycache__`, `.pytest_cache`, `*.jsonl`, `*.pptx`, and other non-build files.
- Add `src/portal/.dockerignore` for the frontend build context (`node_modules`, `.next`, etc.).
- Delete stale `src/training_service/Dockerfile` (unused, diverges from `poetry.lock`, missing alembic — root `Dockerfile` is already the one compose builds from).
- Delete dead `src/gateway/requirements.txt` and `src/document_service/requirements.txt` (nothing builds from them; root `Dockerfile` uses Poetry).
- Convert root `Dockerfile` to multi-stage (builder stage with Poetry/build tooling, slim final runtime stage) to reduce image size.
- Document that `celery_worker` and `celery_worker_extraction` use dev-only bind mounts (`.:/app`) that override the built image — no code change, comment/doc note only.

## Capabilities

### New Capabilities

- `portal-containerization`: Docker build and compose orchestration for the Next.js portal frontend (Dockerfile, compose service, build context hygiene).

### Modified Capabilities

- `local-dev-stack`: Extends "Single-Command Local Stack Startup" to include `portal`; extends "Stable Inter-Service Communication via Docker DNS" to explicitly cover `gateway` → `chat_api`; adds a "Shared Root Dockerfile" refinement for multi-stage build; adds a new requirement that `docker-compose.yml` build contexts SHALL be constrained by `.dockerignore`; removes the now-orphaned `src/training_service/Dockerfile` this spec already disallows referencing.

## Impact

- **Code**: `Dockerfile` (root, multi-stage), new `src/portal/Dockerfile`, `docker-compose.yml` (portal service, gateway env fix), new `.dockerignore` (root + portal).
- **Removed**: `src/training_service/Dockerfile`, `src/gateway/requirements.txt`, `src/document_service/requirements.txt`.
- **Systems**: local Docker Compose dev stack, any CI/CD that builds these images. No production Kubernetes manifests are in scope (`deploy/k8s/mlflow/Dockerfile` untouched).
- **Downstream**: none — no runtime API behavior changes; gateway→chat_api calls still resolve to the same running chat_api service, only via a different hostname.

## Open Questions

- Confirm no external tooling (CI, k8s manifests, docs) still references `src/training_service/Dockerfile` or the two dead `requirements.txt` files before deleting.
- Confirm portal's runtime env vars (e.g. `NEXT_PUBLIC_API_URL` or equivalent) needed for the compose service — to be finalized in design.md.
