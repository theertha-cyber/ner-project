# Deploy Platform to Kubernetes on Azure (AKS) — End-to-End Discovery and Requirements Baseline

## Document Control

| Field | Value |
| --- | --- |
| Title | Deploy the Multi-Tenant Custom NER Platform to Kubernetes on Azure (AKS) |
| Version | 1.0 (rev 2 — clarified baseline incorporating Q1–Q10 resolutions; supersedes the draft) |
| Status | Approved baseline for design (analysis gate pending) |
| Date | 2026-09-08 |
| Run | `deploy-platform-kubernetes-azure-20260908` (stage: analysis, target: full) |
| Prepared from | Run state (`.iris/runs/deploy-platform-kubernetes-azure-20260908/RUN-STATE.md`); `PROJECT.md`; `docker-compose.yml`; root `Dockerfile`; `src/portal/Dockerfile`; `src/shared/config.py`; `.env.example`; `deploy/k8s/mlflow/*`; `deploy/observability/*`; `docs/adr/001-007`; `docs/design-docs/01-technical-design.md`; `docs/requirements.md`; `docs/NER-Platform-Production-Plan.pptx`; `docs/production-plan.md` (git HEAD — deleted from working tree); `docs/deployment-plan.md` (git HEAD — deleted from working tree); `docs/kubernetes-silo-deployment-plan.md` (git HEAD — deleted from working tree); `.github/workflows/telemetry-scan.yml`; `src/*/main.py`, `src/chat_api/services/rate_limiter.py`, `src/portal/src/lib/api.ts`, `src/portal/.env.local`; vendor governance baseline (`incode-opencode/governance/baseline-policy.json`) |
| Owners and approvers | Platform team (3 developers). Run approver: **platform team (3 developers) — Resolved (Q10a)** |
| Prepare by | Analyser agent (requirement-analysis skill) |

> **Working-tree note (verified 2026-09-08):** `docs/production-plan.md`, `docs/deployment-plan.md`, `docs/kubernetes-silo-deployment-plan.md` and `docs/NER-Platform-Production-Plan.pptx` are present in git HEAD but **deleted from the working tree** (uncommitted deletions; the PPTX was present at the start of this analysis and removed during it). The content of all four was recovered from git HEAD. **The deletions were confirmed INTENTIONAL by the human (Q10d): the four planning documents are RETIRED and are NOT the deployment intent.** Scope re-anchors to the user's ask + `PROJECT.md` + repository evidence. The recovered content is retained throughout this document as historical provenance only — it informed the analysis but is not binding; every §-citation to those documents is marked "retired doc".

## Run Configuration Answers

| Answer | Value | Status | Source |
| --- | --- | --- | --- |
| Target | full | confirmed | RUN-STATE.md `Target: full` |
| Track | full | confirmed | RUN-STATE.md `Track: full` |
| Codebase | greenfield | confirmed | RUN-STATE.md `Codebase: greenfield` |
| UI Design | — | no row | The source states nothing about UI Design. RUN-STATE.md records it as "absent until the UI intake question at step 8a". |
| Deep Review | — | no row | The source states nothing about Deep Review. |

Status notes: `Codebase: greenfield` is recorded as dispatched. The discovery nuance is that while the **AKS target is greenfield** (no cloud infrastructure exists), the **application being deployed is an existing brownfield runtime** (the docker-compose stack). This document therefore includes a Current State section with file:line evidence; the two views are reconciled by treating the compose stack as the existing behaviour that the AKS deployment must reproduce. No row is confirmed for UI Design or Deep Review because no source statement exists — the Orchestrator will ask its own UI-intake question at its step.

## Executive Summary

**Problem.** The Multi-Tenant Custom NER Platform is a working application that has never been deployed. It runs as a single docker-compose stack on a developer laptop or CI runner: 8 FastAPI services, 2 Celery workers, a Next.js portal, and self-hosted Postgres/pgvector, MinIO, Redis, MLflow and a local OpenTelemetry observability stack. The only Kubernetes artifacts in the repository are an MLflow Deployment and Service. There is no container registry reference, no ingress, no TLS, no Terraform, no Helm chart, and no CI build/push/deploy pipeline (the sole workflow is a telemetry-scan release gate).

**Proposed outcome.** Deploy the existing platform to Kubernetes on Azure (AKS) as a single-region, shared multi-tenant deployment, replacing self-hosted stateful components with Azure managed services per the recovered production plan, with all deployment-critical decisions recorded and blocking decisions submitted to the human before design begins.

**Scope.** The entire compose application surface (8 FastAPI services + portal + 2 Celery workers + MLflow) plus the supporting Azure platform: container registry, ingress/TLS, secrets, persistence, GPU-capable training (ADR-006), observability backends, db-init ordering, CI/CD build-and-deploy, and operational foundations. Out of scope: the production plan's control-plane and capability-plane refactors (SSO/Entra ID, metering, quota enforcement, LLM broker, capability registry, chatbot-parity work) unless the human expands scope (Blocking Question Q1).

**Major constraints.** Azure, single region, shared multi-tenant (user ask + production plan §2.3.9). No external SLA; 99.5% internal availability target. Team of 3 developers with no dedicated DevOps/QA/security. ~$1,900–2,600/month infrastructure+LLM cost envelope (production plan §10). Vendor governance baseline enforces: no hardcoded secrets, threat model for new external boundaries, encryption in transit and at rest, tenant isolation independent of AI output, structured JSON logging.

**Known contradictions surfaced (not resolved here).** (1) Broker: documented RabbitMQ (PROJECT.md, ADR-006) vs implemented Redis Celery broker (config.py, compose). (2) RPO/RTO: production plan (15 min / 4 h) vs technical design (5 min / 30 min). (3) Portal URL wiring: browser calls service origins directly and URLs are baked at build time (A2/A3 of the recovered silo plan, verified in code). (4) LLM provider: OpenAI (implemented default) vs Azure OpenAI (documented intent). (5) Observability: the recovered silo plan's "zero observability" claim is **outdated** — the current code has full OTel/Prometheus/structured-logging support built since.

**Readiness summary.** **Conditionally Ready.** The outcome, platform inventory, and most NFRs are established from rich repository evidence; 10 blocking questions (2 batches of 5) must be answered before design can begin on the affected workstreams (infrastructure, secrets, observability, GPU, CI/CD, security posture).

## Business Context and Success Measures

**Business problem.** The platform works locally but is not deliverable to users or clients: no deployment, no HA, no backups, no secrets management, no way to measure anything in production. The production plan frames one deployment as the difference between an application and a SaaS platform; the presenter deck's standing promise is "one platform deployment, one API gateway, sealed tenant scopes" — a promise the current compose-only state cannot keep.

**Expected outcomes (from the recovered production plan).**
- A staging and a production AKS environment running all services, traced and dashboarded, deployable from a git tag (production plan §9, Phase 1 milestone).
- No tenant can degrade another (production plan §4) — *note: not achievable by the current code; see NFR-NOISE-001 and Risk R-004*.
- Every tenant's consumption visible and enforced (production plan §4) — *note: metering/quota enforcement is Phase 2 work, out of scope unless expanded; current code has quota columns but no runtime enforcement*.
- Survives a node failure and a security review (production plan §4).

**Success measures.** Definable crisply per the acceptance question (Q10). Recommended measures drawn from the docs: (a) staging runs all services with smoke test green (login → upload → extract → chat); (b) production reachable at the chosen hostname over TLS; (c) telemetry visible in the chosen backends for all services; (d) first Postgres PITR restore drill completed; (e) no tenant data or secrets in logs, per the telemetry-scan gate.

**Budget and timeline.** Production plan §10: ~$1,675/month fixed infra + ~$215–940/month LLM at 10–15 tenants, total ~$1,900–2,600/month; Phase 1 is estimated at 8 weeks for the full program (landing zone 3w, Helm 2.5w, CI/CD 1.5w, secrets 0.5w, observability 3.5w, backups 0.5w). No run-specific deadline stated — confirmation requested via Q10.

**Constraints.** Single region Central India (production plan §2.4 assumption — confirm via Q2); no compliance certification at go-live but SOC 2 / ISO 27001 controls not actively violated (production plan §2.4); no external SLA (production plan §4.8); single-tenant billing/metering deferred.

## Stakeholders, Users, Roles and Personas

| Stakeholder | Role in this run | Notes |
| --- | --- | --- |
| Platform team (3 developers) | Build, operate, on-call; the only engineering resource | Production plan §2.3.13: junior team, no DevOps/QA/security |
| InApp leadership | Approver of subscription, region, GPU line, provider, staging (production plan §11 "Decisions needed to start Phase 1"); run approver unconfirmed (Q10) | Cost owner (~$1.9-2.6k/mo) |
| IT / networking (InApp) | DNS zone + record, certificate path, egress/VPN decisions | Deployment-plan §4-5; DNS is on the critical path (silo plan §6) |
| Legal / security | Sign-off on LLM egress of documents (deployment-plan §10) | "Documents processed here may contain HR or personal data"; data classification question Q2 |
| Tenants (System Admin, Tenant Admin, Annotator, Business User) | End users of the deployed platform; four existing roles confirmed sufficient (production plan §2.3.5) | No document-level ACLs |
| Existing chatbot owners (InApp teams) | Not involved in this run (portfolio parity is Phase 3) | Out of scope unless expanded |

## Scope

### In Scope
1. Deploy all 8 FastAPI services (`gateway`, `chat_api`, `document_service`, `extraction_service`, `model_serving`, `annotation_service`, `training_service`, `analytics_service`), 2 Celery workers (training queue `celery`, extraction queue `extraction`), the Next.js portal, and MLflow to AKS.
2. Azure platform foundations: container registry, ingress + TLS, secrets provisioning, persistence strategy (managed vs self-hosted), db-init ordering, GPU training decision, observability backends, CI/CD build/push/deploy pipeline, environment ladder (dev/staging/prod).
3. Cluster-readiness deltas that are **configuration or minimal code**: probes wiring (`/health/live` + startup probe on `model_serving`), workers running image code (removal of source bind-mount), resource requests/limits, migration/seed split, portal URL wiring for the chosen hostname.
4. Operational foundations: backups + PITR + first restore drill, monitoring/alerting in the chosen backends, deployment and rollback procedures, smoke test.

### Out of Scope (unless expanded — Q1)
- Control plane (Phase 2): Entra ID SSO, token revocation, metering (`usage_events`), entitlements + hard quota enforcement (402), service-to-service auth, admin console, RBAC matrix, generated cross-tenant isolation suite.
- Capability plane (Phase 3): capability registry + profiles, LLM broker, golden-set harness, Graph-RAG, chart agent, multi-format ingestion, consistent-hash model routing, per-tenant queue fairness, KEDA.
- Pricing, licensing, branding, compliance certification, multi-region (production plan §2.3.11 deferred).
- The Redis-backed rate limiter is a Phase-1 item in the production plan but is **code**, not deployment; whether it lands in this run is part of Q1 scope.
- UI/UX design work (portal exists; only URL wiring touches it).

### Future Scope
Phases 2–5 of the production plan (control layer, capability plane, hardening, beta→GA); silo/per-tenant-cell model (kubernetes-silo-deployment-plan Stages 3–4); multi-region; pricing/SLA/compliance (all explicitly deferred with named reversal points).

## Current State

The application is a working brownfield runtime on docker-compose. Every material fact below is file:line verified.

**Platform inventory (compose runtime).** `docker-compose.yml` defines 22 containers:

| Workload | Image / build | In-container port | Host port | Dependencies (depends_on / explicit env URLs) |
| --- | --- | --- | --- | --- |
| `gateway` | root Dockerfile | 8000 | 8000 | postgres, redis, db-init, chat_api, training_service; env: `NER_DOCUMENT_SERVICE_URL`, `NER_EXTRACTION_SERVICE_URL`, `NER_MODEL_SERVING_URL`, `NER_TRAINING_SERVICE_URL`, `NER_CHAT_API_URL`, `NER_ANALYTICS_SERVICE_URL` (docker-compose.yml:90-120) |
| `chat_api` | root Dockerfile | 8000 | 8006 | postgres, db-init; env: `NER_MODEL_SERVING_URL`, `NER_ENTITY_RESOLUTION_ENABLED` (122-141) |
| `document_service` | root Dockerfile | 8000 | 8001 | postgres, db-init, minio (`NER_MINIO_ENDPOINT`) (143-159) |
| `extraction_service` | root Dockerfile | 8000 | 8002 | postgres, redis, db-init; env: redis, `NER_CELERY_BROKER_URL`/`RESULT_BACKEND` = redis, document/model/training URLs (161-185) |
| `model_serving` | root Dockerfile | 8000 | 8004 | postgres, minio, mlflow, training_service; env: `NER_MLFLOW_TRACKING_URI`, `NER_MINIO_ENDPOINT` (187-207) |
| `annotation_service` | root Dockerfile | 8000 | 8005 | postgres, db-init (209-224) |
| `training_service` | root Dockerfile | 8000 | 8003 | postgres, redis, db-init; env: redis, celery broker=redis, minio, mlflow, annotation, model (226-251) |
| `analytics_service` | root Dockerfile | 8000 | 8007 | postgres, db-init (284-300) |
| `celery_worker` (training) | root Dockerfile | — | — | `celery -A src.training_service.celery_app worker --concurrency=1`; `NER_TRAINING_DEVICE=cpu`; **bind-mounts `.:/app`**; env: redis broker/backend, minio, mlflow (253-282) |
| `celery_worker_extraction` | root Dockerfile | — | — | `celery -A src.extraction_service.celery_app worker -Q extraction --pool=solo`; **bind-mounts `.:/app`**; env: redis broker/backend, document/model/training URLs (302-330) |
| `portal` | `src/portal/Dockerfile` (node:20-alpine, Next.js standalone) | 3000 | 3000 | gateway; build args `NEXT_PUBLIC_*` (see A2 below) (399-416) |
| `mlflow` | `deploy/k8s/mlflow/Dockerfile` (ghcr.io/mlflow/mlflow:v2.20.0 + psycopg2) | 5000 | 5000 | postgres (`ner_mlflow` DB), minio; backend-store `postgresql://ner:ner@postgres-test:5432/ner_mlflow`, artifact root `s3://ner-platform/mlflow/` (67-88) |
| `postgres-test` | `pgvector/pgvector:pg16` | 5432 | 55432 | named volume `postgres-data`; creds `ner:ner` (3-23) |
| `minio` | `minio/minio:latest` | 9000/9001 | 9000/9001 | volume `minio-data`; creds `minioadmin:minioadmin` (40-55) |
| `redis` | `redis:7-alpine` | 6379 | 6379 | (57-65) |
| `db-init` | root Dockerfile | — | — | one-shot `python -m src.gateway.ensure_mlflow_db && alembic upgrade head && python -m src.gateway.seed && python -m src.gateway.verify_schema` (25-38) |
| `otel-collector` / `tempo` / `loki` / `prometheus` / `grafana` | contrib 0.115.1 / tempo 2.6.1 / loki 3.3.2 / prom v3.1.0 / grafana 11.4.0 | 4317/4318/8889 / 3200 / 3100 / 9090 / 3000 | as listed | local-only stack; grafana anonymous admin, explicitly "laptop-scoped" (332-397) |

**Image inventory.** One fat Python image (root `Dockerfile`: `python:3.11-slim`, poetry, tesseract-ocr, copies `src/`, `alembic/`, `tenant_schema_ddl.py`; CMD = gateway uvicorn) serves 11 of the 14 application workloads by command override; one portal image; one MLflow image. The image carries torch + transformers + tesseract into every process — "one fat image for everything" (silo plan A14, severity Medium).

**Config surface.** `src/shared/config.py` — pydantic-settings, `NER_` prefix, ~50 settings. **Required-without-default (startup fails if absent):** `NER_JWT_SECRET` (line 38), `NER_TELEMETRY_PEPPER` (line 30), `NER_MINIO_ACCESS_KEY`/`NER_MINIO_SECRET_KEY` (46-47), `NER_OPENAI_API_KEY` (line 76). Defaults that must be overridden in prod: database URLs → localhost (8-9), redis (11), celery broker/backend → redis localhost (42-43), `NER_MINIO_ENDPOINT` localhost:9000 (45), `NER_MLFLOW_TRACKING_URI` localhost:5000 (58), all inter-service URLs localhost:PORT (64, 73-79). `.env` is loaded via `env_file=".env"` (line 192) but real environment variables take precedence — an injected secret works with **no code change** (silo plan A16 good news). Azure OpenAI settings exist but default to `None`/placeholders (81-84); `.env.example` keeps them commented (63-67). `NER_OTLP_ENDPOINT` empty disables telemetry export (config.py:25) — the collector must be reachable in-cluster.

**Health endpoints.** All 8 services expose `/health` (dependency-aware readiness, via `src/shared/readiness.py`) and `/metrics`. `/health/live` exists on gateway, chat_api, training_service, extraction_service, document_service, but is **missing on annotation_service, analytics_service, model_serving** (verified via grep of `src/*/main.py`) — silo plan A8. `model_serving` warms the cross-encoder reranker at startup (config.py:94-98 comment) — needs a startup probe strategy, silo plan A9. Celery workers run no HTTP server; their metrics are exported via OTLP to the collector (prometheus.yml:1-7 comment).

**Portal URL wiring (verified).** `src/portal/src/lib/api.ts` exposes seven build-time constants from `NEXT_PUBLIC_*` (lines 1-7); `src/portal/Dockerfile` declares them as `ARG`s (10-17); compose passes `http://gateway:8000` for server-side (`API_URL`) but `http://localhost:8000/8001/...` for the browser-facing constants (399-411); `src/portal/.env.local` also defaults to localhost with `NEXT_PUBLIC_DEMO_MODE=true`. **Result:** the browser talks to at least 6 service origins directly (document, annotation, training, model_serving, extraction via proxies in gateway only partially — gateway has `chat_proxy`, `analytics_proxy`, `extraction_proxy`; document/annotation/training/model_serving URLs point straight at each service). "A change of hostname later requires rebuilding the portal image" (deployment-plan §7a). This is the single highest-risk wiring fact in the deployment.

**Rate limiter (verified).** `src/chat_api/services/rate_limiter.py` — `SlidingWindowRateLimiter` backed by a process-local `defaultdict` (line 3, 41). Applied to chat_api internal + widget scopes only (chat.py:59, public.py:168). Effective limit = limit × replica count; resets on restart; `get_headers()` calls `check()` and consumes a slot (silo plan A11). This is a **code gap with deployment consequence** (see Risk R-004, NFR-NOISE-001).

**Celery.** Training worker consumes the default `celery` queue (training_service/main.py:66-67); extraction worker consumes `-Q extraction`. No queue-per-workload-class, no per-tenant fairness, no `acks_late`/idempotency evidence, `fine_tune_model` has `max_retries=0` (worker.py:198), no termination-grace handling (silo plan A13). Redis is the broker and result backend today (config defaults + compose).

**Secrets.** `.env` file (gitignored) exists in the working tree; `.env.example` documents dev-grade placeholders; compose hardcodes `ner:ner`, `minioadmin`, and the mlflow backend URL with credentials (docker-compose.yml:33,44-45,75). Production plan §7: `NER_OPENAI_API_KEY` has lived in plaintext and must be rotated on migration. Governance baseline `no-hardcoded-secrets` (non-overridable): none of these values may reach production.

**Kubernetes artifacts.** `deploy/k8s/mlflow/{deployment,service}.yaml` only. The Deployment references Secrets `mlflow-db` and `minio-credentials` (a naming/pattern precedent), hardcodes `AWS_DEFAULT_REGION: us-east-1`, artifact root `s3://ner-platform/mlflow/` and expects MinIO-style S3 (silo plan A17). No Terraform, no Helm, no ingress, no NetworkPolicy, no StorageClass anywhere in the repo (verified via glob).

**CI/CD.** The only workflow is `.github/workflows/telemetry-scan.yml` (PR-triggered + workflow_dispatch; bring up compose, drive one seeded flow, scan logs/span/metric labels for leaks; self-check with `--dry-run` first). No build, no push, no unit/integration/security gates in CI (telemetry-scan.yml:2-7 states CI was previously nonexistent). The technical design §6.1 pipeline (lint/typecheck/unit/integration/security/build/deploy) is a **design target, not implemented**.

**Documented-vs-implemented divergences (findings in their own right).**
- **F-1 Observability reversal.** Recovered silo plan A10 ("zero observability in src/") is false against current code — `src/shared/observability/` (init_observability, metrics.py, tracing.py, propagation.py, domain_metrics.py with 55 metric families and a written-out tenant-label allowlist), `/metrics` on every service, the compose otel stack, and the release-gate telemetry scan were built after that doc. The open observability question is now only the backend routing (decision DEC-009).
- **F-2 Broker contradiction.** PROJECT.md §2/§6 and ADR-006 mandate RabbitMQ; the implemented code and compose use Redis for Celery broker+backend; no RabbitMQ client code exists in the repo. Deploying RabbitMQ would require code work. Decision DEC-003.
- **F-3 Topology drift.** PROJECT.md §4 lists `training-orchestrator`, `model-registry`, and `analytics-chatbot` as separate services; the actual `src/` has `training_service`, no model-registry service (gateway hosts registry+promotion; gateway/api/v1/admin.py, dashboard.py), and `chat_api` + `analytics_service` as two services. The compose inventory above is the deployment truth.
- **F-4 RPO/RTO drift.** Technical design §3.4: RPO 5 min / RTO 30 min. Production plan §4.8 (newer): RPO 15 min / RTO 4 h. Decision DEC-010.
- **F-5 Hostname drift.** deployment-plan: `ner.hr.inapp.com`; silo plan §6: `nerp.inapp.com`; the PPTX and production plan name no hostname. Decision DEC-007.
- **F-6 Planning-doc deletions.** The three deployment planning documents and the PPTX are deleted in the working tree (uncommitted); recovered from HEAD. Q10 asks whether this is deliberate.
- **F-7 Cost figure drift within the production plan itself.** §1 says ~$1,300–1,700 infra + $200–900 LLM; §10 details ~$1,675 fixed + $215–940 LLM = ~$1,900–2,600 total. The detailed §10 table is used here as the primary figure.

## User Journeys and Business Workflows

Deployment-run journeys (the workflows this initiative must support, not the application's tenant workflows):

- **J-1 Deploy release.** Commit → CI build+scan → push SHA-tagged images → migrate Job (wait for success) → helm upgrade → rollout status → smoke test → promote. (Technical design §6.1; silo plan §4.5.)
- **J-2 Operate.** Uptime/queue-depth/disk/cert alerts; restore drill quarterly; on-call response; cost review. (deployment-plan §9; production plan §8.5.)
- **J-3 Rollback.** Image-tag redeploy or `helm rollback`; DB rollback only via backward-compatible `alembic downgrade -1` with pre-deploy dump (deployment-plan §9, technical design §6.4); model rollback via API `< 10 min` (ADR-003).
- **J-4 Onboard tenant.** System Admin provisions a tenant (schema from `tenant_template`, storage prefix, JWT scoping) — application-level journey that must keep working on AKS; no namespace/cell provisioning is in scope (silo plan B1 deferred).
- **J-5 End-to-end smoke.** Login → upload document → extraction → chat query with citations → analytics view (deployment-plan §8 step 12; RS-008).

## Functional Requirements

| ID | Requirement | Source | Stakeholder | Journey | Acceptance Criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FR-001 | Deploy all 8 FastAPI services, 2 Celery workers, portal and MLflow to AKS with per-service Deployment, Service, probes and resources | docker-compose.yml; silo plan A1; production plan §9 Phase 1 | Platform team | J-1 | All workloads Running with ready replicas after `helm upgrade`; `/health` green per service | Confirmed |
| FR-002 | Database initialization runs as an ordered one-shot Job before application rollout: ensure `ner_mlflow` DB → `alembic upgrade head` → verify schema; seeding policy per DEC-012 (recommended: migrate-only in prod) | docker-compose.yml:25-38; silo plan A6, Stage 2 item 1.8 | Platform team; Operations | J-1 | Job completes `Succeeded` before rollouts begin; no seed data in prod (if migrate-only chosen) | Confirmed |
| FR-003 | All secrets provisioned from a key-management source (Azure Key Vault per DEC-008) and injected as environment variables; no `.env` file and no compose dev credentials in any production artifact | governance `no-hardcoded-secrets`; production plan §7; config.py:192 (env precedence) | Security; Platform team | J-1 | Repository scan + runtime check show zero production hardcoded secrets; required-without-default vars present at pod start | Confirmed |
| FR-004 | TLS-terminated ingress for the portal and the API entry surface per the chosen exposure model (DEC-006) and hostname (DEC-007) | production plan §7 (TLS everywhere, Front Door + WAF); deployment-plan §5-6 | IT; Platform team | J-1, J-5 | HTTPS reachable at chosen hostname; HTTP→HTTPS redirect; WAF active if Front Door chosen | Confirmed |
| FR-005 | Per-service configuration delivered via ConfigMap/Secret mirroring the `NER_` settings surface (config.py) without code change | config.py model_config:192; silo plan A16 | Platform team | J-1 | Each service starts with its full effective config; diff against compose env verified per service | Confirmed |
| FR-006 | Health, readiness and startup probing on every workload: liveness → `/health/live`, readiness → `/health`; `startupProbe` on `model_serving`; `/health/live` added to annotation_service, analytics_service, model_serving | grep of src/*/main.py (A8); silo plan A9; technical design §7.5 | Platform team | J-1, J-2 | Kubelet probes wired; no CrashLoopBackOff during model_serving cold start; `kubectl describe pod` shows Ready | Confirmed |
| FR-007 | CI pipeline builds and pushes SHA-tagged images to the chosen registry (DEC-005) and retains the telemetry-scan release gate | silo plan A15, Stage 2 item 1.1; telemetry-scan.yml | Platform team | J-1 | Merge/PR produces images in registry with commit-SHA tag; telemetry scan still blocks on leak | Confirmed |
| FR-008 | GPU-capable training: Celery training worker runs on a GPU node pool with a CUDA-capable image, scale-to-zero per ADR-006 — **conditional on DEC-004** | ADR-006; production plan §2.4, §10 | Platform team | J-1 | Training job completes on GPU worker; pool scales to zero when idle (if GPU chosen) | Open – Blocking (DEC-004) |
| FR-009 | Observability pipeline from every workload to the chosen backends (DEC-009): OTLP export from services/workers, `/metrics` scraping, JSON logs to stdout | config.py:25; prometheus.yml; metric-contract.md | Platform team; Operations | J-2 | All service/worker signals reach backends; telemetry scan passes in cluster | Confirmed (backends pending) |
| FR-010 | Persistent storage for Postgres (if self-hosted, DEC-007) and object storage reachable as S3-compatible from MinIO-oriented code | docker-compose.yml volumes; config.py storage settings; production plan §5 data plane | Platform team | J-1, J-2 | Volume/object-store durability per DR targets; PVC or managed-service connectivity verified | Open – Blocking (DEC-007) |
| FR-011 | Graceful shutdown for long-running workers: termination grace period, Celery `acks_late`-style at-least-once behaviour audited and configured | silo plan A13; PROJECT.md at-least-once | Platform team | J-1, J-2 | Worker pods drain in-flight tasks on SIGTERM within grace; no lost training/extraction work on rollout | Recommended |
| FR-012 | Post-deploy smoke test: login → upload → extraction → chat → analytics against the deployed environment; failure blocks promotion/rolls back | technical design §6.1 (auto-rollback); deployment-plan §8 step 12 | QA; Platform team | J-1, J-5 | Smoke suite green in staging before prod promotion and post-prod deploy | Confirmed |
| FR-013 | Documented rollback procedure: `helm rollback` for image/config; `alembic downgrade -1` only backward-compatible; model rollback via API (`< 10 min`, ADR-003); pre-deploy DB dump | technical design §6.4; deployment-plan §9; ADR-003 | Operations | J-3 | Rollback runbook executed in staging; measured model rollback time recorded | Confirmed |
| FR-014 | Backups and recovery: Postgres PITR, object-store redundancy, quarterly restore drill | production plan §4.8; deployment-plan §9 | Operations | J-2 | Restore drill performed and logged; RPO/RTO of DEC-010 demonstrated | Confirmed |

## Reference Scenarios

Concrete worked examples from the source material. These are the proof points downstream (developer, QA) will exercise.

| ID | Actors | Trigger / Input | Expected Observable Outcome | Source |
| --- | --- | --- | --- | --- |
| RS-001 | CI (platform team) | Run `telemetry_scan.py --dry-run` with a planted leak | Scan exits non-zero before any stack is up, proving the checkers still detect a leak — a scan that silently stopped finding anything fails here | .github/workflows/telemetry-scan.yml:53-55 |
| RS-002 | Remote user | Open the portal from a laptop with an image built from committed `localhost` default URLs | UI loads; **every** API call fails in the browser (localhost resolves on the user's own machine). Documented anti-scenario proving the portal must be rebuilt with the public origin | deployment-plan §7a; silo plan A2; src/portal/src/lib/api.ts:1-7 |
| RS-003 | 30 concurrent chat users | Sustained conversations against staging/prod | p95 first-token < 2.5 s; p95 complete < 8 s; no 5xx | production plan §8.4 |
| RS-004 | 100 concurrent chat users | 5-minute burst | No 5xx; graceful HTTP 429s | production plan §8.4 |
| RS-005 | Batch extraction | 500 documents submitted for extraction | Completed in ≤ 30 min **while chat p95 stays within SLO** | production plan §8.4 |
| RS-006 | Tenant A at 10× quota | Noisy-neighbour test during load run | Tenant B's p95 does not move by more than 20% — the acceptance test of the whole multi-tenancy workstream; **would fail against current code (in-process rate limiter)** | production plan §8.4; Risk R-004 |
| RS-007 | Operations | Quarterly restore drill | Postgres restored from PITR to a scratch environment; object store verified; timing meets DEC-010 targets | production plan §4.8 |
| RS-008 | Tenant user | `POST /documents` upload of `invoice.pdf` | Returns `{ document_id, status: "uploaded" }`; async pipeline continues via broker | technical design §4.2 sequence diagram |

## Business Rules

| ID | Rule | Source | Status |
| --- | --- | --- | --- |
| BR-001 | Secret-class settings (`NER_JWT_SECRET`, `NER_TELEMETRY_PEPPER`, `NER_MINIO_ACCESS_KEY`, `NER_MINIO_SECRET_KEY`, `NER_OPENAI_API_KEY`) must come from the environment with **no default**; absent values fail startup | config.py:30,38,46-47,76 | Confirmed |
| BR-002 | No compose development credential (`ner:ner`, `minioadmin`) and no committed secret may appear in any production artifact | governance `no-hardcoded-secrets` (non-overridable); .env.example | Confirmed |
| BR-003 | Database migrations are backward-compatible only (expand-contract); old and new pods run simultaneously during rolling updates | silo plan §4.5; production plan §4.8 | Confirmed (from docs; must not be violated by design) |
| BR-004 | Migration must complete successfully before application rollout begins; never proceed past a failed migration | silo plan §4.5; compose db-init ordering | Confirmed |
| BR-005 | Workers run the image's code; no source-tree bind-mount in production | silo plan A4; deployment-plan §7c | Confirmed |
| BR-006 | No container port is published to the host/edge except the ingress entry; admin UIs (MLflow UI, MinIO console) are in-cluster-only or restricted | deployment-plan §4.2, §6, §10 | Confirmed |
| BR-007 | A deployment-topology change of this class requires an approved ADR before implementation | governance `boundary-decision-requires-adr` (non-overridable) | Mandated |
| BR-008 | Every process logs structured JSON to stdout, never document content/SQL/prompts/secrets; the telemetry scan remains a release gate | AGENTS.md invariant 4; telemetry-scan.yml | Mandated |
| BR-009 | New externally-reachable boundary (ingress to gateway/portal) requires a documented STRIDE threat model as part of its ADR | governance `threat-model-required-for-new-external-boundaries` (non-overridable) | Mandated |
| BR-010 | Generated SQL executes under the least-privilege read-only role; `sql_execution_role_enabled` role must be provisioned on the production database | config.py:109-117; governance `least-privilege-tool-and-db-credentials` | Mandated (provisioning task for design) |

## Data Requirements

- **PostgreSQL 16 + pgvector** — system of record for tenant schemas, metadata, annotations, entities, training jobs, MLflow backend. Schema-per-tenant isolation (ADR-001) with `tenant_<uuid>` schemas and `SET search_path` enforcement; `public` holds only migration tracking. **Managed (Azure Database for PostgreSQL Flexible Server) vs self-hosted on PVC is DEC-007.** Constraints: pgvector extension must be enabled; `ensure_mlflow_db` performs `CREATE DATABASE` (gateway/ensure_mlflow_db.py:26) — needs a privileged role on the managed server. Connection pooling via PgBouncer in transaction mode is documented as non-negotiable (PROJECT.md §6; production plan §4.2). Status: Confirmed (Postgres+pgvector mandated; hosting Open – Blocking).
- **Object storage (S3-compatible)** — documents, working copies, model artifacts, MLflow artifacts. Current MinIO endpoint + buckets `ner-platform` and `ner-platform-working` (config.py:48-57; working-copy expiry 1 day). Tenant isolation by prefix (`tenant-<uuid>/`, ADR-001). MLflow artifact root `s3://ner-platform/mlflow/`. **Target: Azure Blob Storage (S3-compatible API) is DEC-007's recommended replacement**; the existing K8s MLflow manifest's MinIO assumption (A17) must be updated. Status: Confirmed (object store required; provider Open – Blocking).
- **Redis 7** — cache, JWT blacklist/refresh, and (today) the Celery broker + result backend. Namespace convention `<tenant_id>:<entity>:<id>`, default TTL 5m (PROJECT.md §6). **Azure Cache for Redis vs self-hosted is part of DEC-007.** Status: Confirmed (Redis required; hosting Open – Blocking).
- **MLflow backend** — `ner_mlflow` database + artifact store; metrics/params live in MLflow, deliberately not duplicated in Prometheus (metric-contract.md:26-28). Status: Confirmed.
- **Retention** — telemetry logs: 30 days hot / 12 months cold (technical design §7.1); working copies: 1 day expiry (config.py:57); audit logs retained indefinitely (production plan §2.1). Status: Confirmed from docs; enforcement mapping is design work.
- **Backup/restore** — RPO/RTO per DEC-010 (15 min / 4 h recommended, quarterly drill). Status: Recommended; decision open.
- **Data classification** — unresolved for this run (Q2): client business documents vs HR/health/personal data changes the compliance surface materially (deployment-plan §10 notes documents may contain HR/personal data and that LLM egress needs legal/security sign-off). Status: Open – Blocking.

## Integration Requirements

- **LLM provider: OpenAI or Azure OpenAI** — chat, embeddings, SQL generation, domain classification, entity post-processing. Implemented today: direct OpenAI (`NER_OPENAI_API_KEY` required, config.py:76; `.env.example` Azure block commented). Documented intent: Azure OpenAI, `gpt-4o` + `gpt-4o-mini` (production plan §2.4 assumption; presenter deck §C1 "we call Azure OpenAI for chat and embeddings"). ADR-007 says "OpenAI GPT-4o-class with tenant-scoped API keys". **Decision DEC-002.** Status: Open – Blocking.
- **Hugging Face Hub** — runtime dependency, not one-time-only: `model_serving` loads the cross-encoder reranker at startup (config.py:92-98) and base models for serving/training (`dslim/bert-base-NER`, ADR-002). AKS egress to HF Hub must work (or artifacts vendored). Status: Confirmed; egress design owned by Architect.
- **LangSmith tracing** — optional, SDK-read, no `NER_` prefix (`.env.example:69-74`). Not a deployment blocker. Status: Deferred (owner: Platform team).
- **Prometheus / OTLP** — services expose `/metrics` (scraped), workers push OTLP to the collector (prometheus.yml:1-7). In-cluster collector must exist (config default). Status: Confirmed.
- **Keka / external data sources (S3/Azure Blob pull)** — documented ingestion-boundary work, not in the current runtime; not part of this deployment (document-ingestion-source-boundary.md). Status: Not Applicable to this run — future scope.
- **Egress allowlist** — OpenAI/Azure OpenAI endpoints, HF Hub, container registry, OS/NTP mirrors (deployment-plan §4.3). Status: Confirmed; exact list is design work.
- **Interface owners** — OpenAI/Microsoft (external), InApp IT (DNS/certs/egress), Microsoft Azure (managed services). Owners recorded in Dependency Register.

## UI/UX and Accessibility Requirements

This run has no UI design scope: the portal exists (`src/portal`, Next.js App Router) and the four-role UI is already built. Deployment-relevant UX constraints:
- **Portal URL wiring is a UX-critical deployment fact** — the browser resolves `NEXT_PUBLIC_*` constants compiled at build time (src/portal/src/lib/api.ts:1-7); a wrong origin produces the RS-002 failure. The chosen hostname/origin (DEC-006/007) drives a portal image rebuild per environment. Status: Confirmed (constraint), owner Architect for the wiring change.
- **Streaming chat** — `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` defaults enabled (chat/page.tsx:340); the ingress must not buffer responses and must allow long read timeouts on the chat path (deployment-plan §6: "no response buffering and a long read timeout on the chat path"). Status: Confirmed constraint.
- **Upload size** — document uploads need proxy body limits ~100 MB (deployment-plan §6). Status: Confirmed constraint.
- **Accessibility** — governance uiux controls apply only when a run has UI-facing work in scope; UI Design is absent for this run, so WCAG enforcement does not bind this run. Existing portal follows the repo's own conventions. Status: Not Applicable to this run.
- **System-administrator admin surfaces** (MLflow UI, MinIO console) must not be routed to the public edge (BR-006). Status: Confirmed.

## Security, Privacy and Compliance Requirements

| ID | Requirement | Driver (regulation / policy / risk) | Evidence Needed | Status |
| --- | --- | --- | --- | --- |
| SEC-001 | All secrets from Azure Key Vault (or chosen KMS, DEC-008) via workload identity; secrets injected as env vars; no `.env`, no compose dev creds, no committed secrets in images or manifests | governance `no-hardcoded-secrets` (non-overridable); production plan §7; BR-001/002 | Codespace/repo scan (gitleaks class), image inspection, runtime env check; telemetry scan findings zero | Confirmed |
| SEC-002 | Rotate `NER_OPENAI_API_KEY` (and all MinIO/JWT dev secrets) on migration since they have lived in plaintext | production plan §7 | Rotation record; old key revoked | Confirmed |
| SEC-003 | TLS in transit everywhere, including intra-cluster; WAF (Front Door) at the public edge if exposed | governance `encryption-in-transit-and-at-rest` (non-overridable); production plan §7 | Certificate inventory; ingress TLS config; WAF rules active | Confirmed |
| SEC-004 | Encryption at rest on all managed data services (Azure-managed keys; CMK deferred) | governance `encryption-in-transit-and-at-rest`; production plan §7 | Azure configuration evidence per service | Confirmed |
| SEC-005 | STRIDE threat model for the new externally-reachable boundary (ingress → gateway/portal, and any directly-exposed service) as part of the deployment ADR | governance `threat-model-required-for-new-external-boundaries` (non-overridable); BR-009 | Threat-model section in ADR; review record | Mandated |
| SEC-006 | No browser path bypasses gateway authorisation reachable from the edge; `/internal/v1/*` endpoints in-cluster-only with service auth; admin UIs unrouted | production plan §5.1.a ("currently unauthenticated", "must not be reachable from outside the cluster"); presenter deck "the only door in"; BR-006 | Ingress route table review; NetworkPolicy or equivalent; test from outside cluster | Confirmed (design-owned: DEC-018) |
| SEC-007 | Tenant isolation regression: automated test asserting cross-tenant access returns 403/404 for every endpoint, generated from OpenAPI | production plan §7; governance `tenant-isolation-independent-of-ai-output` | Generated suite green in CI (planned, not yet built — Phase 2 scope unless expanded) | Recommended |
| SEC-008 | One external penetration test before general availability (~$5-10k) | production plan §7 | Pentest report + remediation closure | Confirmed (scheduling dependency) |
| SEC-009 | CI security gates: Trivy image scan, gitleaks secret scan, dependency audit (pip-audit), SBOM per release build | governance overridable defaults (`dependency-vulnerability-scan-cadence`, `secret-scanning-tool`, `sbom-generation-cadence`); technical design §6.1; production plan §8.3 | CI logs showing each gate executed and passed on a release build | Mandated |
| SEC-010 | Secrets and sensitive data redacted from logs, spans and metric labels; telemetry-scan release gate retained in the build pipeline | governance `secrets-redacted-in-logs-and-traces`; AGENTS.md invariant 4; metric-contract.md | Release-gate scan green in cluster; label allowlist respected | Mandated |
| SEC-011 | Data classification and LLM-egress sign-off: confirm what data the platform will hold at go-live and that LLM egress of that data is sanctioned (legal/security) | deployment-plan §10 ("Legal and security must sign off"); Q2 | Signed sign-off or written decision | Open – Blocking (Q2) |
| SEC-012 | Least-privilege DB role for generated SQL (`ner_chat_sql`, config.py:116) provisioned on the production database; no DDL/DML grants | governance `least-privilege-tool-and-db-credentials`; production plan §7; BR-010 | Role provisioning evidence; SQL execution under that role in prod smoke | Mandated |

## Non-Functional Requirements

| ID | Metric | Target | Measurement Point | Workload / Condition | Validation Method | Environment | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NFR-CAPA-001 | Year-one scale basis | 10–15 tenants, ~200 users, ~50k chat msgs/mo, ~20k docs/mo (3× headroom in load targets) | Platform-wide | Assumed peak | Confirm with leadership | Staging + prod | Platform team / leadership | Recommended (assumption from production plan §2.4; confirm via Q10) |
| NFR-AVAIL-001 | Availability | 99.5% monthly, single region, **no external SLA** | Aggregated service uptime (gateway + portal + chat path) | Production load | Uptime monitoring over ≥1 month; beta exit criteria | Prod | Platform team | Recommended (production plan §4.8; confirm via Q10) |
| NFR-AVAIL-002 | Replica floor | ≥2 replicas for every stateless service; PDBs on all services | Deployment manifests | All times | Manifest review + chaos kill-pod test | Staging | Architect | Confirmed from docs (production plan §4.8) |
| NFR-AVAIL-003 | Zone resilience | Survive a single availability-zone failure | AKS across 3 zones; zone-redundant Postgres and Redis (if managed) | Zone-failure drill | Chaos/DR exercise | Staging | Architect | Confirmed from docs; hosting dependent on DEC-007 |
| NFR-PERF-001 | API latency | p95 < 200 ms | Gateway/API endpoints | 30 concurrent sessions baseline | k6/Locust | Staging | Platform team | Recommended (technical design §3.4) |
| NFR-PERF-002 | Inference latency | p95 < 500 ms per chunk | model_serving infer path | Extraction workload | Load suite | Staging | Platform team | Recommended (technical design §3.4; ADR-003 autoscale trigger) |
| NFR-PERF-003 | Chat latency | p95 < 10 s end-to-end (ADR-007 alert at >10 s); load target p95 complete < 8 s | Chat API | 30 concurrent conversations | k6 + golden flows | Staging | Platform team | Recommended (ADR-007 vs production plan §8.4 — reconcile in design) |
| NFR-PERF-004 | First token | p95 first-token < 2.5 s | Chat API streaming response | 30 concurrent conversations | Load suite | Staging | Platform team | Recommended (production plan §8.4) |
| NFR-PERF-005 | Burst behaviour | 100 concurrent for 5 min: no 5xx, graceful 429 | Gateway/chat | Peak burst | Load suite | Staging | Platform team | Recommended (production plan §8.4) |
| NFR-PERF-006 | Batch extraction | 500 docs ≤ 30 min while chat p95 holds SLO | Extraction pipeline + chat simultaneously | Mixed workload | Load suite | Staging | Platform team | Recommended (production plan §8.4) |
| NFR-PERF-007 | Extraction throughput | 100 docs/min per tenant | Extraction service | Sustained tenant load | Load suite | Staging | Platform team | Recommended (technical design §3.4) |
| NFR-SCAL-001 | Autoscaling | HPA 2–10 stateless replicas on CPU+p95; Celery 0–20 by queue depth (KEDA listed as future) | Cluster autoscaler/HPA metrics | Load ramp | Load suite + scale test | Staging | Architect | Recommended (production plan §4.7; KEDA is Phase 3) |
| NFR-DR-001 | RPO | **15 min** (production plan §4.8) vs **5 min** (technical design §3.4) — DECISION REQUIRED | Postgres PITR / object-store redundancy | Any time | Restore drill + PITR test | Staging/prod | Platform team / leadership | Open – Blocking (DEC-010) |
| NFR-DR-002 | RTO | **4 h** (production plan §4.8) vs **30 min** (technical design §3.4) — DECISION REQUIRED | Full recovery | After failure/DR drill | DR exercise | Staging/prod | Platform team / leadership | Open – Blocking (DEC-010) |
| NFR-DR-003 | Restore drill | Quarterly; an untested backup is not a backup | Postgres + object store | Scheduled drill | Drill log + timing record | Staging | Operations | Confirmed (production plan §4.8; FR-014) |
| NFR-OBS-001 | Signal coverage | All 8 services + 2 workers + portal emit structured JSON stdout, OTLP traces/metrics to a collector, `/metrics` scraped | Deployment | All times | Telemetry scan + backend dashboards | Staging + prod | Platform team | Confirmed (current code; backends per DEC-009) |
| NFR-OBS-002 | Alerting | SLO burn rate, queue backlog, quota, LLM error rate, cache thrash | Alert backend | Production | Alert firing tests | Prod | Operations | Recommended (production plan §5.1.d) |
| NFR-COST-001 | Infra cost | ~$1,675/mo fixed + ~$215–940/mo LLM at 10–15 tenants (total ~$1,900–2,600) | Azure cost export | Steady state | Monthly cost review | Prod | Leadership | Recommended (production plan §10; confirm via Q10) |
| NFR-COST-002 | Staging cost | ≤ ~$400/mo, optional scheduled shutdown | Azure cost export | Steady state | Monthly cost review | Staging | Leadership | Recommended (production plan §10; DEC-011) |
| NFR-DEP-001 | Deployment safety | Zero-downtime rolling updates; `helm rollback`; expand-contract migrations only | Deploy pipeline | Release | Deploy drill + rollback drill in staging | Staging | Platform team | Confirmed (production plan §4.8) |
| NFR-DEP-002 | Model rollback | < 10 min via model-registry API (ADR-003) | Model serving | Rollback event | Integration test | Staging | Platform team | Confirmed from docs (ADR-003) |
| NFR-DEP-003 | Pipeline gating | dev auto-deploy; staging manual via GitHub Environments; prod manual approval; smoke test fail → auto-rollback | CI/CD | Release | Gate review + drill | All | Platform team | Confirmed from docs (technical design §6.1) |
| NFR-SOAK-001 | Stability | 24 h soak at 50% load: no memory growth, no connection leaks | All services + workers | Soak run | Soak test | Staging | QA / Platform team | Recommended (production plan §8.4) |
| NFR-NOISE-001 | Noisy neighbour | One tenant at 10× quota must not move another tenant's p95 by >20% | Chat + extraction under contention | Contention test | Load suite acceptance test | Staging | Platform team | **Open – Blocking gap**: would fail today (in-process rate limiter, per-pod model cache, single FIFO queues — R-004); requires Phase-2 code; scope via Q1 |
| NFR-RES-001 | Resource sizing | requests/limits from measured peaks, ~1.5× observed; `model_serving` sized for 2 GB cache + reranker + runtime | Per-pod resource metrics | Under load | `kubectl top pod` + OOM history review | Staging | Architect | Recommended (silo plan §7) |

## Architecture-Driving Requirements and Constraints

What the architecture must satisfy — not a proposed architecture:

- **Constraint AD-1:** One fat image carries torch + transformers + tesseract into every process today; either the single image is kept (simplest, heaviest) or split into api/ml targets (silo plan A14). Decision owner: Architect; recommend the split (DEC-014).
- **Constraint AD-2:** Browser entry is multiple direct origins baked at build time (portal lib/api.ts + Dockerfile ARGs). Architecture must route the browser to a single consolidated origin (recommended: gateway-proxied path routing per deployment-plan §6 and silo plan change 0.1) or expose several services at the edge with their own TLS/CORS — the latter widens SEC-006's surface materially. Decision DEC-018.
- **Constraint AD-3:** `model_serving` cold-start (reranker warm-up) exceeds ordinary liveness thresholds; startup probe + generous `initialDelaySeconds` required; per-pod 2 GB model cache means memory pool and replica-count strategy are load-bearing (A9, A12).
- **Constraint AD-4:** Celery workers are HTTP-less; their metrics ride OTLP to a collector. The collector must be deployed in-cluster and reachable by worker pods, and `NER_OTLP_ENDPOINT` set on every workload (config.py:25).
- **Constraint AD-5:** db-init ordering (ensure_mlflow_db → alembic → verify) plus the seed/verify steps must become a migration Job distinct from seeding; `ensure_mlflow_db` needs a role able to `CREATE DATABASE` on the managed server (FR-002, BR-004).
- **Constraint AD-6:** `pydantic-settings` env precedence means secrets/config inject cleanly as env vars; a ConfigMap/Secret scheme can mirror the whole `NER_` surface without code change (FR-005).
- **Constraint AD-7:** Mutable-state services in the compose stack (postgres, redis, minio, mlflow backend) must either become Azure managed services or StatefulSets+PVC with operator-grade HA — running HA Postgres on K8s is a specialist job (silo plan A7). Decision DEC-007.
- **Constraint AD-8:** Alembic backward-compatibility is a hard release rule (BR-003); `dashboard.py`/admin surfaces read `public` and tenant schemas; cross-schema System Admin reporting uses explicit cross-schema queries (ADR-001).
- **Constraint AD-9:** The chat path streams and uploads are large — ingress must not buffer chat responses and must allow ~100 MB bodies (deployment-plan §6); these are per-route ingress settings.
- **Constraint AD-10:** Multi-tenancy is schema-per-tenant with `search_path` injection; nothing in the current code enforces per-tenant compute/cache/queue isolation (production plan §4; silo plan B2/B6/B7/B8) — deployment must not imply isolation the code does not provide. Any claim of tenant isolation at the platform layer (NetworkPolicy, node pools) must be documented as what it is (load/resource isolation) and verified adversarially (silo plan Stages 3–4).
- **Constraint AD-11:** The run ships under governance: deployment-topology change requires an ADR (BR-007); the ingress boundary requires a STRIDE threat model in that ADR (BR-009); secrets rules apply (BR-001/002).

## Technology Constraints, Preferences and Open Selections

| Area | Item | Tech Status | Driver / Rationale | Decision Owner |
| --- | --- | --- | --- | --- |
| Backend | Python 3.11-slim + poetry image (root Dockerfile) | Existing constraint | The shipped runtime; python:3.12 is documented in PROJECT.md §2 but the image is 3.11 | Architect |
| Backend | FastAPI + uvicorn on :8000 per service | Existing constraint | All 8 services; compose commands | Architect |
| Backend | Docker multi-target split (api vs ml) | Recommended by analysis | Fat image A14: slow pulls, oversized attack surface | Architect |
| Backend | Celery over Redis broker/backend | Existing constraint (contradicts documented RabbitMQ) | Implemented config.py:42-43 + compose; RabbitMQ mandated in docs only — DEC-003 | User (DEC-003) |
| Frontend | Next.js (node:20-alpine, standalone output) :3000 | Existing constraint | src/portal/Dockerfile | Architect |
| Frontend | Single-origin browser wiring (gateway proxying) | Recommended by analysis | AD-2, SEC-006; silo plan change 0.1/0.2 (code work) | User-scope (Q1) + Architect |
| Data stores | PostgreSQL 16 + pgvector | Mandated | PROJECT.md §2; ADR-001; compose postgres-test | — |
| Data stores | Azure Database for PostgreSQL Flexible Server (managed) | Recommended by analysis | Production plan §4.2 (zone-redundant HA, PITR, PgBouncer); silo plan A7; "buy managed" mitigation | User (DEC-007) |
| Data stores | PgBouncer (transaction mode) | Mandated (pattern) | PROJECT.md §6; production plan §4.2 | Architect |
| Data stores | Redis 7 | Existing constraint | JWT blacklist, cache, Celery broker | Architect |
| Data stores | Azure Cache for Redis | Recommended by analysis | Managed option under DEC-007 | User (DEC-007) |
| Data stores | MinIO → Azure Blob Storage (S3-compatible API) | Recommended by analysis | A17; production plan data plane "Blob"; MinIO is dev-only per PROJECT.md §2 | User (DEC-007) |
| Data stores | MLflow (self-hosted image, K8s manifests exist) | Existing constraint | deploy/k8s/mlflow/*; compose | Architect |
| Integration | OpenAI (direct) — implemented default | Existing constraint | config.py:76; .env.example | User (DEC-002) |
| Integration | Azure OpenAI (gpt-4o/gpt-4o-mini) | Recommended by analysis / documented intent | Production plan §2.4; presenter deck; config.py:81-84 | User (DEC-002) |
| Integration | Hugging Face Hub (base + reranker models) | Existing constraint | ADR-002; config.py:92 | Architect |
| Infrastructure | Azure + AKS, single region, shared multi-tenant | Confirmed (user ask + production plan §2.3.9) | The requirement itself | — |
| Infrastructure | Helm | Recommended by analysis (documented in 4 docs) | technical design §6.4 rollback; production plan Phase 1; silo plan §4.3 | Architect |
| Infrastructure | Terraform | Preferred | PROJECT.md §2; silo plan Stage 2 "Terraform/Bicep" | Architect (Bicep also named — open) |
| Infrastructure | GitHub Actions | Existing constraint | telemetry-scan.yml precedent; PROJECT.md §2 | — |
| Infrastructure | ACR (image registry) | Recommended by analysis | Co-located, AKS-integrated, private; A17 names GHCR for base image only | User (DEC-005) |
| Infrastructure | Azure Key Vault (+ workload identity; ESO or CSI driver) | Recommended by analysis (documented in technical design §6.3 and silo plan 1.9 — Vault also named in PROJECT.md §6) | Production plan §7; no-hardcoded-secrets | User (DEC-008) |
| Infrastructure | Azure Front Door + WAF at edge | Recommended by analysis | Production plan §7; deployment-plan §6 path-routing shape | User (DEC-006) |
| Infrastructure | Managed Prometheus + Log Analytics + Grafana (Azure Monitor) | Recommended by analysis | Production plan §5.1.d ("so a 3-person team is not also running an observability stack") | User (DEC-009) |
| Infrastructure | cert-manager / managed certificates | Recommended by analysis | TLS per DEC-006; deployment-plan §5.2 internal CA path | Architect |
| Third-party | Azure OpenAI TPM quota request | Existing constraint (procurement) | Production plan §11 — request early | Leadership |

## Environment and Infrastructure Requirements

- **Environment ladder** — `local` (compose) → `ci` (ephemeral) → `staging` (AKS, production-shaped, always-on question DEC-011) → `production` (technical design §6.2; production plan §8.2). Staging is currently missing and is a Phase-1 deliverable; without it there is nowhere to run load/chaos tests. Status: Confirmed from docs.
- **Region** — Azure, single region, **Central India** (production plan §2.4 assumption; silo plan Azure commands use `centralindia`). Confirm via Q2. Status: Assumed pending confirmation.
- **AKS shape (documented intent)** — 3 availability zones; node pools: `system` (2×D2s_v5), `app` (3×D4s_v5), `memory` (2×E4s_v5, taint `workload=memory` for model_serving), `training` (0–2×NC4as_T4_v3 spot, taint `workload=training`, scale-to-zero) — silo plan §2.1/§4.4. These are worked numbers from the planning docs, not an approved design. Status: Recommended.
- **Networking** — private cluster VNet; managed services on private endpoints (recommended); Front Door at edge (DEC-006) or internal-only exposure (Q7); no host ports published (BR-006). Status: Open subject to DEC-006/007.
- **DNS** — one hostname for portal + API path-routed (deployment-plan §6); name disputed between `ner.hr.inapp.com` and `nerp.inapp.com` (F-5, DEC-007); DNS lead time sits on the critical path (silo plan §6). Status: Open – Blocking.
- **Compute sizing** — requests/limits from measured peaks (NFR-RES-001); `model_serving` memory pool sized for 2 GB cache + reranker + torch (silo plan §4.3). Status: Recommended.
- **Secrets** — Key Vault + workload identity per DEC-008; ESO vs CSI driver vs direct env-injection is an Architect selection with both documented. Status: Open subject to DEC-008.
- **Backups** — Postgres PITR; Blob geo-redundancy + soft-delete/versioning; quarterly drill (FR-014, NFR-DR-003). Status: Confirmed from docs.

## Engineering and Quality Requirements

- **CI today:** only the telemetry-scan workflow (PR + dispatch). Everything else in technical design §6.1 (lint, typecheck, unit, integration, security scan, build, push, deploy) is unbuilt. Status: Confirmed gap.
- **Build** — SHA-tagged images; SBOM per release build (governance overridable; Mandated for this project's release builds). Container scanning via Trivy (production plan §8.3). Status: Mandated.
- **Secret scanning** — gitleaks with committed allowlist (governance overridable default). SAST: bandit/semgrep; dependency: pip-audit. Status: Mandated.
- **Test conventions** — pytest per service; Testcontainers for integration (PROJECT.md §9); coverage 70% changed lines / 85% control-layer (production plan §8.1) — targets for the code deltas this run may include (health-live endpoints, rate limiter if in scope). Status: Confirmed from docs.
- **Contract tests** — OpenAPI diffs across the 9 services, breaking change fails (production plan §8.1) — unbuilt; out of run scope unless Q1 expands. Status: Recommended.
- **Definition of Done for this run** — deployment smoke green, telemetry visible, security gates pass, rollback drill executed, restore drill logged (consolidated acceptance, Q10).

## Testing and Acceptance Strategy

- **Acceptance stakeholders** — platform team + run approver (Q10).
- **Smoke suite (post-deploy)** — health endpoints + login → upload → extraction → chat with citations → analytics (deployment-plan §8 step 12; FR-012; RS-008). Fail → block promotion / auto-rollback (technical design §6.1).
- **Tenant isolation test** — the generated OpenAPI cross-tenant suite is Phase-2 scope (SEC-007); the run's minimum is verifying the existing isolation tests still pass on AKS and that no new external boundary bypasses authz (SEC-006).
- **Load/chaos** — k6/Locust on staging incl. RS-003..006; chaos (kill pods, fail over Postgres, block LLM) — production plan §8.4-8.5; gated on staging existing (DEC-011) and scope (Q1).
- **Security validation** — CI gates (SEC-009), telemetry release-gate scan (SEC-010), external pentest pre-GA (SEC-008).
- **DR validation** — PITR restore drill (RS-007) per quarter; zone-failure exercise (NFR-AVAIL-003).
- **Entry/exit for promotion** — staging sign-off before prod (technical design §6.1); GA exit criteria per production plan §8.6 (99.5% over beta, p95 in SLO, zero isolation incidents, golden-set ≥80%).

## Delivery, Release and Deployment Requirements

- **CI/CD platform** — GitHub Actions (existing constraint); OIDC federation to ACR/AKS recommended over stored credentials. Status: Recommended; pipeline design owned by Architect.
- **Pipeline shape (documented intent)** — build/test/scan/deploy; dev auto on merge; staging manual via GitHub Environments; prod manual approval + smoke (technical design §6.1; FR-007, NFR-DEP-003).
- **Release flow** — git tag → SHA-tagged images → migration Job first, wait for success → `helm upgrade` → `rollout status` → smoke → promote (silo plan §4.5; FR-002/012).
- **Rollback** — `helm rollback`; `alembic downgrade -1` backward-compatible only; **data rollback limitation**: schema/data changes are the point where "rollback" stops — expand-contract migrations and pre-deploy DB dumps are the mitigations (BR-003; deployment-plan §9). Model rollback via API <10 min (NFR-DEP-002).
- **Helm vs raw manifests** — only 2 raw manifests exist; Helm is documented in 4 planning docs; recommend Helm with one chart, values per environment (silo plan §4.3 direction). Status: Recommended, owner Architect (DEC-013).
- **Environment promotions** — dev/staging/prod (DEC-011); staging always-on question.
- **Go-live** — staging sign-off → prod deploy → smoke → hypercare window (recommended); GA per production plan §8.6.

## Migration and Rollout Requirements

- **Current state** — a working application that has never been deployed; the compose DB holds dev/test data only (production plan §2 "never been deployed"). Rollout is the **first production deployment**, not a migration of live data. Status: Confirmed.
- **Data carry-over** — no tenant data migration assumed; validate that no compose-DB content is required in prod (ASM-003). If a working demo tenant is wanted in prod, that is seed data — governed by DEC-012 (recommended: migrate-only; no factory_boy seed in prod).
- **Coexistence/parallel run** — not applicable: nothing in production exists to run alongside. Cutover = first deploy.
- **Behaviour preservation** — the compose application's observable behaviour (all FRs of the app itself, API contracts, tenant lifecycle) must be preserved on AKS; the deployment must not change application semantics, only the runtime substrate (this is the "existing behaviour preserved" contract of the run; the must-elicit item is answered by the user's ask itself).
- **Post-migration verification** — full smoke + telemetry check + first restore drill.
- **Rollback feasibility** — trivial at image level (helm rollback); constrained at data level (BR-003).
- **Process note** — the recovered planning docs were deleted from the working tree mid-analysis; Q10 asks whether they remain the deployment intent (F-6).

## Operations and Support Requirements

- **Service/operational owner** — platform team (3 developers); on-call rota is a documented gap to solve before GA (production plan §8.6 note; risk R-001).
- **SLOs** — 99.5% internal, no external SLA (NFR-AVAIL-001); alerting on SLO burn, queue backlog, cert expiry, disk, GPU eviction (NFR-OBS-002; deployment-plan §9).
- **Monitoring** — uptime check on health endpoint; queue depth (earliest extraction-wedge signal); container restart counts; disk growth (deployment-plan §9).
- **Backups** — nightly DB dumps/PITR; object-store mirror/redundancy; weekly snapshot; quarterly restore drill (FR-014).
- **Cost** — monthly Azure cost review vs NFR-COST-001/002; reservations (30-40% compute saving) and scheduled staging shutdown as levers (production plan §10).
- **Capacity** — replica floors per NFR-AVAIL-002; measured resource sizing (NFR-RES-001); GPU spot pool eviction handled via checkpoint-resume per ADR-006 (note: checkpoint resume is documented, not verified in code — flag to Developer).
- **Certificate/secret renewal** — cert issuance path per DEC-006; Key Vault rotation including the migrated OpenAI key (SEC-002).
- **LLM cost attribution — gap warning:** the production plan's metering (`usage_events`, per-tenant LLM cost) is Phase-2 scope and does not exist in the current code; until it lands, per-tenant LLM cost is visible only via the existing `ner_llm_cost_usd_total` metric family (metric-contract.md:276). Status: recorded gap, owner Platform team.
- **Patch/vulnerability management** — monthly OS patch window; unattended security updates; image scan cadence in CI (deployment-plan §9; SEC-009).
- **Runbooks required before GA** — rollback, restore-from-backup, tenant onboarding, incident response (silo plan Stage 4; production plan §8.6).
- **End-of-life** — the compose runtime remains for local dev only; no decommissioning scope beyond that.

## Traceability Matrix

| Requirement ID | Source | Stakeholder / Owner | Acceptance Criterion | Validation Method | Status |
| --- | --- | --- | --- | --- | --- |
| FR-001 | compose; silo plan A1 | Platform team | All workloads Running + /health green | `kubectl` + smoke | Confirmed |
| FR-002 | compose db-init; silo plan A6 | Platform team | Job Succeeded before rollout; prod unseeded | Job status + DB check | Confirmed |
| FR-003 | governance; production plan §7 | Security, Platform team | No prod hardcoded secrets; required vars present | Scan + runtime check | Confirmed |
| FR-004 | production plan §7; deployment-plan §6 | IT, Platform team | HTTPS at hostname | TLS + WAF check | Confirmed (DEC-006/007) |
| FR-005 | config.py:192 | Platform team | Per-service config verified | Config diff per service | Confirmed |
| FR-006 | src/*/main.py; silo plan A8/A9 | Platform team | Probes wired; no crash on cold start | `kubectl describe` | Confirmed |
| FR-007 | silo plan A15; telemetry-scan.yml | Platform team | SHA-tagged images; gate retained | CI logs | Confirmed |
| FR-008 | ADR-006 | Platform team | GPU job completes; pool scales to zero | Job + pool metrics | Open – Blocking (DEC-004) |
| FR-009 | config.py:25; prometheus.yml | Platform team | All signals in backends | Dashboards + scan | Confirmed (DEC-009) |
| FR-010 | compose volumes; production plan §5 | Platform team | Storage durable per DEC-010 | Restore drill | Open – Blocking (DEC-007) |
| FR-011 | silo plan A13 | Platform team | No lost work on rollout | Rollout drill | Recommended |
| FR-012 | technical design §6.1 | QA, Platform team | Smoke green pre/post release | Smoke suite | Confirmed |
| FR-013 | technical design §6.4; ADR-003 | Operations | Rollback executed; model rollback timed | Drills | Confirmed |
| FR-014 | production plan §4.8 | Operations | Restore drill logged | Drill record | Confirmed |
| BR-001..010 | config.py; governance; AGENTS.md; silo plan | Platform team | Gates in CI + review | Scan + review | Confirmed / Mandated |
| SEC-001..012 | governance; production plan §7; BRs | Security | See SEC table | See SEC table | Mixed (Q2, DEC-008 open) |
| NFR-* | production plan; technical design; ADR-007 | Platform team / leadership | See NFR table | See NFR table | Mixed (DEC-010 open) |

## Decision Register

| ID | Decision Required | Context and Constraints | Options | Recommendation | Owner | Decision Deadline | Status | Downstream Impact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DEC-001 | Deployment scope for this run | Production plan is a 9-month, 5-phase program. Current code lacks Phase-1 items (Redis rate limiter is code; migrate/seed split is code; staging; backups) and all Phase-2+ items (SSO, metering, quota, LLM broker). User asked to "deploy the already-built platform" | (a) App as-is on AKS + managed Azure services, later phases as separate runs; (b) Production-plan Phase-1 scope (incl. Redis rate limiter, migrate/seed split, staging, restore drill, observability backends); (c) Go-live deferred until Phase-3 (alpha) scope | (a) as the literal reading of the ask, with (b) items that are configuration/minimal-code included (probes, portal wiring, migrate split, staging); rate-limiter/queue-fairness as a named follow-up since NFR-NOISE-001 otherwise fails | User (leadership) | Before design gate | **Open – Blocking** | Everything downstream: which code deltas are in scope; acceptance definition (Q10) |
| DEC-002 | LLM provider: OpenAI vs Azure OpenAI | Implemented default: OpenAI (config.py:76 required key). Documented intent: Azure OpenAI gpt-4o/gpt-4o-mini (production plan §2.4; presenter deck; config.py:81-84 ready). ADR-007 says OpenAI. `.env.example` keeps Azure commented | (a) OpenAI direct as today; (b) Azure OpenAI (config-only switch — endpoint, API version, 2 deployment names, key); (c) both via config | (b) Azure OpenAI — matches stated intent and keeps data in-subscription/region (production plan §2.4 rationale) | User | Before design gate | **Open – Blocking** | Secrets surface (which key), egress allowlist, networking (private endpoints), cost line, TPM quota request lead time |
| DEC-003 | Message broker: Redis (implemented) vs RabbitMQ (documented) | PROJECT.md §2/§6 and ADR-006 mandate RabbitMQ; the code, compose and config use Redis for Celery broker+backend; no RabbitMQ client code exists anywhere | (a) Redis for this deployment — zero code change, ships today's behaviour; (b) RabbitMQ (Azure managed or self-hosted) with the required code work scheduled before go-live | (a) ship Redis — the implemented behaviour is the requirement; RabbitMQ becomes an ADR-tracked code change with its own run. Record contradiction openly (F-2) | User | Before design gate | **Open – Blocking** | Broker hosting (managed vs pod), queue semantics, event-schema debt, CVEs on redis-as-broker |
| DEC-004 | GPU training: image + node pool vs CPU-only vs off-platform | ADR-006 mandates GPU node pools, scale-to-zero, checkpoint resume. Only CPU image exists (`python:3.11-slim`, `NER_TRAINING_DEVICE=cpu`); no CUDA Dockerfile. Production plan: spot T4 ~$30/mo; CPU fallback = 4-8 h/job | (a) CUDA image + GPU spot node pool (NC4as_T4_v3, scale-to-zero) per ADR-006; (b) CPU-only go-live, GPU later; (c) training off-cluster (Azure ML / on-demand VM) | (a) — ADR-006 compliance + production plan's explicit recommendation ("approve the GPU line"); requires image work + pool provisioning | User (+ GPU-line approver) | Before design gate | **Open – Blocking** | New Dockerfile target, node pool + taint/toleration, worker deployment, DR/spot-eviction handling, cost line |
| DEC-005 | Container registry | No registry reference in repo; only GHCR appears as the mlflow base image (deploy/k8s/mlflow/deployment.yaml:22). CI build/push is unbuilt | (a) ACR (co-located, AKS-attached, private); (b) GHCR (already referenced, public by default); (c) both (ACR primary, GHCR mirror) | (a) ACR — egress-free pulls in-region, kubelet integration, no proxy issues | User | Before design gate | **Open – Blocking** | CI build step, image pull auth, cost line, SBOM/signing target |
| DEC-006 | Ingress/TLS + public exposure model | Only ClusterIP exists; nothing for gateway:8000 / portal:3000. Production plan §7: "TLS everywhere including intra-cluster, Front Door plus WAF at the edge." Deployment plan: internal-only (VPN) deployment. Portal wiring bakes origins at build time (AD-2) | (a) Internet-facing SaaS: Front Door + WAF → AKS ingress (AGIC or nginx) + managed certs; (b) private/internal only (VNet + VPN, internal CA certs) — deployment-plan §4-5 shape; (c) hybrid: private now, Front Door later | (a) for a client-serving SaaS per production plan; (b) if go-live is internal-only; geographic/legal ruling pending Q2 | User + IT | Before design gate | **Open – Blocking** | DNS, cert path, SEC-005 threat model, CORS/portal rebuild, WAF cost |
| DEC-007 | Hostname(s) | `ner.hr.inapp.com` (deployment-plan) vs `nerp.inapp.com` (silo plan §6) vs none named (production plan). DNS request has real lead time and sits on the critical path | Pick one primary hostname (+ staging subdomain); path-routing single-origin recommended over per-service subdomains | Path-routed single origin; staging subdomain; confirm which name | User + IT | Before design gate | **Open – Blocking** | Portal build args, cert SANs, ingress routes, CORS |
| DEC-008 | Secrets provisioning | PROJECT.md §6: HashiCorp Vault + ESO. Technical design §6.3: ESO → Azure Key Vault. Silo plan item 1.9: Key Vault CSI driver. Production plan §7: "Key Vault with workload identity". Internal doc conflict: Vault vs Key Vault | (a) Azure Key Vault + workload identity (+ ESO and/or CSI); (b) Vault server (self-hosted HA on AKS or HCP) + ESO; (c) plain K8s Secrets (rejected: governance) | (a) — no extra server to operate, matches 3 of 4 docs and "buy managed services" mitigation; Vault adds an HA operator burden | User | Before design gate | **Open – Blocking** | Secret-object mechanism (ESO vs CSI), rotation, workload identity, no-hardcoded-secrets evidence |
| DEC-009 | Observability backends | Code already emits OTLP + /metrics + JSON logs (F-1 — silo plan A10 outdated). Compose stack (otel/tempo/loki/prometheus/grafana) is laptop-scoped. Production plan §5.1.d: Azure Monitor + Log Analytics ("so a 3-person team is not also running an observability stack") | (a) Azure Monitor managed: managed Prometheus + Log Analytics + managed Grafana; (b) self-hosted Prometheus/Loki/Tempo/Grafana in-cluster (compose pattern); (c) hybrid (managed Prometheus + self-hosted Tempo for traces) | (a) — matches the operating-team constraint; the otel-collector indirection means routing is a config change (design Dec. 1 of the observability work) | User | Before design gate | **Open – Blocking** | Collector config, retention costs, dashboards/alerting surface, cost line |
| DEC-010 | Availability/DR targets | Technical design §3.4: RPO 5 min / RTO 30 min. Production plan §4.8 (newer): RPO 15 min / RTO 4 h, quarterly drill, 99.5% no-SLA. ADR-001: RPO 5 / RTO 30 | (a) Production-plan set (15 min / 4 h / 99.5%); (b) technical-design set (5 min / 30 min — costlier: more frequent WAL shipping/DR rigour) | (a) — newer doc, single region, internal no-SLA posture; (b) if client contracts require | User | Before design gate | **Open – Blocking** | Backups design, managed-PG tier/HA choice, restore-drill targets, NFR-DR-001/002 |
| DEC-011 | Environment ladder + staging always-on | technical design §6.2 defines dev/staging/prod; production plan says staging ~$400/mo, "recommended, and cheaper than testing in production", with scheduled-shutdown option | (a) dev+staging+prod, staging always-on; (b) staging with scheduled shutdown; (c) dev+prod only | (a) — staging is where load/chaos/DR drills run; cost ceiling respected | User | Phase 1 planning | Open – Non-blocking (owner: user) | Where testing happens, cost line, promotion gates |
| DEC-012 | db-init split + seed policy | db-init runs ensure_mlflow_db + alembic + **seed** + verify in one shot (compose:29). Seeding factory_boy demo data into prod is unacceptable (silo plan A6) | (a) migrate-only Job in prod, seed only dev/staging; (b) seed in prod (rejected — demo data in tenant DBs) | (a) — migrate Job per FR-002; seed job instance for non-prod | Architect + Platform team | Design | Open – Non-blocking (recommendation made) | db-init Job design, prod data hygiene |
| DEC-013 | Helm vs raw manifests | Only 2 raw manifests exist. Helm documented across technical design/§6.4, production plan, silo plan, ADR-001 (rollback vocabulary) | (a) Helm (one chart, values per env); (b) raw manifests + kustomize | (a) — rollback/smoke vocabulary already assumes it | Architect | Design | Open – Non-blocking | Everything in delivery |
| DEC-014 | Image strategy | One fat image (torch+transformers+tesseract) for 11 workloads (A14) | (a) keep one image; (b) split api/ml targets | (b) — smaller API pods, faster pulls, smaller attack surface; note: MLflow manifest precedent exists | Architect | Design | Open – Non-blocking | Dockerfile work, registry tags, pod size |
| DEC-015 | Browser entry consolidation | Browser calls ≥6 origins directly; URLs compiled in; SEC-006 forbids bypass of authz at the edge | (a) gateway proxies all `/api/*` and portal rewritten to relative paths (silo plan changes 0.1/0.2 — code); (b) all services exposed at edge with own TLS/CORS (wider surface) | (a) — "one door in"; requires code change, so scope-gated by Q1/DEC-001 | Architect + Platform team | Design | Open – Blocking for SEC-006 posture | Portal Dockerfile rewrite, ingress routes, CORS, threat model (SEC-005) |
| DEC-016 | Budget ceiling | Production plan §10: ~$1,900–2,600/mo at 10–15 tenants; GPU line ~$30/mo; staging ~$400/mo | (a) approve plan figures; (b) reduce (drop GPU, no staging); (c) expand | (a) — includes GPU line (DEC-004) and always-on staging (DEC-011) | Leadership | Before Phase 1 | Open – Non-blocking | Everything cost-shaped |
| DEC-017 | CI/CD tooling | GitHub Actions is the only CI precedent; build/push/deploy pipeline unbuilt | (a) GitHub Actions + OIDC federation to ACR/AKS; (b) other runner | (a) — existing constraint, no new platform | Architect | Design | Open – Non-blocking | Pipeline delivery (FR-007) |
| DEC-018 | RabbitMQ/eventing follow-up | See DEC-003 — recorded separately so the contradiction stays visible after the broker decision | Track RabbitMQ as an ADR change post-deployment | — | Platform team | Post-go-live | Deferred (owner: Platform team) | Event-schema debt |
| DEC-019 | GPU training implementation detail (if DEC-004 = a) | CUDA base image, spot pool eviction, checkpoint resume (ADR-006) | — | — | Architect | Design | Deferred pending DEC-004 | FR-008 |

## Assumption Register

| ID | Assumption | Reason | Validation Owner | Validation Deadline | Impact if Incorrect |
| --- | --- | --- | --- | --- | --- |
| ASM-001 | `Codebase: greenfield` (run config) means the AKS target is greenfield; the compose application is the existing behaviour to preserve | Dispatch + verified runtime inventory | Orchestrator (recorded) | Analysis gate | Document misclassified; brownfield discipline (preservation contract) still applied here — no impact to content |
| ASM-002 | The recovered planning docs (production plan, deployment plan, silo plan, PPTX) remain the deployment intent despite working-tree deletions | All three .md files are referenced by each other and by AGENTS-visible docs; deletions are uncommitted | User (Q10) | Before design gate | Intent retired → this baseline overstates the plan; scope/questions re-anchored to the ask only |
| ASM-003 | The production database starts empty; no migration of compose dev data | "A working application that has never been deployed" (production plan §2); compose DB is dev-only | User (Q10/acceptance) | Go-live | Existing tenants/data to carry → migration workstream appears |
| ASM-004 | Year-one scale: 10–15 tenants, ~200 users, ~50k msgs/mo, ~20k docs/mo | Production plan §2.4 | Leadership | Before load testing | NFR targets re-derived from real numbers |
| ASM-005 | Single Azure region: Central India | Production plan §2.4 assumption | User (Q2) | Before design gate | Region/sovereignty constraints change everything downstream |
| ASM-006 | Azure OpenAI assumed as provider | Production plan §2.4 | User (DEC-002) | Before design gate | Config-only reversal (per production plan §2.4) but secrets/network change |
| ASM-007 | GPU spot line (~$30/mo) approved | Production plan §10 recommendation | User (DEC-004) | Before design gate | CPU-only training (4–8 h/job) or scope reduction |
| ASM-008 | No compliance certification at go-live; SOC 2 / ISO 27001 controls respected, not certified | Production plan §2.4 | Security / leadership | Go-live | Certification required → SEC table grows, timeline shifts |
| ASM-009 | Staging always-on (~$400/mo) | Production plan §10 recommendation | User (DEC-011) | Phase 1 | No safe place for load/chaos/DR tests |
| ASM-010 | ~$1,900–2,600/mo cost envelope accepted | Production plan §10 | Leadership (DEC-016) | Phase 1 | Redesign toward cheaper posture |
| ASM-011 | The observability code present in the repo satisfies the production plan's Phase-1 observability items (structured logs, OTel, Prometheus) — only backends are open | F-1 verification (src/shared/observability, /metrics, telemetry scan) | Platform team | Design gate | Observability code work resurfaces as scope |

## Dependency Register

| ID | Dependency | Type | Owner | Needed By | Status | Impact if Unavailable |
| --- | --- | --- | --- | --- | --- | --- |
| DEP-001 | Azure subscription + Central India region confirmed | External | Leadership | Design start | Open | Nothing can be provisioned |
| DEP-002 | Azure OpenAI TPM quota / deployment names (if DEC-002=b) | External | Leadership / Microsoft | Phase 1 | Open | 429s platform-wide; lead times are real (production plan §11) |
| DEP-003 | DNS zone + hostname approval (`ner.hr.inapp.com` or `nerp.inapp.com`) | External (IT) | IT | Phase 1 | Open | On the critical path (silo plan §6); ingress cannot finish |
| DEP-004 | Certificate issuance path (internal CA vs ACME DNS-01 vs managed) | External (IT) | IT | Phase 1 | Open | TLS cannot be provisioned |
| DEP-005 | Hugging Face Hub reachability from AKS (reranker + base models) | External | Platform team | Phase 1 | Confirmed dependency | model_serving cold start fails; training/serving broken until vendored |
| DEP-006 | LLM egress allowlist on any corporate proxy/firewall | External (IT) | IT | Phase 1 | Open | Chat/embeddings fail (deployment-plan §4.3) |
| DEP-007 | External penetration test vendor (~$5–10k) | External | Leadership | Pre-GA | Open | GA blocked (SEC-008) |
| DEP-008 | Optional part-time DevOps contractor | External | Leadership | Phase 1 | Optional | Mitigation for R-001 only |
| DEP-009 | GitHub Actions OIDC federation to Azure | Internal | Platform team | CI build | Open | Static credentials or manual push |
| DEP-010 | Azure OpenAI/OpenAI account holding the migrated key | External | Platform team | Phase 1 | Open | Rotation (SEC-002) cannot complete |

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R-001 | 3 junior developers doing Azure+K8s+OTel+security simultaneously; no DevOps/QA/security | High | High — dominant risk (production plan §11) | Buy managed services everywhere; phase strictly; automated CI gates; external pentest; consider part-time DevOps (DEP-008) | Leadership | Open |
| R-002 | Scope confusion: "deploy the app" mistaken for production-plan GA | Medium | High | Q1/Q10 settle scope and acceptance explicitly; this document's In/Out sections cite them | User | Open (Q1/Q10) |
| R-003 | GPU training absent → 4–8 h CPU jobs bottleneck the annotate→train→evaluate loop | Medium | Medium | DEC-004; approve GPU line ($30/mo); checkpoint resume | User | Open |
| R-004 | In-process rate limiter: effective limit × replicas, resets on restart, no protection for Postgres/OpenAI | High (current code) | High — NFR-NOISE-001 and RS-006 fail; 429 contract incorrect at scale | Redis sliding-window limiter (Phase-1/2 code); interim: single-replica chat_api or conservative limits; record as documented gap | Platform team | Open |
| R-005 | Portal shipped with baked-in localhost URLs → RS-002 broken-in-browser failure | Medium (high if missed) | High | Portal origin rebuild per environment; smoke includes a browser-side check; DEC-015 | Platform team | Open |
| R-006 | Self-hosted Postgres chosen and run without HA expertise | Medium | High | DEC-007 managed-first; Flexible Server zone-redundant + PgBouncer | Architect | Open |
| R-007 | Secrets from `.env`/compose creds leak into prod artifacts | Medium | High | DEC-008; rotation (SEC-002); gitleaks gate; no-hardcoded-secrets | Platform team | Open |
| R-008 | Guessed resource limits → model_serving OOMKilled or idle cost | Medium | Medium | NFR-RES-001 measured sizing; startup probe; memory pool | Architect | Open |
| R-009 | Migration/seed ordering error (seed into prod, or rollouts before migration) | Medium | High | FR-002 Job-first ordering; DEC-012 migrate-only; BR-004 | Platform team | Open |
| R-010 | Azure OpenAI TPM quota exhaustion | Medium | Medium | Request quota early (DEP-002); interactive/batch separation (Phase 3); circuit breaker | Leadership | Open |
| R-011 | Telemetry not visible after deploy (collector unreachable; OTLP empty disables export) | Medium | Medium | FR-009; in-cluster collector; telemetry scan run in cluster; NFR-OBS-001 | Platform team | Open |
| R-012 | Planning-doc deletions signal a change of intent that is not communicated | Low | Medium | Q10; ASM-002 | User | Open |
| R-013 | LLM cost overrun with no per-tenant metering in current code | Medium | Medium | Existing `ner_llm_cost_usd_total` metric; Phase-2 metering; monthly cost review | Leadership | Open |
| R-014 | No staging → load/chaos/DR testing impossible pre-GA | Medium | High | DEC-011 staging always-on (~$400/mo) | User | Open |
| R-015 | Ingress boundary without threat model → governance violation | Low | Medium | BR-009/SEC-005: STRIDE in the deployment ADR | Architect | Open |
| R-016 | GPU spot eviction loses long training runs (no verified checkpoint resume) | Medium | Medium | ADR-006 checkpoint resume — flag to Developer for verification before DEC-004=a | Platform team | Open |

## Open Questions

### Blocking
Each blocks the Design stage for the workstream named:

- Q1 (DEC-001) — run scope — blocks all workstreams.
- Q2 (SEC-011, ASM-005) — data classification/residency + region — blocks Security and Infrastructure.
- Q3 (DEC-003) — broker — blocks Architecture + Data.
- Q4 (DEC-002) — LLM provider — blocks Security (secrets), Integration, DevOps.
- Q5 (DEC-004) — GPU — blocks Infrastructure + Development (image).
- Q6 (DEC-005) — registry — blocks DevOps (CI build).
- Q7 (DEC-006/007/015) — exposure model + hostname + browser entry — blocks Infrastructure + Security (ingress/TLS/threat model).
- Q8 (DEC-009) — observability backends — blocks DevOps + Operations.
- Q9 (DEC-010) — availability/DR numbers — blocks Infrastructure + Operations.
- Q10 (approver, acceptance, staging, planning-doc deletions) — blocks Go-live definition and the Analysis gate closure.

### Non-blocking
- Seed policy (DEC-012) — recommended migrate-only in prod; owner Architect + Platform team.
- Staging always-on (DEC-011) — folded into Q10; recommended yes.
- Helm vs manifests (DEC-013) — owner Architect; recommended Helm.
- Image split (DEC-014) — owner Architect; recommended split.
- Cost ceiling (DEC-016) — recommended production-plan figures; owner Leadership.
- RabbitMQ follow-up (DEC-018) — deferred post-go-live; owner Platform team.
- Resource sizing numbers (NFR-RES-001) — to be measured in staging, not guessed; owner Architect.

## Readiness Assessment

**Overall rating: Conditionally Ready.**

Architecture can begin against the recorded assumptions — the outcome, the platform inventory, the config surface, the wiring constraints and most NFRs are established from repository evidence with file:line citations, and every remaining gap has a named owner. However, the 10 blocking questions (2 batches) must be resolved before design on the affected workstreams: they are deployment-scope decisions that only the user/leadership can make, and the skill's floor rules (data classification, acceptance, approver) are among them, which caps the rating at Conditionally Ready by rule.

| Workstream | Ready / Conditional / Blocked | Evidence | Remaining gap | Owner |
| --- | --- | --- | --- | --- |
| Product and business | Conditional | Goal and cost envelope clear (ask + production plan §10) | Scope of this run (Q1), acceptance + approver (Q10) | User / leadership |
| UX | Ready | Portal exists; only URL wiring + streaming/upload proxy constraints (AD-2, deployment-plan §6) | Portal origin rebuild per environment (DEC-007/015, design-owned) | Architect |
| Architecture | Conditional | AD-1..AD-11 constraints documented; topology inventory verified | Broker (Q3), LLM provider (Q4), GPU (Q5), boker-entry consolidation (DEC-015) | User + Architect |
| Data | Conditional | Data requirements + retention/DR recorded; ADR-001 schema-per-tenant | Managed vs self-hosted (DEC-007), RPO/RTO set (DEC-010) | User + Architect |
| Security | Conditional | SEC-001..012 with drivers and evidence; governance floor applied | Data classification/Q2, provider (Q4), exposure model (Q7), Key Vault (DEC-008) | User + Security |
| Development | Conditional | Cluster-readiness gaps enumerated (probes on 3 services, startup probe, portal wiring; rate limiter/graceful shutdown flagged) | Scope of code deltas (Q1), GPU image (Q5) | Platform team |
| QA | Conditional | Smoke criteria, RS-003..006 scenarios, load/chaos programme documented | Staging existence (Q10/DEC-011), scope (Q1) | Platform team |
| Infrastructure and DevOps | Blocked | No registry, ingress, persistence, secrets, observability, CI/CD decisions made | Q3, Q5, Q6, Q7, Q8, Q9 (all design-blocking) | User + Architect |
| Migration | Ready | First deploy is net-new; no data migration (production plan §2) | ASM-003 validation; seed policy (DEC-012) | Platform team |
| Operations | Conditional | Monitoring/backup/runbook requirements documented | On-call rota, runbooks before GA, observability backends (Q8), DR numbers (Q9) | Platform team |

## Delivery Workstreams and Todo List

High-level per workstream — task breakdown is Architect's and Developer's work.

- **Business analysis** — resolve Q1/Q10 (scope, acceptance, approver); confirm region/classification (Q2); cost sign-off (DEC-016); planning-doc deletions verdict.
- **Architecture** — deployment ADR incl. STRIDE threat model for the ingress boundary (BR-007/009); broker (Q3), provider (Q4), GPU (Q5), registry (Q6), exposure+hostname+entry (Q7), observability backends (Q8), DR numbers (Q9) → locked decisions; Helm chart + values-per-environment (DEC-013); image split (DEC-014); node pool model; NetworkPolicy posture; secret mechanism selection (ESO/CSI).
- **Security** — Key Vault + workload identity design (DEC-008); rotation of dev secrets incl. OpenAI key (SEC-002); CI security gates (SEC-009); threat model; encryption evidence; pentest scheduling (SEC-008).
- **Data** — managed Postgres/Redis/Blob vs PVC (DEC-007); PgBouncer + statement timeouts; `ner_chat_sql` read-only role provisioning (BR-010); migration Job (FR-002); RPO/RTO per DEC-010; PITR + restore drill (FR-014).
- **Development** — cluster-readiness deltas: `/health/live` on 3 services, startup probe (FR-006), portal origin rewiring (DEC-015), migration/seed split (DEC-012), worker bind-mount removal (FR-001 corollary); in-scope code from Q1 (rate limiter if approved); graceful shutdown (FR-011); CUDA image if GPU approved (FR-008).
- **Testing** — smoke suite (FR-012); telemetry release gate in cluster (RS-001); load criteria RS-003..006 when staging lands; DR drill (RS-007); isolation verification on AKS (SEC-006).
- **DevOps** — build/push pipeline with SHA tags + OIDC (FR-007, DEC-017); promotion gates dev→staging→prod (NFR-DEP-003); rollback procedures (FR-013); observability backends per DEC-009; cost monitoring vs NFR-COST-001/002.
- **Migration** — first-deploy cutover; empty-prod validation (ASM-003); post-deploy verification suite.
- **Operations** — runbooks (rollback, restore, onboarding, incident); on-call rota before GA; backup schedule + quarterly drill; cert/secret renewal calendar; queue-depth/disk/uptime alerts.

## Handoff Contract

- **Product / BA** — Business goals and success measures; scope In/Out/Future; user journeys J-1..J-5; acceptance criteria in FRs; RS-001..008 proof points; the 10 blocking questions for the human.
- **UX** — portal wiring constraint (build-time URLs, RS-002), streaming/upload proxy requirements, admin-surface exposure rule (BR-006); no UI design scope in this run.
- **Architect** — Architecture-driving constraints AD-1..AD-11; full config surface (config.py §Current State); Technology Constraints table with Tech Status; DEC-001..019 with recommendations and owners; node-pool/resource guidance (NFR-RES-001); ingress/streaming/upload constraints; threat-model requirement (SEC-005).
- **Security** — SEC-001..012 with drivers and evidence needs; data-classification question Q2; secrets rotation list (SEC-002); governance floor citations; pentest dependency (DEP-007).
- **Developer** — confirmed behaviour (compose inventory is the truth), cluster-readiness gaps list (probes, startup, portal wiring, worker mounts, migrate/seed, graceful shutdown), BR-001..010 rules, FR-001..014 acceptance criteria, metric/label contract for the new-wiring code.
- **QA** — traceable FRs and NFRs, RS-001..008 scenarios to exercise, smoke suite + load/chaos programme + staging gating, telemetry release-gate check, restore drill acceptance.
- **DevOps** — environment ladder, CI/CD + registry + Helm + observability decisions (open: blocked on Q3/Q5/Q6/Q7/Q8/Q9), promotion gates, rollback mechanics incl. data-rollback limitation (BR-003), cost monitoring.
- **Operations** — NFR-AVAIL-001 SLO posture, alerting list (NFR-OBS-002), backup/restore + quarterly drill, runbook list, on-call gap, cert/secret renewal, cost review cadence.