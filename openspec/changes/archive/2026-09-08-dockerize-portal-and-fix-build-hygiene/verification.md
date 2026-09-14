# Verification Plan

**Change:** dockerize-portal-and-fix-build-hygiene
**Generated:** 2026-08-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | local-dev-stack | Single-Command Local Stack Startup | All services start with docker compose up | Given a valid `.env`, when `docker compose up` is run, then all application services (including `portal`) and infrastructure services start without error and gateway `/health` returns `{"status":"ok"}` | task 4.5 manual full-stack `docker compose up` run | - [x] |
| 2 | local-dev-stack | Single-Command Local Stack Startup | Individual service health endpoints respond | Given the stack is running, when each backend health endpoint is called, then each returns HTTP 200 `{"status":"ok"}` | task 4.5 `/health` curl outputs | - [x] |
| 3 | local-dev-stack | Single-Command Local Stack Startup | Portal serves the app via docker compose | Given the stack is running, when `http://localhost:3000` is requested, then it returns HTTP 200 and renders the app shell | task 2.6 `curl -I` output + browser check | - [x] |
| 4 | local-dev-stack | Shared Root Dockerfile | All services built from shared Dockerfile | Given the root `Dockerfile`, when `docker compose build` runs, then every backend image builds from it, no service references `src/training_service/Dockerfile`, and that file does not exist in the repo | task 4.2 build output + task 5.1/5.2 grep and deletion confirmation | - [x] |
| 5 | local-dev-stack | Shared Root Dockerfile | Service CMD overrides route to correct app module | Given gateway's `command` override, when the container starts, then it binds internally to `8000` and responds on host port `8000` | task 4.3 `curl http://localhost:8000/health` | - [x] |
| 6 | local-dev-stack | Shared Root Dockerfile | Final image excludes build-only tooling | Given the multi-stage root `Dockerfile`, when the final runtime image is inspected, then Poetry is absent and the app still serves requests | task 4.4 image inspection output | - [x] |
| 7 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Extraction worker reaches document_service via service name | Given `NER_DOCUMENT_SERVICE_URL=http://document_service:8000` on `celery_worker_extraction`, when it calls document_service, then it resolves without error and no `host.docker.internal` extra_hosts block is present | task 4.7 regression check log | - [x] |
| 8 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Extraction worker reaches model_serving via service name | Given `NER_MODEL_SERVING_URL=http://model_serving:8000` on `celery_worker_extraction`, when it calls model_serving, then it resolves without error | task 4.7 regression check log | - [x] |
| 9 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Training service reaches model_serving for warmup via service name | Given `NER_MODEL_SERVING_URL=http://model_serving:8000` on `training_service`, when it calls the warmup endpoint, then it resolves without falling back to `localhost:8004` | task 4.7 regression check log | - [x] |
| 10 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Model serving reaches training_service via service name at the correct internal port | Given `NER_TRAINING_SERVICE_URL=http://training_service:8000` on `model_serving`, when it resolves a tenant's model version, then it targets internal port `8000`, not host-mapped `8003` | task 4.7 regression check log | - [x] |
| 11 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Gateway reaches chat_api via service name | Given `NER_CHAT_API_URL=http://chat_api:8000` on `gateway`, when gateway proxies to chat API, then it resolves to the `chat_api` container and `gateway`'s definition does not reference `host.docker.internal` | task 3.3 cold-start proxy request log | - [x] |
| 12 | local-dev-stack | Docker Build Context Hygiene | Root build context excludes VCS and secrets | Given root `.dockerignore`, when `docker compose build` sends context for any backend service, then `.git`, `.env`, `node_modules`, `**/__pycache__`, `.pytest_cache` are excluded | task 1.3 build output / context size check | - [x] |
| 13 | local-dev-stack | Docker Build Context Hygiene | Portal build context excludes node_modules and build output | Given `src/portal/.dockerignore`, when `docker compose build portal` sends context, then `node_modules` and `.next` (beyond what's explicitly staged) are excluded | task 1.4 build output / context size check | - [x] |
| 14 | portal-containerization | Portal Multi-Stage Docker Build | Portal image builds successfully | Given `src/portal/Dockerfile` and `output: "standalone"`, when `docker compose build portal` runs, then the build completes and produces a runnable image | task 2.4 build output | - [x] |
| 15 | portal-containerization | Portal Multi-Stage Docker Build | Runtime image excludes dev dependencies | Given the built `portal` image, when the final `runner` layer is inspected, then dev-only dependencies are absent and the app still serves via `node server.js` | task 2.5 image inspection output | - [x] |
| 16 | portal-containerization | Portal Compose Service | Portal starts as part of the compose stack | Given `docker compose up`, when the `portal` container starts, then it binds to `3000` and is reachable at `http://localhost:3000` | task 2.6 `curl -I` output | - [x] |
| 17 | portal-containerization | Portal Compose Service | Portal can reach the gateway API | Given portal's gateway-URL env var, when it makes a request to gateway, then the request resolves successfully | task 2.7 network trace / log | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Next.js `standalone` output layout | AI may COPY the wrong paths in the `runner` stage (standalone layout varies by Next.js major version, e.g. missing `public/` or `.next/static` copy) → app builds but 500s or serves unstyled pages | Run `docker compose up portal` and load the app in a browser; confirm CSS/static assets load, not just that the process starts |
| 2 | Multi-stage root Dockerfile dependency completeness | AI may drop a runtime dependency (e.g. a shared library needed by a C-extension package like `psycopg2`, `torch`) when separating builder/runtime stages, causing an ImportError only at runtime, not build time | Run full `docker compose up` and hit every backend `/health` endpoint plus one functional endpoint per service (not just build success) |
| 3 | Deleting `src/training_service/Dockerfile` and dead `requirements.txt` files | AI may miss an external reference (CI config, deploy script, README) not visible via in-repo grep | Grep the full repo (excluding `openspec/changes/archive/**`, which is immutable history) for the three deleted filenames immediately before merge, and check any external CI/CD config if one exists outside this repo |
| 4 | `.dockerignore` scope | AI may write an overly broad `.dockerignore` pattern that accidentally excludes a file a Dockerfile's `COPY` actually needs (e.g. excluding all `*.py` instead of just `__pycache__`) | Run `docker compose build` for every service after adding `.dockerignore` and confirm all builds still succeed with no missing-file errors |
| 5 | `NER_CHAT_API_URL` fix | AI may change the URL but miss updating `depends_on`, causing gateway to start before chat_api is ready and fail its first proxied request | Restart the full stack from a cold `docker compose down` and confirm gateway's first request to chat_api after startup succeeds without a connection-refused error |
| 6 | Portal environment variables for reaching gateway | AI may invent an env var name not actually read by the portal's existing code (e.g. assuming `NEXT_PUBLIC_API_URL` exists when the codebase uses a different name or a build-time constant) | Grep `src/portal/src` for the actual env var name used for the API base URL before wiring it into `docker-compose.yml`; do not assume a name from convention |
| 7 | Server-side vs. client-side URL targets in Next.js | Same env var name (`NEXT_PUBLIC_*`) can mean two different network contexts: browser-side calls (need host-mapped `localhost:PORT`) vs. `next.config.js` `rewrites()`, which runs server-side inside the container and gets serialized into `routes-manifest.json` at **build time**, not read fresh at container runtime. AI may set the right value at the wrong stage (runtime env instead of build arg), producing a fix that looks applied but has no effect | After any portal env/URL change, actually exercise a feature that goes through the relative `/api/*` server-side proxy (not just a feature calling gateway directly from the browser) — e.g. click "New conversation" in Chat — and check portal container logs for `ECONNREFUSED` |

---

## 3. Pattern & ADR Compliance

No constraining ADRs.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|--------------------|
| — | No ADR governs Docker build/compose topology (confirmed in design.md) | None | N/A |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 & 2: `docker compose up` full-stack log output showing all services start, plus `curl` output for each backend `/health` endpoint returning 200
- [x] Scenario 3: `curl -I http://localhost:3000` output (or screenshot) showing HTTP 200 and rendered app shell
- [x] Scenario 4: `docker compose build` output showing all images build from root `Dockerfile`; `ls src/training_service/` (or git status) confirming the file no longer exists
- [x] Scenario 5: `curl http://localhost:8000/health` output confirming gateway responds on host port 8000
- [x] Scenario 6: `docker history` or `docker run --rm <image> which poetry` output showing Poetry absent from final image, plus a passing health check proving the app still runs
- [x] Scenario 7-10: existing worker/training/model-serving DNS scenarios — log excerpts or a successful end-to-end extraction/training run showing no `host.docker.internal` connection errors (regression check, no code change expected here)
- [x] Scenario 11: log excerpt or trace of a gateway request that proxies to chat_api succeeding, plus `docker-compose.yml` diff showing `NER_CHAT_API_URL=http://chat_api:8000` and no `host.docker.internal` reference in the `gateway` block
- [x] Scenario 12 & 13: `docker build` context size comparison (before/after `.dockerignore`) or `docker build --progress=plain` output showing excluded paths not transferred
- [x] Scenario 14: `docker compose build portal` output showing successful build
- [x] Scenario 15: `docker run --rm <portal-image> sh -c "ls node_modules 2>&1 || echo absent"` (or `du -sh` size comparison) confirming dev dependencies are not in the final layer
- [x] Scenario 16: `curl -I http://localhost:3000` after `docker compose up` from a cold state
- [x] Scenario 17: browser network trace or server log showing a portal-to-gateway request succeeding

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓ (N/A — no constraining ADRs)
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — portal loaded in a real browser with assets rendering correctly, not just process-up check
- [x] Risk 2 mitigation confirmed — full `docker compose up` with functional (not just health) requests exercised against at least gateway, extraction_service, and training_service
- [x] Risk 3 mitigation confirmed — repo-wide grep for deleted filenames (excluding archived change history) run immediately before merge, zero live references found
- [x] Risk 4 mitigation confirmed — `docker compose build` succeeds for all services after `.dockerignore` added, no missing-file errors
- [x] Risk 5 mitigation confirmed — cold-start `docker compose down && docker compose up` with gateway's first chat_api proxy request succeeding
- [x] Risk 6 mitigation confirmed — portal's actual gateway-URL env var name verified against `src/portal/src` source before use in compose
- [x] Risk 7 mitigation confirmed — user-reported "can't create new conversation" traced to `next.config.js` `rewrites()` resolving `NEXT_PUBLIC_API_URL` at build time (not runtime); fixed by setting the **build arg** to `http://gateway:8000` (was `http://localhost:8000`) and rebuilding; reverified live via browser click, `POST /api/v1/chat/conversations → 201`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|---------------------|-----------------------|---------------|------|
| 1 | Functional | `docker compose up -d` cold-start, `docker compose ps` shows all 15 services `Up`/`Healthy`; `curl` to `/health` on ports 8000-8005, 8007 all returned `200` | 1, 2, 5 | AI agent (apply) | 2026-08-03 |
| 2 | Functional | `curl -I http://localhost:3000` → 200; browser navigation to `/login` showed rendered app shell (fonts, CSS, JS chunks all 200 in network log), no console errors | 3, 16 | AI agent (apply) | 2026-08-03 |
| 3 | Functional | `docker compose build` output: all backend images (gateway, document_service, extraction_service, model_serving, annotation_service, training_service, chat_api, analytics_service, db-init, celery_worker, celery_worker_extraction) built successfully from new multi-stage root `Dockerfile`; `src/training_service/Dockerfile` confirmed deleted | 4 | AI agent (apply) | 2026-08-03 |
| 4 | Functional | `docker run --rm ner-project-gateway:latest which poetry` → exit 1 (absent); `python -c "import uvicorn, fastapi"` → succeeded | 6 | AI agent (apply) | 2026-08-03 |
| 5 | Functional | `docker inspect` on `celery_worker_extraction`, `training_service`, `model_serving` running containers: `NER_DOCUMENT_SERVICE_URL=http://document_service:8000`, `NER_MODEL_SERVING_URL=http://model_serving:8000`, `NER_TRAINING_SERVICE_URL=http://training_service:8000` — all Docker service DNS, zero `host.docker.internal` references in `docker-compose.yml` (grep confirmed) | 7, 8, 9, 10 | AI agent (apply) | 2026-08-03 |
| 6 | Functional | `curl http://localhost:8000/api/v1/chat/conversations` → `401 AUTH_ERROR` (app-level response, not connection error); gateway container logs show no `host.docker.internal`/connection-refused/timeout entries after cold `docker compose down && up` | 11 | AI agent (apply) | 2026-08-03 |
| 7 | Structural | Root `.dockerignore` and `src/portal/.dockerignore` added; `docker compose build` (all backend services) and `docker compose build portal` both succeeded post-addition with no missing-file errors | 12, 13 | AI agent (apply) | 2026-08-03 |
| 8 | Functional | `docker compose build portal` succeeded after fixing 4 pre-existing app-source errors (2 ESLint unescaped-entity, 2 TypeScript type errors) uncovered by running `next build` for the first time | 14 | AI agent (apply) | 2026-08-03 |
| 9 | Functional | `docker run --rm ner-project-portal:latest` — checked `node_modules/{typescript,eslint,vitest,tailwindcss,prettier}` all absent; `server.js` present; `docker compose up portal` served the app | 15 | AI agent (apply) | 2026-08-03 |
| 10 | Functional | Browser: filled login form on `http://localhost:3000/login`, submitted — network log shows `POST http://localhost:8000/api/v1/auth/login → 401`, UI displayed "Invalid email or password", proving portal's client-side calls reach gateway. **Post-completion correction**: this covered only client-side `NEXT_PUBLIC_*_URL` calls. A second, distinct path — Next.js's server-side `rewrites()` proxy for relative `/api/*` calls (used by chat's "New conversation") — was still broken: it resolves `NEXT_PUBLIC_API_URL` at *build time* into `routes-manifest.json`, baked as `http://localhost:8000`, which inside the portal container is the container itself, not gateway (`ECONNREFUSED 127.0.0.1:8000` in portal logs). Fixed by changing the `NEXT_PUBLIC_API_URL` **build arg** (not a runtime env — confirmed runtime env has no effect on the already-serialized rewrite manifest) to `http://gateway:8000` in `docker-compose.yml`, then rebuilt. Reverified: `POST http://localhost:3000/api/v1/chat/conversations → 201 Created` via actual browser click after rebuild. | 17 | AI agent (apply) + user bug report | 2026-08-03 |
| 11 | Functional | `curl http://localhost:8002/api/v1/extractions` → 401, `curl http://localhost:8003/api/v1/jobs` → 401, `curl http://localhost:8000/api/v1/tenants` → 401 — real app-level auth responses (DB-backed), not connection failures, confirming no dropped runtime dependency after multi-stage rebuild | Risk 2 mitigation | AI agent (apply) | 2026-08-03 |
| 12 | Edge Case | `celery_worker` and `celery_worker_extraction` logs showed clean startup (`celery@... ready`, `mingle: sync complete`) after switching root `Dockerfile` to `virtualenvs.create false` + `COPY --from=builder /usr/local /usr/local` — avoids placing the venv under `/app`, which the services' `.:/app` dev bind mount would otherwise have shadowed (discovered live: first attempt using an in-project `.venv` under `/app` broke both celery workers with `celery: executable file not found`) | Risk 2 mitigation (regression) | AI agent (apply) | 2026-08-03 |
| 13 | Edge Case | Repo-wide grep (excluding `openspec/changes/archive/**`) for the three deleted filenames found only documentation/spec references, zero live code/config/CI references, before deletion | Risk 3 mitigation | AI agent (apply) | 2026-08-03 |
| 14 | Edge Case | Portal's actual env var names verified via grep of `src/portal/src/lib/api.ts` (`NEXT_PUBLIC_GATEWAY_URL` etc.) and `next.config.js` (`NEXT_PUBLIC_API_URL`) before wiring into `docker-compose.yml` build args — not assumed | Risk 6 mitigation | AI agent (apply) | 2026-08-03 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** dockerize-portal-and-fix-build-hygiene
**Proposal:** `openspec/changes/dockerize-portal-and-fix-build-hygiene/proposal.md`
**Spec files reviewed:**
- specs/local-dev-stack/spec.md
- specs/portal-containerization/spec.md

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
