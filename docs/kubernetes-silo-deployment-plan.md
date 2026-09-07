# Kubernetes Deployment Plan — Silo (Per-Tenant Cell) Model

**Audience:** platform team (3 developers, no prior Kubernetes experience)
**Status:** working document
**Companion to:** [production-plan.md](production-plan.md) — this document supersedes locked decision #9 ("shared multi-tenant") with a hybrid pooled + silo model.

---

## 0. Vocabulary you need before reading the rest

| Term | One-line meaning |
|---|---|
| **Image** | A packaged, immutable filesystem + command. You already build these (`Dockerfile`). |
| **Registry** | Where images live so a cluster can pull them. On Azure: ACR. |
| **Cluster** | A set of machines Kubernetes manages as one computer. |
| **Node** | One VM in the cluster. |
| **Node pool** | A group of identical nodes, labelled (e.g. `workload=training`). |
| **Pod** | The smallest runnable unit — normally one container. Disposable, new IP each time. |
| **Deployment** | "Keep N pods of this image alive; replace them one at a time on change." |
| **Service** | Stable internal DNS name + load balancer over a Deployment's pods. |
| **Ingress** | The single public entrypoint. TLS termination + host/path routing. |
| **ConfigMap / Secret** | Non-secret / secret key-value data injected as env vars. |
| **Job** | Run once to completion, then stop (migrations, seeding). |
| **StatefulSet + PVC** | Pods with stable identity and permanent disk (databases). |
| **Namespace** | A named partition of the cluster. The attachment point for quotas and network policy. |
| **ResourceQuota** | Hard ceiling on total CPU/memory/objects in a namespace. |
| **LimitRange** | Default and maximum per-pod resource values in a namespace. |
| **NetworkPolicy** | Pod-level firewall. **Without one, all pods can reach all pods, cluster-wide.** |
| **requests / limits** | Reserved amount (used for scheduling) / hard ceiling (enforced). CPU over limit = throttled; memory over limit = pod killed. |
| **Probes** | `liveness` = restart me if this fails. `readiness` = stop sending me traffic if this fails. `startup` = don't judge me until I've booted. |
| **Helm** | A templating + release tool for Kubernetes YAML. One chart, many value files. |
| **Cell / silo** | One tenant's dedicated copy of the stack. |

---

## 1. Current problems

Two separate lists. Group A blocks running on Kubernetes *at all*. Group B blocks the *silo* model specifically. Everything below is verified against the current code, not assumed.

### Group A — blocks any Kubernetes deployment

| # | Problem | Where | Why it blocks | Severity |
|---|---|---|---|---|
| A1 | **No manifests exist.** `deploy/k8s/` contains MLflow only. | `deploy/k8s/` | Nothing to deploy. 10 workloads + portal have zero Kubernetes definition. | Blocker |
| A2 | **Portal bakes service URLs at build time, pointing at `localhost`.** 8 `NEXT_PUBLIC_*` values are `ARG`s consumed by `npm run build`. | `src/portal/Dockerfile`, `docker-compose.yml` portal `args` | `NEXT_PUBLIC_*` is compiled into the JS bundle. The browser is told to call `http://localhost:8001`, `:8005`, etc. In a cluster those hosts do not exist. You would need a separate image per environment *and per tenant* — which defeats "one image everywhere". | Blocker |
| A3 | **Browser talks to 8 services directly**, not through one entrypoint. | portal API clients | Requires 8 public hostnames + 8 CORS configs + 8 TLS certs, and leaks internal topology. Should be one host, path-routed. | Blocker |
| A4 | **`celery_worker` bind-mounts source code** (`volumes: - .:/app`). | `docker-compose.yml` | There is no host filesystem to mount in a cluster. The worker must run the code baked into the image. | Blocker |
| A5 | **No resource `requests`/`limits` anywhere.** | all services | The scheduler cannot place pods sensibly; one training task starves the node. `model_serving` (2 GB ONNX cache + reranker + torch) will be OOMKilled on a wrong guess. | Blocker |
| A6 | **`db-init` runs migrations *and* `seed`** in one command. | `docker-compose.yml` `db-init` | Seeding demo data into production is unacceptable. Migrations must be a separate pre-upgrade Job running `alembic upgrade head` only. | Blocker |
| A7 | **Stateful services are compose containers with local volumes**: `postgres`, `redis`, `minio`, `mlflow` backend. | `docker-compose.yml` | Running your own HA Postgres on Kubernetes is a specialist job. These must become Azure managed services (or, on-prem, StatefulSets driven by an operator). | Blocker |
| A8 | **No liveness/readiness split on 3 services.** `/health/live` missing on `analytics_service`, `annotation_service`, `model_serving`. | `src/*/main.py` | Kubernetes needs a *cheap* liveness check and a *dependency-aware* readiness check. If liveness hits a DB-checking `/health`, a brief DB blip restarts every pod at once. | High |
| A9 | **No startup probe strategy for `model_serving`.** It warms the cross-encoder reranker at startup (see the `rerank_timeout_seconds` comment in `config.py`). | `src/model_serving/main.py` | Kubernetes will kill it during boot as "unhealthy" before warm-up finishes. Needs a `startupProbe`. | High |
| A10 | **Zero observability.** No `structlog`, `prometheus`, or `opentelemetry` in `src/`. | whole codebase | In compose you read one terminal. In a cluster, pods are killed and replaced and their logs vanish with them. Debugging a tenant complaint becomes impossible. | High |
| A11 | **Rate limiter is in-process.** `SlidingWindowRateLimiter` uses a local `defaultdict`. | `src/chat_api/services/rate_limiter.py` | Limits multiply by replica count and reset on restart. Separately: `get_headers()` calls `check()`, which *consumes* a slot — so reading the headers double-counts every request. Move it to Redis. | High |
| A12 | **Model cache is per-pod, 2 GB.** | `src/model_serving/services/model_loader.py`, `NER_MODEL_CACHE_MEMORY_LIMIT_GB` | Every replica downloads and holds every hot tenant's model. 3 replicas = 3× memory and 3× object-storage egress. Needs a shared volume, tenant-affinity routing, or an accepted cost. | Medium |
| A13 | **No graceful shutdown for long tasks.** A training task runs for hours; a rolling update sends `SIGTERM`. | `src/training_service/worker.py`, celery config | Work is lost mid-run. Needs `terminationGracePeriodSeconds`, Celery `acks_late=True`, and idempotent tasks. | Medium |
| A14 | **One fat image for everything** — torch + transformers + tesseract in the same image that runs `gateway`. | `Dockerfile` | Likely 3–5 GB. Slow pulls, slow scale-up, oversized attack surface on API pods. Split into a slim API image and a heavy ML image. | Medium |
| A15 | **No image build/push pipeline.** | CI | Kubernetes pulls from a registry; it cannot build. Need CI producing SHA-tagged images in ACR. | Blocker |
| A16 | **Secrets come from a `.env` file** loaded via `env_file=".env"`. | `src/shared/config.py` | Must come from Kubernetes Secrets backed by Azure Key Vault. Good news: `pydantic-settings` already prefers real env vars over the file, so injection works with no code change — just stop shipping `.env` in the image. | High |
| A17 | **`mlflow` manifest hardcodes `us-east-1` and expects MinIO.** | `deploy/k8s/mlflow/deployment.yaml` | Needs to point at Azure Blob and the real region. `replicas: 1` with no PVC is fine only because artifacts live in object storage — preserve that property. | Low |

### Group B — blocks the silo model specifically

| # | Problem | Where | Why it blocks |
|---|---|---|---|
| B1 | **No tenant provisioning automation.** `tenant_service.py` creates a `tenant_{id}` schema from `tenant_template`. Nothing creates a namespace, database, secret, bucket, DNS record, or Helm release. | `src/gateway/services/tenant_service.py` | Onboarding a siloed tenant is currently a manual, undocumented, multi-hour operation. This is the largest piece of new work. |
| B2 | **A siloed pod does not know it is siloed.** Tenant identity is resolved from the JWT by `middleware/tenant_context.py` in every service. | `src/*/middleware/tenant_context.py` | Hand a siloed deployment a valid token for a *different* tenant and it will serve that tenant's data. Isolation is cosmetic unless each cell pins itself to one tenant and rejects everything else. **This is the security core of the design.** |
| B3 | **Single JWT issuer, single shared secret.** | `gateway`, `NER_JWT_SECRET` | Open question: does a siloed tenant authenticate against the shared control plane, or its own gateway with its own signing key? Affects SSO, token revocation, and the blast radius of a leaked secret. |
| B4 | **Single portal host.** Combined with A2, the portal cannot serve `acme.ner.inapp.com` and the pooled host from one image. | `src/portal` | Per-tenant hostnames are the normal silo entry pattern. Blocked on A2. |
| B5 | **Shared singletons with no per-tenant partition.** One bucket `ner-platform`; one MLflow tracking server; one Redis at DB index `0`. | `src/shared/config.py` defaults | A siloed tenant needs its own container/bucket, its own Redis instance or index, and either its own MLflow or strictly-scoped experiments. |
| B6 | **Celery queue names are global constants.** `extraction_celery_queue: "extraction"`, one training queue. | `src/shared/config.py`, `celery_app.py` | Per-tenant fairness is impossible with one shared FIFO. Queue names must derive from the cell/tier. |
| B7 | **No NetworkPolicy.** | `deploy/k8s/` | Kubernetes defaults to allow-all between pods across namespaces. Tenant A's pod can reach Tenant B's database by DNS name. Default-deny is mandatory, not optional. |
| B8 | **Quotas are columns, not enforcement.** `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions` on `public.tenants`. | see `production-plan.md` §2.2 | Nothing reads them at runtime. A pooled tenant has no ceiling. |
| B9 | **No tenant tier in the data model.** | `public.tenants` | Nothing records whether a tenant is `pooled` or `silo`, or which cell serves it. The control plane needs this to route. |
| B10 | **Config is process-wide, not per-tenant.** All settings come from env. | `src/shared/config.py` | Fine for silos (each cell gets its own env). Breaks pooled tenants needing different limits. Needs a per-tenant config table for pooled mode. |

---

## 2. Target state — what the platform must look like

### 2.1 Core principle: one image, many cells

```
                            ┌───────────────────────────────┐
   users ──── HTTPS ────────►         INGRESS               │
   *.ner.inapp.com          │  TLS + host/path routing      │
                            └───────────────┬───────────────┘
                                            │
   ┌────────────────────────────────────────┼─────────────────────────────────┐
   │  namespace: ner-control  (CONTROL PLANE — always shared)                 │
   │  • identity / SSO / token issue      • tenant registry + tier            │
   │  • provisioning controller           • metering + quota ledger           │
   │  • observability (metrics, logs, traces)                                 │
   └────────────────────────────────────────┬─────────────────────────────────┘
                                            │  routes by tenant tier
                 ┌──────────────────────────┴──────────────────────────┐
                 ▼                                                     ▼
   ┌──────────────────────────────┐              ┌──────────────────────────────┐
   │ namespace: ner-pooled        │              │ namespace: tenant-acme       │
   │ TIER: pooled (most tenants)  │              │ TIER: silo (demanding client)│
   │                              │              │                              │
   │ gateway        ×3            │              │ gateway        ×2            │
   │ chat_api       ×3            │              │ chat_api       ×2            │
   │ document_svc   ×2            │              │ document_svc   ×1            │
   │ extraction_svc ×2            │              │ extraction_svc ×1            │
   │ annotation_svc ×2            │              │ annotation_svc ×1            │
   │ analytics_svc  ×2            │              │ analytics_svc  ×1            │
   │ training_svc   ×1            │              │ training_svc   ×1            │
   │ model_serving  ×2            │              │ model_serving  ×1            │
   │ celery-extract ×2            │              │ celery-extract ×1            │
   │ celery-train   ×1            │              │ celery-train   ×1            │
   │ portal         ×2            │              │ portal         ×1            │
   │                              │              │                              │
   │ ResourceQuota (whole ns)     │              │ ResourceQuota (this tenant)  │
   │ NetworkPolicy: default-deny  │              │ NetworkPolicy: default-deny  │
   │ TENANT_MODE=pooled           │              │ TENANT_MODE=silo             │
   │                              │              │ TENANT_ID=acme  ← ENFORCED   │
   │ ▼ Postgres A (shared)        │              │ ▼ Postgres B (dedicated)     │
   │   tenant_1 … tenant_12       │              │   tenant_acme                │
   │ ▼ Blob container: pooled     │              │ ▼ Blob container: acme       │
   │ ▼ Redis DB 0                 │              │ ▼ Redis (own instance)       │
   └──────────────────────────────┘              └──────────────────────────────┘

   NODE POOLS (physical separation of workload types, across all tiers)
   ├── system    2 × D2s_v5   — ingress, monitoring, control plane
   ├── app       3 × D4s_v5   — all FastAPI services + portal
   ├── memory    2 × E4s_v5   — model_serving   (taint workload=memory)
   ├── training  0–2 × NC4as_T4_v3 spot — celery training (taint workload=training)
   └── acme      2 × D4s_v5   — dedicated to one tenant (taint tenant=acme)
```

Both columns run **the exact same container images**. The only differences are environment variables, replica counts, node selectors, and which database URL they receive. This is the non-negotiable invariant: the moment a silo needs a code fork, you own two products.

### 2.2 What every service must satisfy to be "cluster-ready"

Hold each service against this checklist:

1. **Stateless.** Nothing persisted to the pod filesystem beyond scratch. `tempfile.mkdtemp()` in `model_loader.py` and `worker.py` is acceptable — it is per-task scratch, discarded. Anything that must survive goes to object storage or Postgres.
2. **Config from environment only.** Already true (`pydantic-settings`, `NER_` prefix). Keep it that way.
3. **Secrets injected, never baked.** No `.env` in the image.
4. **Two health endpoints.** `/health/live` — process is alive, no dependency calls, no DB. `/health` (readiness) — dependencies reachable.
5. **Declares resources.** `requests` and `limits` for CPU and memory, sized from measurement not guesswork.
6. **Handles `SIGTERM`.** Finishes in-flight work, stops accepting new work, exits. Celery: `acks_late=True` + idempotent tasks + a long grace period.
7. **Logs structured JSON to stdout.** No log files. Include `tenant_id`, `request_id`, `service` on every line.
8. **Exposes `/metrics`.** Request rate, latency, errors, queue depth, token spend.
9. **Tenant-scope-enforced.** Reads `TENANT_MODE`; when `silo`, rejects any request whose resolved tenant ≠ `TENANT_ID` with 403.
10. **Migrations decoupled from startup.** Services must not run `alembic` on boot — three replicas racing the same migration corrupts state. Migrations run once, as a Job, before the rollout.

### 2.3 What stays shared even in silo mode

Silo does not mean "duplicate everything". These stay in the control plane:

- Identity and token issuance (or a per-cell issuer — decision B3)
- Tenant registry, tier assignment, and the provisioning controller
- Observability stack
- Container registry and CI
- Ingress controller and certificate management

Duplicating these per tenant multiplies operational cost with no isolation benefit an auditor cares about.

---

## 3. Changes required, in dependency order

Four stages. Each one must be finished before the next is useful. No dates: the ordering is the point, not the calendar.

(These are called *stages* to avoid colliding with the Phase 1-6 numbering in the execution plan document, which counts something different.)

### Stage 1 — Make the application cluster-ready (code only, no Kubernetes yet)

| # | Change | Files | Fixes |
|---|---|---|---|
| 0.1 | **Route all browser traffic through the gateway.** Add proxy routes on `gateway` for `/api/documents/*`, `/api/annotation/*`, `/api/training/*`, `/api/extraction/*`, `/api/analytics/*`, `/api/chat/*`, `/api/models/*`. The portal then calls one origin. | `src/gateway/`, portal API clients | A3, unblocks A2 |
| 0.2 | **Remove build-time `NEXT_PUBLIC_*` URLs.** Replace with a runtime-resolved base URL — same-origin relative paths (`/api/...`) or a `/config.json` fetched on boot. Delete all 8 `ARG`s from the portal Dockerfile. | `src/portal/Dockerfile`, portal API clients | A2, B4 |
| 0.3 | **Split health endpoints.** Add `/health/live` (no dependency calls) to `analytics_service`, `annotation_service`, `model_serving`. Verify `/health` on all 8 actually checks DB/Redis/object storage via `src/shared/readiness.py`. | `src/*/main.py` | A8 |
| 0.4 | **Move the rate limiter to Redis** (sliding window via a sorted set). Fix the `get_headers()` double-count and the wrong `tuple[bool, int, int]` annotation — it returns 4 values. | `src/chat_api/services/rate_limiter.py` | A11 |
| 0.5 | **Structured logging.** `structlog` JSON to stdout, with `tenant_id` / `request_id` / `service` bound from middleware. | `src/shared/`, all `main.py` | A10 |
| 0.6 | **Prometheus metrics** on all 8 services, plus custom gauges for Celery queue depth, model cache size, and LLM tokens per tenant. | `src/shared/`, all `main.py` | A10 |
| 0.7 | **Add `TENANT_MODE` + `TENANT_ID` settings and enforcement middleware.** When `TENANT_MODE=silo`, any request resolving to a different tenant returns 403 before touching the DB. | `src/shared/config.py`, `src/*/middleware/tenant_context.py` | **B2 — do not skip** |
| 0.8 | **Parameterise Celery queue names** from config (`NER_CELERY_QUEUE_PREFIX`) so each cell has its own queues. Set `acks_late=True`, `task_reject_on_worker_lost=True`, make training/extraction tasks idempotent. | `src/*/celery_app.py`, `worker.py` | B6, A13 |
| 0.9 | **Separate migrations from seeding.** `db-init` becomes two commands: `migrate` (alembic only) and `seed` (never in production). | `docker-compose.yml`, new entrypoint | A6 |
| 0.10 | **Enforce quotas.** Read `max_users` / `max_documents` / `max_storage_gb` / `max_model_versions` at the write paths; hard-block. | `gateway`, `document_service`, `training_service` | B8 |
| 0.11 | **Add `tier` and `cell` columns to `public.tenants`** (`pooled` \| `silo`, plus cell name). Alembic migration. | `alembic/versions/`, `src/gateway/` | B9 |
| 0.12 | **Split the Dockerfile** into an `api` target (slim, no torch) and an `ml` target (torch, transformers, tesseract). Stop relying on the source bind-mount; never copy `.env`. | `Dockerfile`, `docker-compose.yml` | A14, A4, A16 |
| 0.13 | **Parameterise object storage and Redis per tenant** — bucket/container name and Redis DB index from config, not the hardcoded `ner-platform` / `/0` defaults. | `src/shared/config.py`, storage clients | B5 |

**Checkpoint:** at the end of Stage 1, `docker compose up` still works, and every change is independently testable without a cluster. Do not touch Kubernetes before this is green.

### Stage 2 - Base cluster + pooled tier

| # | Change | Deliverable |
|---|---|---|
| 1.1 | CI builds and pushes both images to ACR, tagged with the git SHA | CI workflow |
| 1.2 | Azure landing zone: resource group, VNet, AKS across 3 zones, ACR, Key Vault | Terraform/Bicep, committed |
| 1.3 | Managed data services: Postgres Flexible Server + PgBouncer, Azure Cache for Redis, Blob Storage | replaces A7 |
| 1.4 | One Helm chart, `deploy/helm/ner-platform/`, with a generic `templates/service.yaml` looping over a `services:` map | 11 workloads from ~150 lines of template |
| 1.5 | Node pools + taints/tolerations + `nodeSelector` per workload | noisy-neighbour fix |
| 1.6 | Resource requests/limits, measured under load (start generous, tighten) | A5 |
| 1.7 | Probes wired: `startupProbe` on `model_serving`, `livenessProbe` → `/health/live`, `readinessProbe` → `/health` | A8, A9 |
| 1.8 | Migration as a Helm `pre-upgrade` hook Job | A6 |
| 1.9 | Secrets via the Key Vault CSI driver | A16 |
| 1.10 | Ingress (nginx or AGIC) + cert-manager for TLS, one hostname | A3 |
| 1.11 | Observability: managed Prometheus + Grafana, log aggregation | A10 |
| 1.12 | Backups: Postgres point-in-time restore, Blob soft-delete + versioning | plan gap |

**Checkpoint:** the pooled tenants run on AKS. This alone solves the noisy-neighbour problem, via node pools, per-queue workers, resource limits, and the Redis-backed rate limiter.

### Stage 3 - Isolation mechanisms

| # | Change |
|---|---|
| 2.1 | `NetworkPolicy`: default-deny ingress and egress per namespace; explicit allows for gateway→services, services→Postgres/Redis/Blob, and DNS. Verify by attempting a cross-namespace connection and confirming it fails. |
| 2.2 | `ResourceQuota` + `LimitRange` per namespace |
| 2.3 | `PodDisruptionBudget` on every service, so node maintenance cannot take a tier down |
| 2.4 | Distinct `ServiceAccount` per namespace; Workload Identity so each cell reaches only its own Key Vault secrets and its own Blob container |
| 2.5 | Per-tenant Celery queues live, with a worker Deployment per queue |
| 2.6 | `TENANT_MODE=silo` enforcement tested adversarially: a valid token for tenant B against tenant A's cell must return 403 |

### Stage 4 - First silo cell + provisioning automation

| # | Change |
|---|---|
| 3.1 | Second Helm release from the same chart, `values-acme.yaml`: own namespace, `TENANT_MODE=silo`, `TENANT_ID=acme`, own DB URL, own Blob container, own queue prefix, `nodeSelector: tenant=acme` |
| 3.2 | Dedicated Postgres Flexible Server for the siloed tenant |
| 3.3 | Dedicated node pool with taint `tenant=acme:NoSchedule` |
| 3.4 | Per-tenant hostname `acme.ner.inapp.com` + ingress rule + certificate |
| 3.5 | **Provisioning controller** in the control plane: given a tenant with `tier=silo`, create namespace → DB + schema → Key Vault secrets → Blob container → Helm release → DNS + cert → mark ready. Start as a scripted runbook; promote to code once it has been run twice by hand. |
| 3.6 | Deprovisioning path (data export, then teardown) — required before signing any contract with an exit clause |
| 3.7 | Runbooks: rollback, restore-from-backup, tenant onboarding, incident response |

Stages 1–2 are the mandatory foundation; nothing in Stages 3–4 is reachable without them.

---

## 4. How to actually deploy — concrete steps

### 4.1 Learn on a laptop cluster first

Do not learn Kubernetes on Azure. You will spend money and confuse cloud problems with Kubernetes problems.

Install: Docker Desktop, `kubectl`, `kind`, `helm`.

```bash
kind create cluster --name ner --config kind-config.yaml
kubectl get nodes
kubectl create deployment hello --image=nginx --replicas=3
kubectl get pods -o wide          # 3 pods spread across nodes
kubectl delete pod <one-pod>      # watch it return — this is desired state
kubectl expose deployment hello --port=80
kubectl run -it --rm curl --image=curlimages/curl -- curl http://hello
```

That sequence is the whole mental model: you declared 3, deleted 1, Kubernetes restored 3, and the Service kept a stable name across a changed pod IP. Spend a day on `kubectl get`, `describe`, `logs`, `exec`, `port-forward` until they are reflexes. `kubectl describe pod` is where most debugging happens — the `Events` section at the bottom explains nearly every failure.

### 4.2 Get one of your own services running locally

Start with `gateway`, the smallest useful slice.

1. `kind load docker-image ner-api:dev` — push your locally built image into the kind cluster.
2. Deploy Postgres and Redis as simple single-replica StatefulSets (local only; production uses managed services).
3. Create a `Secret` for `NER_JWT_SECRET` and a `ConfigMap` for the rest.
4. Run the migration as a `Job`; confirm completion with `kubectl get jobs`.
5. Deploy `gateway` as a `Deployment` + `Service`.
6. `kubectl port-forward svc/gateway 8000:8000`, then hit `/health`.

Expect failures. The three you will hit:

| Symptom | Cause |
|---|---|
| `ImagePullBackOff` | Cluster cannot find the image — wrong name/tag, or never loaded/pushed. |
| `CrashLoopBackOff` | Container starts then exits. `kubectl logs <pod> --previous` shows why. Usually a missing env var. |
| `Pending` forever | Nothing can schedule it — `requests` exceed node capacity, or a taint has no matching toleration. `kubectl describe pod` names which. |

### 4.3 Write the Helm chart

You have 11 near-identical workloads. Do **not** write 11 sets of YAML. One template, driven by values:

```yaml
# deploy/helm/ner-platform/values.yaml
image:
  api: myacr.azurecr.io/ner-api
  ml:  myacr.azurecr.io/ner-ml
  tag: ""            # set per release to the git SHA

tenant:
  mode: pooled       # pooled | silo
  id: ""             # required when mode=silo
  queuePrefix: pooled

services:
  gateway:
    image: api
    replicas: 3
    port: 8000
    command: ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
    public: true
    resources:
      requests: { cpu: 250m, memory: 512Mi }
      limits:   { cpu: "1",  memory: 1Gi }

  model_serving:
    image: ml
    replicas: 2
    port: 8000
    command: ["uvicorn", "src.model_serving.main:app", "--host", "0.0.0.0", "--port", "8000"]
    nodeSelector: { workload: memory }
    tolerations: [{ key: workload, value: memory, effect: NoSchedule }]
    startupProbe: { path: /health, failureThreshold: 30, periodSeconds: 10 }
    resources:
      requests: { cpu: "1", memory: 4Gi }      # 2Gi cache + reranker + runtime
      limits:   { cpu: "2", memory: 6Gi }

  celery_train:
    image: ml
    replicas: 1
    command: ["celery", "-A", "src.training_service.celery_app", "worker",
              "-Q", "{{ .Values.tenant.queuePrefix }}-training", "--concurrency=1"]
    nodeSelector: { workload: training }
    tolerations: [{ key: workload, value: training, effect: NoSchedule }]
    terminationGracePeriodSeconds: 3600       # let a training run finish
  # ... remaining 8 workloads
```

Deploying a silo is then one command with a different values file — not new YAML:

```bash
helm upgrade --install pooled ./deploy/helm/ner-platform \
  -n ner-pooled --create-namespace \
  -f values-pooled.yaml --set image.tag=$GIT_SHA

helm upgrade --install acme ./deploy/helm/ner-platform \
  -n tenant-acme --create-namespace \
  -f values-acme.yaml --set image.tag=$GIT_SHA
```

Always render before applying — this catches most template mistakes:

```bash
helm template acme ./deploy/helm/ner-platform -f values-acme.yaml | less
```

### 4.4 Move to Azure

```bash
az group create -n rg-ner-prod -l centralindia
az acr create -g rg-ner-prod -n neracr --sku Standard
az aks create -g rg-ner-prod -n aks-ner-prod \
  --node-count 3 --node-vm-size Standard_D4s_v5 \
  --zones 1 2 3 --attach-acr neracr \
  --enable-managed-identity --enable-addons monitoring

az aks nodepool add -g rg-ner-prod --cluster-name aks-ner-prod \
  -n memory --node-vm-size Standard_E4s_v5 --node-count 2 \
  --labels workload=memory --node-taints workload=memory:NoSchedule

az aks nodepool add -g rg-ner-prod --cluster-name aks-ner-prod \
  -n training --node-vm-size Standard_NC4as_T4_v3 \
  --priority Spot --eviction-policy Delete \
  --min-count 0 --max-count 2 --enable-cluster-autoscaler \
  --labels workload=training --node-taints workload=training:NoSchedule

az postgres flexible-server create -g rg-ner-prod -n pg-ner-pooled \
  --tier GeneralPurpose --sku-name Standard_D2ds_v4 --high-availability ZoneRedundant
az redis create -g rg-ner-prod -n redis-ner --sku Standard --vm-size c1
az storage account create -g rg-ner-prod -n nerstorageprod --sku Standard_ZRS

az aks get-credentials -g rg-ner-prod -n aks-ner-prod
```

Then, in order: cert-manager and ingress → Key Vault CSI driver and secrets → migration Job → `helm upgrade --install pooled` → smoke test → point DNS.

### 4.5 Deployment order for a production release

1. Build and push images tagged with the git SHA.
2. Run the migration Job. **Wait for success.** Never proceed past a failed migration.
3. `helm upgrade --install` the pooled release with the new tag.
4. `kubectl rollout status deployment/gateway -n ner-pooled` — blocks until pods are ready, fails if they are not.
5. Smoke test through the ingress: login, upload, extract, chat.
6. If broken: `helm rollback pooled` — instant, because the previous release is retained.

This puts a hard constraint on schema changes: because old and new pods run simultaneously during a rolling update, **every migration must be backwards-compatible** (expand-contract — add a nullable column, deploy code that writes both, backfill, drop in a later release). A migration that renames a column breaks the pods not yet replaced.

### 4.6 Onboarding a siloed tenant (the runbook to automate later)

1. Create the tenant record with `tier=silo`, `cell=acme`.
2. Provision the dedicated Postgres server; run migrations against it; create the `tenant_acme` schema.
3. Create the Blob container and the Key Vault secrets.
4. Add the dedicated node pool with taint `tenant=acme:NoSchedule`.
5. Write `values-acme.yaml`: namespace, `tenant.mode=silo`, `tenant.id=acme`, DB URL, container name, queue prefix, node selector.
6. `helm upgrade --install acme ...`
7. Apply `NetworkPolicy`, `ResourceQuota`, `LimitRange` to the namespace.
8. Create the DNS record and certificate for `acme.ner.inapp.com`.
9. **Verify isolation.** Obtain a valid token for a different tenant, call the acme cell, confirm 403. Attempt a pod-to-pod connection from `tenant-acme` to the pooled Postgres, confirm it is refused. Neither test is optional.
10. Record the cell in the tenant registry so the control plane routes correctly.

---

## 5. Cost implication

The pooled baseline from `production-plan.md` §11 is ~$1,300–1,700/month. Each silo adds roughly:

| Item | Monthly |
|---|---|
| Dedicated node pool (2 × D4s_v5) | ~$280 |
| Dedicated Postgres Flexible Server (D2ds_v4, zone-redundant) | ~$180 |
| Dedicated Redis (C1) | ~$55 |
| Blob, DNS, certificates | ~$10 |
| **Per siloed tenant** | **~$525** |

One demanding client is affordable. Silos for all 15 tenants is ~$8,000/month plus mandatory provisioning automation, and it changes the commercial model — that is a pricing decision, not an infrastructure one.

---

## 6. Relationship to the execution plan

**Decision: the single-VM deployment is cancelled.** The execution plan's Phase 4 ("Production deployment - internal network": Docker Compose on an assigned VM, nginx proxying `nerp.inapp.com` to `localhost:3000`) is replaced by the Kubernetes deployment described in this document. Its Phase 6 ("Cloud migration") is therefore no longer a separate follow-on step - it is the same work, brought forward and merged into Phase 4.

Consequences worth stating plainly:

- **Internal go-live moves later.** The VM path was the fast route to a URL the teams could use. Kubernetes is not faster; it is the correct end state. Stage 1 of this document has to finish before any cluster work is useful.
- **The nginx reverse proxy work disappears.** In Kubernetes an Ingress does that job. Nothing carries over from that step, which is precisely why doing the VM first was duplicated effort.
- **The `nerp.inapp.com` DNS and TLS request still matters.** Raise it with ITS regardless - the hostname points at an Ingress instead of a VM, but the request and the lead time are identical. It is external and it will sit on the critical path if left late.
- **No VM is needed for production**, but one is still worth having as a shared development box.

### 6.1 What the execution plan already covers

Three parts of the execution plan are unchanged by this decision and feed directly into Stage 1.

**Section 6 (Security, Compliance & Tenant Isolation)** covers the *logical data* axis thoroughly: signed-token tenant identity, schema-per-tenant with Row-Level Security as defence in depth, tenant-prefixed storage/cache/queue keys, per-tenant models and config. All of it is correct and all of it is prerequisite. It is worth being explicit in that document that none of it delivers *silo* isolation - it is the lock on the apartment door, not a separate plot. Compute, failure, network, and operations isolation (see §2 here) come only from Stages 2-4. Section 6.4's test list should gain two cases: a valid token for tenant B against tenant A's cell returns 403, and a cross-namespace network connection is refused.

**Section 7 (Observability)** already specifies OpenTelemetry, Prometheus, Grafana, Loki, and Tempo. That is changes 0.5-0.6 of this document, already scoped. Two implementation constraints so it survives into a cluster: log **structured JSON to stdout only** (no log files - Loki and Kubernetes both read stdout, and pod filesystems are discarded), and bind `tenant_id`, `request_id`, and `service` on every line.

**Section 5.4's two commitments** - treat tenant isolation and per-tenant rate limiting as a first-class access boundary now, and keep configuration environment-driven. The configuration half already holds (`pydantic-settings`, `NER_` prefix). The rate-limiting half does not: `SlidingWindowRateLimiter` is an in-process `defaultdict` and will have to be rebuilt. That is change 0.4.

### 6.2 What the execution plan does not cover

Everything in §3 of this document. In execution-plan terms, Phase 4 is no longer a four-step VM setup but the four stages here, and the Phase 6 row is deleted rather than deferred.

The parts with no equivalent anywhere in the current plan, and therefore the parts most likely to be under-estimated:

- Stage 1's 13 application changes - particularly the portal consolidation (0.1-0.2) and `TENANT_MODE` enforcement (0.7)
- A container registry and an image build pipeline (A15)
- Managed Postgres, Redis, and object storage replacing the compose containers (A7)
- Resource sizing measured under load rather than guessed (A5)
- Backups and restore, which the VM plan mentioned in one line and which Kubernetes does not provide for you
- Tenant provisioning automation (B1) - the largest single new piece of work, and a product in its own right

### 6.3 One thing to raise with whoever owns the roadmap

Two independent drivers led here: noisy-neighbour fairness, and a client demanding dedicated infrastructure. The first is satisfied at the end of Stage 2. The second needs Stage 4.

The single-VM deployment could not have served that client at all - one VM, one Postgres, one Docker network is the architectural opposite of a silo. So this decision does not merely change infrastructure; it is what makes that commercial conversation possible. Worth saying out loud, because it is the justification for a later go-live.

Cost shape for that conversation: ~$1,300-1,700/month for the shared cluster, plus ~$525/month per siloed tenant (§5).

---

## 7. The three things most likely to go wrong

1. **Skipping Stage 1.** The temptation is to start writing YAML immediately. Deploy the portal with `localhost` URLs baked in and nothing works, and you will not understand why — because the failure is in the browser, not in the cluster.
2. **Guessing resource limits.** `model_serving` will be OOMKilled. Measure real memory under load (`kubectl top pod`), then set limits at roughly 1.5× the observed peak.
3. **Treating `TENANT_MODE=silo` as optional.** Without change 0.7, a siloed namespace is a cosmetic boundary — the pods will serve any tenant whose token they receive. You would be selling isolation you do not have.
