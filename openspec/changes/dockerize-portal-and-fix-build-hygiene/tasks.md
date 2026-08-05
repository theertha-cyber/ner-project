## 1. Build Context Hygiene

- [x] 1.1 Add root `.dockerignore` excluding `.git`, `.env*`, `node_modules`, `**/__pycache__`, `.pytest_cache`, `*.jsonl`, `*.pptx`, `.venv`, `venv`, and other non-build artifacts (allow-list `src/`, `alembic/`, `alembic.ini`, `tenant_schema_ddl.py`, `pyproject.toml`, `poetry.lock` are not excluded)
- [x] 1.2 Add `src/portal/.dockerignore` excluding `node_modules`, `.next`, `.git`, `.env*`
- [x] 1.3 Verify: `docker compose build` for all backend services succeeds with `.dockerignore` in place (manual run, scenario 12)
- [x] 1.4 Verify: `docker compose build portal` succeeds with `src/portal/.dockerignore` in place (manual run, scenario 13)

## 2. Portal Containerization

- [x] 2.1 Grep `src/portal/src` for the actual env var name used for the gateway/API base URL (do not assume a name)
- [x] 2.2 Create `src/portal/Dockerfile` with `deps`, `build`, `runner` stages targeting the Next.js `standalone` output
- [x] 2.3 Add `portal` service to `docker-compose.yml` — build context `src/portal`, host port `3000:3000`, gateway URL env var from 2.1
- [x] 2.4 Verify: `docker compose build portal` completes successfully (scenario 14)
- [x] 2.5 Verify: inspect final `portal` image layer — confirm dev dependencies/build tooling absent (scenario 15)
- [x] 2.6 Verify: `docker compose up portal` (with gateway running) — `curl -I http://localhost:3000` returns 200, app shell renders in browser (scenarios 3, 16)
- [x] 2.7 Verify: portal successfully calls gateway from within the compose network (scenario 17)

## 3. Gateway to chat_api Docker DNS Fix

- [x] 3.1 Update `docker-compose.yml` `gateway.environment.NER_CHAT_API_URL` from `http://host.docker.internal:8006` to `http://chat_api:8000`
- [x] 3.2 Add `chat_api: condition: service_started` to `gateway.depends_on`
- [x] 3.3 Verify: cold `docker compose down && docker compose up` — gateway's first proxied request to chat_api succeeds without connection error (scenario 11)

## 4. Root Dockerfile Multi-Stage Conversion

- [x] 4.1 Rewrite root `Dockerfile` with a `builder` stage (Poetry install) and a slim runtime stage that copies only installed dependencies and app source
- [x] 4.2 Verify: `docker compose build` — all backend service images build successfully from the new root `Dockerfile` (scenario 4)
- [x] 4.3 Verify: gateway container starts and responds on host port `8000` (scenario 5)
- [x] 4.4 Verify: final runtime image does not contain Poetry, app still starts and serves (scenario 6)
- [x] 4.5 Verify: full `docker compose up` — hit `/health` on gateway, document_service, extraction_service, training_service, model_serving, annotation_service, all return 200 (scenario 2)
- [x] 4.6 Verify: exercise one functional (non-health) request against gateway, extraction_service, and training_service to confirm no dropped runtime dependency (Risk 2 mitigation)
- [x] 4.7 Verify: existing DNS-based inter-service scenarios still pass post-rebuild — extraction worker to document_service/model_serving, training_service to model_serving warmup, model_serving to training_service (scenarios 7-10, regression check)

## 5. Dead File Cleanup

- [x] 5.1 Grep full repo (excluding `openspec/changes/archive/**`) for `src/training_service/Dockerfile`, `src/gateway/requirements.txt`, `src/document_service/requirements.txt` — confirm zero live references
- [x] 5.2 Delete `src/training_service/Dockerfile`
- [x] 5.3 Delete `src/gateway/requirements.txt`
- [x] 5.4 Delete `src/document_service/requirements.txt`
- [x] 5.5 Verify: `docker compose build` still succeeds for all services after deletion (regression check, part of scenario 4)

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 6.6 Run `openspec validate dockerize-portal-and-fix-build-hygiene --type change --strict` and confirm it exits clean before archive.
