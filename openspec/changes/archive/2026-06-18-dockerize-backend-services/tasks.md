## 1. Root Dockerfile

- [x] 1.1 Create `Dockerfile` at the project root: use `python:3.11-slim`, `WORKDIR /app`, copy `pyproject.toml` + `src/`, install all deps with `pip install .`, then install torch CPU separately (`--index-url https://download.pytorch.org/whl/cpu`), and `EXPOSE 8000` with a default `CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- [x] 1.2 Verify the root `Dockerfile` builds without errors: `docker build -t ner-base .`
- [x] 1.3 Confirm `src/training_service/Dockerfile` is no longer referenced anywhere in `docker-compose.yml` (the training_service entry will use the root Dockerfile)

## 2. docker-compose.yml — New Application Services

- [x] 2.1 Add `gateway` service: `build: {context: ., dockerfile: Dockerfile}`, `command: uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000`, `ports: ["8000:8000"]`, `environment` with all `NER_*` vars, `depends_on: postgres-test (service_healthy), redis (service_healthy)`
- [x] 2.2 Add `document_service` service: same build, `command: uvicorn src.document_service.main:app --host 0.0.0.0 --port 8000`, `ports: ["8001:8000"]`, appropriate `NER_*` env vars, `depends_on: postgres-test (service_healthy)`
- [x] 2.3 Add `extraction_service` service: same build, `command: uvicorn src.extraction_service.main:app --host 0.0.0.0 --port 8000`, `ports: ["8002:8000"]`, appropriate `NER_*` env vars, `depends_on: postgres-test (service_healthy), redis (service_healthy)`
- [x] 2.4 Add `model_serving` service: same build, `command: uvicorn src.model_serving.main:app --host 0.0.0.0 --port 8000`, `ports: ["8004:8000"]`, appropriate `NER_*` env vars (no DB dependency required)
- [x] 2.5 Add `annotation_service` service: same build, `command: uvicorn src.annotation_service.main:app --host 0.0.0.0 --port 8000`, `ports: ["8005:8000"]`, appropriate `NER_*` env vars, `depends_on: postgres-test (service_healthy)`

## 3. docker-compose.yml — Update Existing Services

- [x] 3.1 Update `training_service` entry: change `build.dockerfile` from `src/training_service/Dockerfile` to `Dockerfile` (root)
- [x] 3.2 Update `celery_worker_extraction`: set `NER_DOCUMENT_SERVICE_URL=http://document_service:8000` and `NER_MODEL_SERVING_URL=http://model_serving:8000`, and remove the `extra_hosts: [host.docker.internal:host-gateway]` block
- [x] 3.3 Add `depends_on` conditions to `celery_worker_extraction` for `document_service` and `model_serving` (so they start before the extraction worker)
- [x] 3.4 Confirm no `host.docker.internal` references remain anywhere in `docker-compose.yml`: `grep host.docker.internal docker-compose.yml` should return nothing

## 4. Environment Documentation

- [x] 4.1 Add `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL` to `.env.example` with comments explaining they default to localhost for bare-metal and are overridden to Docker service names inside docker-compose
- [x] 4.2 Verify `.env.example` still contains all existing required entries: `NER_JWT_SECRET`, `NER_MINIO_ACCESS_KEY`, `NER_MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` each with `# REQUIRED` and a generation hint

## 5. Smoke Testing

- [x] 5.1 Run `docker compose build` and confirm all service images build without errors
- [x] 5.2 Run `docker compose up -d` and wait for all services to reach running state (`docker compose ps`)
- [x] 5.3 Curl all six health endpoints and confirm HTTP 200: `localhost:8000/health`, `localhost:8001/health`, `localhost:8002/health`, `localhost:8003/health`, `localhost:8004/health`, `localhost:8005/health`
- [x] 5.4 Check `celery_worker_extraction` container logs for successful startup (no `ConnectionRefused` to document_service or model_serving)

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.6 Run `openspec validate dockerize-backend-services --type change --strict` and confirm it exits clean before archive.
