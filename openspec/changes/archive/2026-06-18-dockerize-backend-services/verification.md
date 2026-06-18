# Verification Plan

**Change:** dockerize-backend-services
**Generated:** 2026-06-18
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | local-dev-stack | Single-Command Local Stack Startup | All services start with docker compose up | Given a valid .env file, when `docker compose up` is run, then all 12 services start without error AND `curl localhost:8000/health` returns `{"status":"ok"}` | manual: `docker compose up` smoke test | - [ ] |
| 2 | local-dev-stack | Single-Command Local Stack Startup | Individual service health endpoints respond | Given all compose services are running, when `/health` is called on ports 8000–8005, then every endpoint returns HTTP 200 with `{"status":"ok"}` | manual: curl each health endpoint | - [ ] |
| 3 | local-dev-stack | Shared Root Dockerfile | All services built from shared Dockerfile | Given the root `Dockerfile` exists, when `docker compose build` completes, then every application service image uses `build.context: .` and `build.dockerfile: Dockerfile`; no service references `src/training_service/Dockerfile` | code review: docker-compose.yml build entries | - [ ] |
| 4 | local-dev-stack | Shared Root Dockerfile | Service CMD overrides route to correct app module | Given the gateway compose entry has `command: uvicorn src.gateway.main:app --host 0.0.0.0 --port 8000`, when the gateway container starts, then it binds on port 8000 and health endpoint responds | manual: `docker compose up gateway` + curl | - [ ] |
| 5 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Extraction worker reaches document_service via service name | Given `celery_worker_extraction` has `NER_DOCUMENT_SERVICE_URL=http://document_service:8000`, when the worker makes an HTTP call to document_service, then it resolves correctly AND no `extra_hosts: host.docker.internal` block exists in the service definition | code review: docker-compose.yml + manual worker log inspection | - [ ] |
| 6 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Extraction worker reaches model_serving via service name | Given `celery_worker_extraction` has `NER_MODEL_SERVING_URL=http://model_serving:8000`, when the worker calls the model serving endpoint, then the call resolves to the `model_serving` container without error | manual: worker log inspection during extraction task | - [ ] |
| 7 | local-dev-stack | Application Service Port Mapping | Services are reachable on distinct host ports | Given compose is running, when `curl localhost:<port>/health` is called for each of 8000, 8001, 8002, 8003, 8004, 8005, then each returns HTTP 200 from the correct service and no two share a host port | manual: curl all six ports | - [ ] |
| 8 | local-dev-stack | Service Startup Dependencies | Gateway waits for postgres to be healthy | Given `docker compose up` is run, when the gateway container starts, then it will not start before `postgres-test` passes its `pg_isready` healthcheck (visible in compose startup order logs) | code review: docker-compose.yml `depends_on` for gateway | - [ ] |
| 9 | local-dev-stack | Service Startup Dependencies | Celery workers wait for postgres and redis | Given `docker compose up` is run, when `celery_worker` and `celery_worker_extraction` start, then both wait for `postgres-test` (healthy) and `redis` (healthy) before starting | code review: docker-compose.yml `depends_on` for celery services | - [ ] |
| 10 | env-config | Environment Variable Documentation | .env.example documents all settings | Given the Settings class fields, when `.env.example` is read, then every field appears as `NER_<UPPER_CASE_FIELD_NAME>` with a comment and example value | code review: .env.example | - [ ] |
| 11 | env-config | Environment Variable Documentation | .env.example marks secret fields as required | Given `.env.example` is read, when secret field entries are examined, then `NER_JWT_SECRET`, `NER_MINIO_ACCESS_KEY`, `NER_MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` each have a `# REQUIRED` comment and a generation hint | code review: .env.example | - [ ] |
| 12 | env-config | Environment Variable Documentation | .env.example includes docker-compose variables | Given `.env.example` is read, when searched for `MINIO_ROOT_USER` and `AWS_ACCESS_KEY_ID`, then both appear as documented entries | code review: .env.example | - [ ] |
| 13 | env-config | Environment Variable Documentation | .env.example documents inter-service URL variables | Given `.env.example` is read, when searched for `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL`, then both appear with comments explaining docker-compose overrides them to container service names | code review: .env.example | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Root Dockerfile dependency installation | AI may copy the training_service Dockerfile's manual pip list instead of using `pip install .` from pyproject.toml, silently omitting newer deps | Confirm `Dockerfile` contains `pip install .` (or equivalent PEP 517 install) rather than a hardcoded package list; run `docker compose build` and verify a recently-added dep is importable inside the container |
| 2 | Port mapping in docker-compose.yml | AI may assign wrong host ports (e.g., collide two services or mismap extraction_service to 8004 instead of 8002) | Check each `ports:` entry against the spec table (gateway→8000, document→8001, extraction→8002, training→8003, model_serving→8004, annotation→8005) |
| 3 | Inter-service URL env vars | AI may leave `host.docker.internal` in `celery_worker_extraction` or fail to update both `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL` | `grep -r "host.docker.internal" docker-compose.yml` must return no results; check that both URL env vars use Docker service names |
| 4 | depends_on conditions | AI may add `depends_on` as a plain list without `condition: service_healthy`, which does not actually wait for health | Inspect every `depends_on` block in docker-compose.yml; services needing Postgres or Redis must use `condition: service_healthy` |
| 5 | training_service Dockerfile reference | AI may keep both the root Dockerfile and `src/training_service/Dockerfile` in the compose file without updating the training_service entry, or forget to update `training_service` to point at the root Dockerfile | Confirm `training_service` compose entry uses `dockerfile: Dockerfile` (root) not `src/training_service/Dockerfile` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-003-model-serving-topology | Shared Model Serving Layer with per-tenant routing | `model_serving` service must be reachable by `extraction_service`/Celery workers via a stable URL | Confirm `NER_MODEL_SERVING_URL=http://model_serving:8000` in `celery_worker_extraction`; confirm `model_serving` service is defined in docker-compose.yml |
| ADR-006-training-infrastructure | Celery-based async GPU workers | `celery_worker` and `celery_worker_extraction` must remain as separate Docker Compose services | Confirm both Celery worker services still exist in docker-compose.yml and continue to target the training and extraction queues respectively |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: `docker compose up` output shows all 12 services running without errors (container logs or `docker compose ps` output)
- [ ] Scenario 2: `curl` output for all six `/health` endpoints showing HTTP 200 and `{"status":"ok"}`
- [ ] Scenario 4: Gateway container starts and `/health` responds after `docker compose up gateway`
- [ ] Scenario 5: `celery_worker_extraction` container log showing successful connection to document_service (no connection-refused errors on startup)
- [ ] Scenario 6: Extraction task completes successfully with model_serving reachable via container DNS
- [ ] Scenario 7: Six `curl` responses confirming distinct port-to-service mapping
- [ ] Scenarios 10–13: `.env.example` diff showing all required entries present

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] `docker-compose.yml` reviewed: all 5 new service entries present, no `host.docker.internal` references remain
- [ ] Root `Dockerfile` reviewed: deps installed via `pip install .`, not a hardcoded package list
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation: `docker compose build` completed without errors and a Python import check inside the container confirms all pyproject.toml deps are importable
- [ ] Risk 2 mitigation: Port mapping table verified against spec row-by-row; no port collisions found
- [ ] Risk 3 mitigation: `grep "host.docker.internal" docker-compose.yml` returns no matches
- [ ] Risk 4 mitigation: Every `depends_on` that targets postgres-test or redis uses `condition: service_healthy`
- [ ] Risk 5 mitigation: `training_service` compose entry confirmed to use root `Dockerfile`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** dockerize-backend-services
**Proposal:** `openspec/changes/dockerize-backend-services/proposal.md`
**Spec files reviewed:**
- specs/local-dev-stack/spec.md
- specs/env-config/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
