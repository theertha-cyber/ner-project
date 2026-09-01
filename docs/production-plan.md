# Production Plan — NER Platform as an Internal SaaS

**Version:** 1.0
**Date:** 2026-08-19
**Owner:** Platform team (3 developers)
**Audience:** InApp leadership, platform engineering, and client-facing stakeholders
**Status:** Draft for approval

---

## 1. Executive Summary

The NER Platform today is a working multi-tenant document-intelligence application: tenants define custom entities, annotate documents, fine-tune a per-tenant NER model, run extractions, and query results through a RAG chat assistant. It runs on docker-compose against a single Postgres instance and has never been deployed.

This plan takes it to production as an **internal InApp SaaS platform serving InApp and it's clients**, and folds in the architecture and use cases proven by the RAG chatbots other InApp teams have already built (LangChain / FastGraphRAG based). Those chatbots are **not** being ported as code or plugins — we re-implement their behaviours natively on our stack so there is one platform and one control plane.

Four things must be true before we can call this production:

| # | Outcome | Why it is not true today |
|---|---|---|
| 1 | **Any agent, retriever, LLM, or tool can be swapped by config** | Retrieval and generation are hardwired into a fixed LangGraph topology in [`builder.py`](../src/chat_api/graph/builder.py); swapping means editing code and redeploying |
| 2 | **One tenant cannot degrade another** | Rate limiting is in-process ([`rate_limiter.py`](../src/chat_api/services/rate_limiter.py)), model cache is per-pod, training and OCR share the same worker pool, and all tenants share one unpooled Postgres | 
| 3 | **We can see and enforce what every tenant consumes** | No metrics, tracing, or structured logging exists anywhere in `src/`; token spend is invisible; quotas exist as columns on `public.tenants` but are not enforced at runtime |
| 4 | **It survives a node failure and a security review** | No Kubernetes manifests except MLflow, no HA, no backups, no SSO, no pentest |

The plan is delivered in **five phases over ~9 months** with a 3-developer team. Phase 1–3 (≈5 months) produce a beta-ready platform for one pilot client. Phase 4–5 harden it for general availability across InApp's client base.

Estimated steady-state infrastructure cost at 10 tenants: **~$1,300–1,700/month** plus **~$200–900/month** of Azure OpenAI usage, detailed in §11.

---

## 2. Where We Are Today

### 2.1 What works

Nine services, all functional in local compose:

| Service | Port | Responsibility |
|---|---|---|
| `gateway` | 8000 | Auth (JWT), tenant CRUD, entity definitions, training approval, model promotion |
| `document_service` | 8001 | Upload to MinIO, Tesseract OCR, text span extraction |
| `extraction_service` | 8002 | Live + batch extraction, entity review workflow |
| `training_service` | 8003 | Training job lifecycle, Celery dispatch, MLflow runs |
| `model_serving` | 8004 | Per-tenant ONNX model cache, inference, warmup |
| `annotation_service` | 8005 | Task assignment, span CRUD, pre-labeling, dataset export |
| `chat_api` | 8006 | LangGraph RAG orchestration, conversations, widget API keys |
| `analytics_service` | 8007 | Dashboard aggregates, SQL query surface |
| `portal` | 3000 | Next.js UI for all four roles |

Foundations that are genuinely good and that this plan builds on rather than replaces:

- **Schema-per-tenant isolation** (`tenant_{id}` schemas from a `tenant_template` blueprint) — strong data boundary, no cross-tenant leak risk from a missing `WHERE` clause.
- **Deterministic graph routing.** [`builder.py`](../src/chat_api/graph/builder.py) routes on state, never on an LLM's choice of next node. Keep this invariant — it is what makes the pipeline testable.
- **Feature flags already in `src/shared/config.py`** (`reranker_enabled`, `entity_resolution_enabled`, `sql_execution_role_enabled`, `candidate_document_filtering_enabled`) — the seed of the config-driven registry in §4.
- **Widget API keys** — SHA-256 hashed, prefix-only on list, raw shown once. Correct pattern; extend it, don't rebuild it.
- **Quota columns on `public.tenants`** (`max_users`, `max_documents`, `max_storage_gb`, `max_model_versions`) — the schema is there, enforcement is not.
- **Audit logging** already implemented and retained indefinitely.

### 2.2 Gaps that block production

| Area | Current state | Risk |
|---|---|---|
| Deployment | docker-compose only; `deploy/k8s` has MLflow alone | Cannot deploy, scale, or roll back |
| Observability | Zero `prometheus` / `opentelemetry` / `structlog` usage in `src/` | Blind in production; no way to debug a tenant complaint |
| Rate limiting | In-memory `defaultdict` per process | Limits multiply by replica count, reset on restart, and do not protect Postgres or Azure OpenAI |
| LLM metering | Not captured | Cannot attribute cost, cannot enforce, cannot price later |
| Model cache | 2 GB in-process cache per `model_serving` pod, 30-min TTL | Every pod loads every hot tenant's model; memory pressure is shared, evictions are random across tenants |
| Worker isolation | One Celery pool for training, a second for extraction; no per-tenant fairness | One tenant's 50-document batch starves everyone |
| Postgres | Single instance, no connection pooler, no read replica, no HA | Single point of failure; connection exhaustion at ~10 services × replicas |
| Auth | Custom JWT, password hashes in `public.tenant_users` | No SSO, no MFA, no session revocation |
| Secrets | `.env` file, committed `.env.example`, `NER_OPENAI_API_KEY` in plaintext | Fails any security review |
| Testing | pytest suite exists; no load, security, or contract tests; no CI gates verified | Regressions ship silently |
| Backups | None | Data loss is unrecoverable |

### 2.3 Locked decisions from requirements review

These were confirmed and are **not** revisited in this plan:

1. Product is a **NER/document-intelligence platform that also hosts chatbots** — NER training and annotation stay core, because extraction quality is what the chatbots are grounded on.
2. Existing InApp chatbots are **re-implemented, not ported**. We reuse their architecture and design patterns (LangChain, graph-RAG) and their use cases. No code lift, no plugin wrapper, no data migration — there are no live users on them and no state to move.
3. Data sources are **ours only** — documents uploaded into the platform. No SharePoint/Confluence/external connectors in scope.
4. Agent/component switching is **config-driven, platform-team-only**. System admins configure; tenants do not author agents.
5. **No document-level ACLs.** The tenant is the only data boundary; the four existing roles are sufficient.
6. **SSO is required.**
7. Usage metering is **per-tenant, visibility-only** for now — but built accurately enough to bill from later.
8. Quota enforcement is **hard** (block, not warn).
9. Azure, **single region**, **shared multi-tenant** deployment. Greenfield — no existing infrastructure to inherit.
10. Postgres remains the primary datastore and vector store (pgvector).
11. Pricing, licensing model, branding/white-labelling, compliance certification, SLA commitments, and beta cohort selection are **deferred to a later phase**. This plan builds the mechanisms they will need, and says so explicitly.
12. API-only delivery. No Teams/Slack/WhatsApp channels.
13. Team is **3 developers, junior**, with no dedicated DevOps, QA, or security resource. Every estimate assumes this.

### 2.4 Assumptions I am making where no answer was available

Flagging these rather than burying them. Each is cheap to reverse now and expensive later.

| Assumption | Rationale | Reverse by |
|---|---|---|
| **Azure OpenAI** is the LLM provider, `gpt-4o-mini` for routing/SQL/titles and `gpt-4o` for final generation | Azure is the cloud; keeps data in our subscription and region | Phase 2, once the provider adapter in §4.2 exists |
| Training runs on an **on-demand Azure GPU spot VM** (`NC4as_T4_v3`), created per job and destroyed after | No GPU budget was allocated, but spot pricing makes this ~$25–60/month at expected volume — far cheaper than the CPU alternative's wall-clock cost. CPU-only fine-tuning is the fallback and takes 4–8 hours per job | Phase 3 |
| Year-one scale target: **10–15 tenants, ~200 named users, ~50k chat messages/month, ~20k documents/month** | "Not much" load; sized so headroom exists without over-engineering | Load test targets in §9.4 |
| Single Azure region: **Central India** | InApp's likely subscription home; no residency requirement stated | Phase 4 |
| No compliance certification pursued in this plan, but **SOC 2 / ISO 27001 controls are not actively violated** — audit logging, encryption, least privilege, secret management are built to be certifiable later | Certification deferred, but retrofitting controls costs 3–4× | N/A |

---

## 3. Target Architecture

### 3.1 Principle: three layers, cleanly separated

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTROL PLANE          (new — §6)                              │
│  identity · entitlements · quotas · metering · observability     │
│  Every request passes through. Nothing bypasses it.              │
├─────────────────────────────────────────────────────────────────┤
│  CAPABILITY PLANE       (refactor — §4)                          │
│  agents · retrievers · tools · LLM adapters · rerankers          │
│  All resolved from a registry at request time. All swappable.     │
├─────────────────────────────────────────────────────────────────┤
│  DATA PLANE             (harden — §5)                            │
│  Postgres+pgvector · Blob · Redis · RabbitMQ · model artifacts    │
│  Per-tenant schemas, per-tier resource pools.                    │
└─────────────────────────────────────────────────────────────────┘
```

The rule that makes this work: **a capability never talks to infrastructure directly, and never reads config from the environment.** It receives a `TenantContext` carrying the resolved configuration, the metering handle, and the budget remaining. This is the single change that makes everything else in this plan possible.

### 3.2 Making it futuristic: the capability registry

The requirement is that any future change — a new agent, a different LLM, a new retriever, a swapped reranker — plugs in without touching the pipeline. The mechanism:

**a. Every pluggable thing implements a narrow protocol.**

```python
# src/shared/capabilities/protocols.py  (new)

class Retriever(Protocol):
    name: str
    async def retrieve(self, q: Query, ctx: TenantContext) -> list[Evidence]: ...

class LLMAdapter(Protocol):
    name: str
    async def complete(self, req: CompletionRequest, ctx: TenantContext) -> Completion: ...
    # returns token counts — metering is not optional

class Tool(Protocol):
    name: str
    schema: dict            # JSON Schema; MCP-compatible shape
    async def invoke(self, args: dict, ctx: TenantContext) -> ToolResult: ...

class Agent(Protocol):
    name: str
    async def run(self, state: ChatState, ctx: TenantContext) -> ChatState: ...
```

Existing code already fits these shapes with modest refactoring — `sql_generator`, `embedding_service`, `entity_resolver`, and the reranker each become a registered capability rather than an import.

**b. A registry maps names to implementations, and config maps tenants to names.**

```yaml
# config/profiles/default.yaml — versioned in git, edited by platform team only
profile: default
version: 7
llm:
  generation:  { adapter: azure_openai, model: gpt-4o,      max_tokens: 1200 }
  utility:     { adapter: azure_openai, model: gpt-4o-mini, max_tokens: 400 }
retrievers:
  - { name: sql_entities,   weight: 1.0, timeout_ms: 2500 }
  - { name: vector_chunks,  weight: 1.0, timeout_ms: 2000, top_k: 12 }
  - { name: live_ner,       weight: 0.6, timeout_ms: 3000 }
reranker: { name: cross_encoder_minilm, enabled: true }
agents:
  - qa_agent
  - chart_agent
guardrails: { input: [pii_scan, injection_scan], output: [citation_required] }
```

Tenants reference a profile; overrides are a shallow merge stored in `public.tenant_capability_profiles`. This turns today's boolean flags in `src/shared/config.py` into structured, versioned, per-tenant configuration — the same idea, one level up.

**c. The graph topology becomes data, not code.**

[`builder.py`](../src/chat_api/graph/builder.py) currently hardcodes the node list and edges, with one `if` for `entity_resolution_enabled`. Replace with a builder that compiles a topology from the resolved profile. **Keep the existing invariant absolutely: routing predicates remain pure functions of state, never LLM-chosen.** That property is why this pipeline is testable, and a registry must not erode it.

**d. Every change is versioned and reversible.** Profile changes are git commits; a `version` field is stamped on every conversation record so any answer can be traced to the exact configuration that produced it. Rollback is a revert.

**Explicitly out of scope by decision (5.4 above):** no tenant-facing agent builder, no third-party plugin marketplace, no MCP server implementation. The `Tool.schema` field is deliberately MCP-shaped so adopting MCP later is an adapter, not a redesign.

### 3.3 Porting the existing chatbots' behaviours

We take architecture and use cases, not code. Concretely, three things the existing chatbots do that we do not:

**1. Graph-RAG retrieval (from FastGraphRAG).** Today retrieval is three parallel flat lookups: SQL over `extracted_entities`, pgvector similarity over chunks, and live NER inference. FastGraphRAG's contribution is *relational* retrieval — following edges between entities to answer questions that no single chunk contains ("which vendors appear in contracts that also mention indemnity?").

Implementation: build a tenant-scoped entity graph from data we already have. `extracted_entities` rows give the nodes; co-occurrence within a document or span window gives the edges. Materialise as `tenant_{id}.entity_graph_edges` and register a `graph_walk` retriever alongside the existing three. This is additive — a fourth entry in the `retrievers` list, no change to the other three.

**2. Chart plotting over extracted data.** Register a `chart_agent` whose tool returns a **chart specification** (Vega-Lite JSON), never rendered images or executable code. The portal renders it. The agent's data access goes through `analytics_service`'s existing query surface under the read-only role that `sql_execution_role_enabled` already anticipates. Never let an LLM emit code that runs server-side.

**3. Multi-format ingestion.** Today: Tesseract OCR on images and PDFs. Needed: DOCX, XLSX/CSV, PPTX, HTML, EML, and native-text PDFs (which should skip OCR entirely — a large accuracy and cost win). Implementation is a format-handler registry in `document_service` keyed on detected MIME type, each handler emitting the same `document_text_spans` rows. Spreadsheets need their own path: rows become records, not prose, and feed the SQL retriever rather than the vector store.

**Porting method.** For each existing chatbot: (1) sit with its owner and capture behaviour as 15–30 golden question/answer pairs plus its system prompts and retrieval strategy; (2) express it as a capability profile; (3) run the golden set against our platform; (4) iterate the profile until it passes. The golden sets become permanent regression tests. This is the only reliable way to prove a re-implementation matches a system whose code we are not reusing.

**Note on §2.4:** an evaluation harness was marked out of scope in requirements review. I am including the golden-set mechanism anyway, at minimal cost — without it there is no evidence a re-implemented chatbot behaves like the original, and no way to safely swap a component later. It is roughly 3 developer-days for a pytest-driven runner over YAML fixtures. If you want it removed, it is the one item in this plan I would argue against cutting.

---

## 4. Multi-Tenancy: Noisy Neighbours and Fair Use

This is where a working application becomes a SaaS platform. Six contention points exist in the current code, ordered by how quickly they will bite.

### 4.1 Contention point 1 — LLM concurrency and spend (highest risk)

**Problem.** Azure OpenAI deployments have a fixed tokens-per-minute quota. One tenant running a 200-document batch extraction with chat summarisation consumes the whole TPM allocation; every other tenant sees 429s and multi-second latency. Today nothing prevents this — there is no token accounting at all.

**Fix.**
- A shared **LLM broker** in front of every Azure OpenAI call. All traffic goes through the `LLMAdapter`, so there is exactly one chokepoint.
- **Per-tenant token buckets in Redis** (replacing the in-process limiter), keyed `ratelimit:{tenant}:{resource}:{window}`. Redis-backed means limits are global across replicas and survive restarts.
- **Two queue classes**: interactive (chat, low latency, guaranteed share) and batch (extraction, summarisation, preemptible). Batch never starves interactive. A tenant's batch work is capped at a percentage of total batch capacity.
- **Hard budget enforcement** per §2.3.8: `max_tokens_per_month` on `public.tenants`; the broker refuses the call and returns HTTP 402 with a structured quota error when exhausted.
- Separate Azure OpenAI deployments for interactive vs batch, so batch 429s cannot affect chat.

### 4.2 Contention point 2 — Postgres

**Problem.** One instance, no pooler. Ten services × N replicas × pool size exhausts `max_connections` fast. Worse, pgvector similarity search and `analytics_service` aggregate queries are both CPU-heavy and share the same server — one tenant's dashboard query slows everyone's chat retrieval. Schema-per-tenant isolates *data*, not *load*.

**Fix.**
- **Azure Database for PostgreSQL Flexible Server**, General Purpose, zone-redundant HA.
- **PgBouncer in transaction mode** as a mandatory hop. Non-negotiable at this service count.
- **Statement timeouts by workload class** — set on the session, not globally: 5s for interactive retrieval, 30s for analytics, 5min for batch. Prevents a runaway query from holding resources.
- **Read replica** for `analytics_service` and dashboard queries, moving all reporting load off the primary.
- **Per-tenant connection caps** in PgBouncer so one tenant cannot occupy the whole pool.
- **HNSW indexes** on every `pgvector` column (verify these exist; sequential vector scans are the most common cause of pgvector slowness).
- **Schema count ceiling.** Schema-per-tenant is right for the stated 10–15 tenants. Past roughly 200 tenants, catalogue bloat and migration time become real problems — migrations run once per schema. Flag now, revisit if growth exceeds plan; the mitigation is tenant-group sharding across databases, not a switch to RLS.

### 4.3 Contention point 3 — model_serving memory

**Problem.** `model_cache_memory_limit_gb: 2` with a 30-minute TTL, in-process per pod. With N replicas behind a round-robin service, every pod eventually loads every active tenant's ONNX model — N× the memory for the same working set. Cache evictions are effectively random across tenants: tenant A's traffic evicts tenant B's model, and B pays a cold-start penalty (the warmup path in `promote` exists precisely because that penalty is significant).

**Fix.**
- **Consistent-hash routing by `tenant_id`** so a tenant's requests land on the same pod and its model is loaded once, not N times. This is the single highest-value change in this section.
- **Per-tenant cache reservation** — a tenant cannot evict more than its share.
- **Tiered pools**: shared pool by default; a dedicated `model_serving` deployment for any tenant whose latency requirements justify it. This is the natural shape of a future premium tier.
- **Warm-standby on promote** — extend the existing warmup call to pre-load on all pods in the tenant's hash ring before flipping the active version.

### 4.4 Contention point 4 — Celery workers

**Problem.** `celery_worker` (training) and `celery_worker_extraction` share broker and pool. A tenant submitting 50 documents fills the queue; FIFO means everyone behind them waits. Training jobs are hours long and hold a worker slot the whole time.

**Fix.**
- **Queue per workload class**: `training`, `extraction`, `ocr`, `embedding` — separate queues, separately scaled.
- **Per-tenant concurrency cap** enforced at task-accept time (a Redis semaphore keyed by tenant), so a tenant can hold at most K slots regardless of how many tasks they submit.
- **Weighted fair queueing** — round-robin across tenants with pending work rather than global FIFO.
- **Training on ephemeral GPU nodes** (per §2.4) so a training job never occupies a shared worker at all.
- **KEDA autoscaling** on queue depth per queue.

### 4.5 Contention point 5 — storage and ingestion bursts

**Problem.** `max_storage_gb` is a column nobody checks. OCR is CPU-bound and unbounded — a 500-page PDF upload saturates the OCR pool.

**Fix.** Enforce storage quota at upload time (reject with 402, do not accept-then-fail). Page-count and file-size limits per plan. OCR admission control by tenant. Native-text PDF fast path (§3.3.3) removes most OCR load outright.

### 4.6 Contention point 6 — the rate limiter itself

**Problem.** [`rate_limiter.py`](../src/chat_api/services/rate_limiter.py) holds buckets in a process-local `defaultdict`. Two consequences: the effective limit is `limit × replica_count`, and buckets grow unboundedly since keys are never reaped. There is also a signature bug — the method is annotated `-> tuple[bool, int, int]` but returns a 4-tuple.

**Fix.** Replace with a Redis sliding-window or token-bucket limiter in `src/shared/`, applied at the gateway for *every* service rather than only `chat_api`. Keep the existing `X-RateLimit-*` header contract — it is correct and clients may already depend on it. Fix the annotation while touching the file.

### 4.7 Scalability

| Layer | Mechanism | Trigger |
|---|---|---|
| Stateless services (`gateway`, `chat_api`, `document_service`, `extraction_service`, `annotation_service`, `analytics_service`) | HPA on CPU + p95 latency, 2–10 replicas | CPU > 65% or p95 > SLO |
| `model_serving` | HPA 2–8, consistent-hash routed, node pool with more memory | Memory > 70% or inference p95 |
| Celery workers | KEDA on per-queue depth, 0–20 | Queue depth > 50 |
| GPU training | Ephemeral spot node pool, scale-to-zero | Job enqueued |
| Postgres | Vertical first, then read replicas, then tenant-group sharding | Connection or CPU saturation |
| Portal | Static + SSR on 2+ replicas behind Front Door | — |

Design the **tenant-group shard** boundary now even though it will not be used at 15 tenants: tenant → shard mapping lives in `public.tenants`, and no code may assume all tenants are in one database. Cheap now, near-impossible to retrofit.

### 4.8 High availability

| Concern | Target | Mechanism |
|---|---|---|
| Zone failure | Survive | AKS across 3 availability zones; zone-redundant Postgres and Redis |
| Pod failure | No user impact | ≥2 replicas of everything, PodDisruptionBudgets, readiness/liveness probes on all nine services |
| Region failure | Documented recovery, not automatic failover | Geo-redundant backups; runbook. Multi-region deferred per §2.3.9 |
| Data loss | RPO 15 min, RTO 4 hours | Postgres PITR, geo-redundant Blob, **quarterly restore drills** — an untested backup is not a backup |
| Deployment failure | Zero-downtime, fast rollback | Rolling updates, `helm rollback`, expand-contract migrations only |
| Dependency failure (Azure OpenAI) | Degrade, don't fail | Circuit breaker; on LLM outage return retrieved evidence without synthesis rather than erroring |

Because HA and multi-region were deferred: this plan commits to **no external SLA**. Internally we target 99.5% monthly availability, which single-region AKS with zone redundancy comfortably supports. Publishing 99.9% to clients requires the deferred multi-region work.

---

## 5. The Control Layer

A single cross-cutting layer every request traverses. This is the piece that turns the application into a platform, and it is the largest new build in this plan.

### 5.1 Components

**a. Identity and access**
- **Azure AD / Entra ID via OIDC** as the primary IdP, satisfying the SSO requirement. Per-tenant IdP configuration in `public.tenant_idp_config` so a client can federate their own directory.
- Keep the existing four roles (`system_admin`, `tenant_admin`, `annotator`, `business_user`) — confirmed sufficient, no ACLs.
- Retain local password auth as a break-glass path for `system_admin` only.
- Short-lived access tokens (15 min) with refresh tokens in Redis, enabling **session revocation** — currently impossible.
- Service-to-service auth on all `/internal/v1/*` endpoints (`model_serving`, warmup). These are currently unauthenticated and must not be reachable from outside the cluster.

**b. Metering**
Every metered event lands in a `public.usage_events` table (partitioned monthly), written asynchronously so metering never adds request latency:

```
tenant_id · user_id · event_type · resource · quantity · unit
· prompt_tokens · completion_tokens · model · cost_estimate_usd
· conversation_id · trace_id · occurred_at
```

Metered: LLM tokens (prompt/completion, per model), embedding tokens, chat messages, documents ingested, pages OCR'd, extraction runs, training jobs and GPU-minutes, storage bytes, API calls.

Per §2.3.7 this is **per-tenant, visibility-first** — but the grain is per-user and per-conversation because that costs nothing extra now and cannot be reconstructed later. Rolled up hourly into `usage_rollup_hourly` and daily for dashboards.

**c. Entitlements and quotas**
- Extend `public.tenants` with `plan_code`, and add `public.plan_entitlements` — a feature-flag and limit map per plan.
- A single `check_entitlement(tenant, feature)` / `consume_quota(tenant, resource, n)` pair in `src/shared/`, called from every enforcement point. One implementation, not scattered `if` statements.
- **Hard enforcement** per §2.3.8: HTTP 402 with a structured body naming the exceeded limit, its value, and the reset time.
- Quota state cached in Redis with write-through to Postgres, because it is on the hot path.

**d. Observability** — building from zero
- **Structured JSON logging** (`structlog`) with `tenant_id`, `user_id`, `trace_id`, `conversation_id` on every line. Never log document content or PII.
- **OpenTelemetry tracing** across all nine services. The chat graph already has a `_traced` decorator in [`nodes.py`](../src/chat_api/graph/nodes.py) — wire it to real OTel spans so every node's latency and token cost is visible per request. This is the highest-value observability work in the plan: it makes "why was this answer slow/wrong/expensive" answerable.
- **Prometheus metrics**: RED per endpoint, plus token spend, cache hit rate, queue depth, quota rejections, retriever timeouts — **all labelled by tenant**, with cardinality capped by label allowlist.
- **Grafana dashboards**: platform health, per-tenant consumption, LLM cost, pipeline quality.
- **Alerting** on SLO burn rate, quota exhaustion, LLM error rate, queue backlog, cache thrash.
- Azure Monitor + Log Analytics as the managed backend, so a 3-person team is not also running an observability stack.

**e. Admin console** (extends the existing system-admin portal area)
Tenant lifecycle, plan assignment, quota overrides, live usage and cost per tenant, capability profile assignment, feature-flag toggles, audit log search, training approval queue.

### 5.2 Deferred, and what we build anyway

Branding/white-labelling (§2.3.11) is deferred. The only accommodation made now: tenant-scoped configuration is a first-class table rather than environment config, so adding `theme`, `logo_url`, and custom domain later is additive.

---

## 6. Monetization and Licensing

Pricing and licensing model are deferred by decision (§2.3.11). What this plan delivers is the **machinery** so pricing becomes a configuration exercise rather than an engineering project.

**Built now:**
- Accurate, durable per-tenant usage records at per-user and per-conversation grain (§5.1.b).
- A plan/entitlement model (`plan_code` + `plan_entitlements`) with hard enforcement, so a "plan" is already a real, enforced object.
- Cost attribution — every LLM call carries a `cost_estimate_usd`, so gross margin per tenant is visible from day one. For an internal platform serving InApp's clients, this is the number leadership will actually ask for.
- An exportable monthly usage statement per tenant (CSV/JSON), which is a chargeback artefact whether or not it becomes an invoice.

**Deliberately not built:** payment processing, invoicing, subscription lifecycle, dunning, license keys, trial management. No billing provider is selected, and building against an unchosen provider is waste.

**Recommendation for the pricing phase.** Because token spend dominates marginal cost and varies 10× between tenants doing chat versus batch extraction, a pure per-seat model will lose money on heavy users. A base platform fee per tenant plus metered usage above an included allowance matches cost to revenue. The metering built here supports either model — that is the point of building it first.

---

## 7. Security Baseline

Compliance certification is deferred (§2.3.11); the controls below are the minimum for a platform holding clients' documents, and are chosen so certification later is an audit rather than a rebuild.

| Control | Action |
|---|---|
| Secrets | Azure Key Vault + workload identity. Remove all secrets from `.env`; `NER_OPENAI_API_KEY` rotated on migration since it has lived in plaintext |
| Transport | TLS everywhere including intra-cluster; Front Door + WAF at the edge |
| At rest | Azure-managed encryption on Postgres and Blob; CMK deferred |
| Tenant isolation | Automated test asserting cross-tenant access returns 403/404 for **every** endpoint — generated from the OpenAPI spec so new endpoints cannot skip it |
| Internal endpoints | `/internal/v1/*` reachable only in-cluster, with service auth. Currently open |
| Prompt injection | Extend [`guardrails.py`](../src/chat_api/services/guardrails.py): input scanning, output citation enforcement, and — most importantly — **no LLM output is ever executed**. The chart agent returns a spec, the SQL generator runs under a read-only role (`sql_execution_role_enabled`) with statement timeouts and an allowlisted schema |
| SQL generation | Read-only role, per-tenant schema scoping, query cost ceiling, no DDL/DML grants |
| File upload | MIME sniffing, size and page caps, ClamAV scan, never serve uploads from the app origin |
| Dependencies | Dependabot, `pip-audit`, Trivy image scanning in CI, signed images |
| Audit | Already implemented and retained; extend to cover capability-profile changes, quota overrides, and admin actions |
| RBAC | Centralised policy check in `src/shared/`, with a test matrix of every role × every endpoint |

With no security staff and three junior developers, **one external penetration test before general availability is a requirement, not a nice-to-have.** Budget ~$5–10k. Everything else above is achievable in-house with the tooling named.

---

## 8. Production Test Strategy

Current state: a pytest suite exists; no load, security, contract, or resilience testing; CI gates unverified.

### 8.1 Test pyramid and gates

| Layer | Scope | Gate |
|---|---|---|
| Unit | Services, capabilities, quota/entitlement logic | ≥70% on changed lines; ≥85% on `src/shared/` control-layer code |
| Contract | OpenAPI schema diffs across all nine services | Breaking change fails the build |
| Integration | Real Postgres + Redis + MinIO via testcontainers; full flows: upload→OCR→annotate→train→promote→extract→chat | Green on every PR |
| Tenant isolation | Generated from OpenAPI: every endpoint probed cross-tenant | Any leak fails the build, blocking |
| Golden-set evaluation | Per-chatbot Q&A fixtures (§3.3) | Regression below baseline blocks capability-profile changes |
| E2E | Playwright over the portal, per role | Nightly + pre-release |
| Load | §8.4 | Pre-release |
| Chaos | §8.5 | Pre-release |
| Security | §8.3 | Weekly scan; pentest pre-GA |

### 8.2 Environments

`local` (compose, as today) → `ci` (ephemeral, testcontainers) → `staging` (AKS, production-shaped, anonymised data, always-on) → `production`. Staging is currently missing and is a Phase 2 deliverable; without it there is nowhere to run load or chaos tests safely.

### 8.3 Security testing

- SAST (`bandit`, `semgrep`), dependency audit, container scanning (Trivy), secret scanning (`gitleaks`) — all in CI.
- DAST (OWASP ZAP) against staging weekly.
- **LLM-specific**: an OWASP LLM Top 10 test suite — prompt injection via uploaded document content (the highest-risk vector here, since documents are attacker-controlled text that enters the prompt), data exfiltration attempts, cross-tenant leakage through conversation state, SQL-generation escape attempts.
- External pentest before GA (§7).

### 8.4 Load and performance testing

Tooling: k6 for HTTP, Locust for mixed workloads, with a stubbed LLM for throughput runs and live Azure OpenAI for a smaller realistic run.

Targets, derived from the §2.4 scale assumption with 3× headroom:

| Scenario | Target |
|---|---|
| Chat, sustained | 30 concurrent conversations, p95 first-token < 2.5s, p95 complete < 8s |
| Chat, peak burst | 100 concurrent for 5 min, no 5xx, graceful 429 |
| Batch extraction | 500 documents, ≤ 30 min, **while chat p95 stays within SLO** |
| Ingestion | 200 concurrent uploads, OCR backlog drains < 15 min |
| Noisy-neighbour test | One tenant at 10× its quota **must not** move another tenant's p95 by more than 20% — this is the acceptance test for all of §4 |
| Soak | 24h at 50% load, no memory growth, no connection leaks |

The noisy-neighbour test is the single most important one in this plan. It is the difference between an application and a SaaS platform, and it is the test that would fail today.

### 8.5 Chaos and resilience

Kill pods under load; fail over Postgres; block Azure OpenAI (verify graceful degradation per §4.8); fill a disk; exhaust the Redis connection pool; saturate a tenant's quota mid-conversation. Run pre-release, quarterly thereafter.

### 8.6 Beta programme

Cohort selection is deferred (§2.3.11). The structure to be ready with:

- **Internal alpha** — the platform team plus one InApp team's real documents, 4 weeks. Exit: golden sets pass, no P1 bugs open.
- **Closed beta** — 2–3 InApp clients, 8 weeks, generous quotas, weekly feedback, all usage instrumented. Exit criteria: 99.5% availability over the period, p95 within SLO, zero isolation incidents, no P1 open, ≥80% of golden-set questions answered acceptably by the client's own judgement.
- **GA** — pentest closed, runbooks written, on-call rota defined, restore drill passed.

A note worth stating plainly: with 3 junior developers and no QA, on-call and incident response are a real gap. Before GA, define who is paged and what they do. The runbooks matter more than the tooling.

---

## 9. Phased Roadmap

Assumes 3 developers, no dedicated DevOps/QA/security. Estimates are calendar weeks with all three working, and include the learning curve on Azure, Kubernetes, and OpenTelemetry that this team will pay.

### Phase 1 — Foundations (Weeks 1–8)

*Goal: it deploys, and we can see what it does.*

| Work | Est. |
|---|---|
| Azure landing zone: subscription, VNet, AKS, Flexible Server + PgBouncer, Cache for Redis, Blob, ACR, Key Vault | 3w |
| Helm charts for all nine services + portal; expand-contract migration job | 2.5w |
| CI/CD: build, test, scan, deploy to staging on merge; production on tag | 1.5w |
| Secrets out of `.env` into Key Vault; rotate `NER_OPENAI_API_KEY` | 0.5w |
| Structured logging + OpenTelemetry across all services; wire the existing `_traced` decorator | 2w |
| Prometheus metrics + Grafana dashboards + first alerts | 1.5w |
| Postgres backups, PITR, first restore drill | 0.5w |
| Redis-backed rate limiter replacing the in-process one | 0.5w |

**Milestone:** staging environment running all services, traced and dashboarded, deployable from a git tag.

### Phase 2 — Control Layer (Weeks 9–16)

*Goal: we can see, attribute, and enforce per-tenant consumption.*

| Work | Est. |
|---|---|
| OIDC/Entra ID SSO, per-tenant IdP config, refresh tokens + revocation | 3w |
| `usage_events` schema, async metering writer, rollup jobs | 2w |
| Entitlements + plan model + hard quota enforcement (402 path) | 2w |
| Service-to-service auth on `/internal/v1/*` | 0.5w |
| Admin console: tenants, plans, quotas, usage, audit search | 3w |
| Centralised RBAC policy check + role × endpoint test matrix | 1w |
| Generated cross-tenant isolation test suite | 1w |

**Milestone:** every LLM token and document is attributed to a tenant; quotas block; SSO works.

### Phase 3 — Capability Plane and Chatbot Parity (Weeks 17–26)

*Goal: components are swappable, and the existing chatbots' use cases are reproduced.*

| Work | Est. |
|---|---|
| Capability protocols + registry; refactor existing retrievers/LLM/reranker onto them | 3w |
| Capability profiles (YAML + per-tenant overrides + versioning); config-driven graph topology | 2.5w |
| LLM broker: routing, interactive/batch queues, token buckets, budget enforcement, circuit breaker | 2w |
| Golden-set evaluation harness + fixtures captured from existing chatbots | 1.5w |
| Graph-RAG retriever (`entity_graph_edges` + `graph_walk`) | 2.5w |
| Chart agent (Vega-Lite spec output) + portal rendering | 2w |
| Multi-format ingestion registry: DOCX, XLSX/CSV, PPTX, HTML, EML, native-text PDF fast path | 3w |
| `model_serving` consistent-hash routing + per-tenant cache reservation | 1.5w |
| Celery queue split, per-tenant concurrency caps, KEDA autoscaling | 2w |
| Ephemeral GPU training node pool | 1w |

**Milestone:** internal alpha. Re-implemented chatbots pass their golden sets. Swapping the generation model is a config commit.

### Phase 4 — Hardening (Weeks 27–34)

*Goal: it survives load, failure, and attack.*

| Work | Est. |
|---|---|
| HA: multi-zone AKS, zone-redundant Postgres/Redis, PDBs, probes on all services | 1.5w |
| Read replica + analytics workload separation; statement timeouts by class | 1w |
| Load test suite (k6/Locust) and the noisy-neighbour acceptance test | 2w |
| Performance remediation from load results (reserve; expect HNSW indexes, N+1 queries, pool sizing) | 3w |
| Chaos suite + graceful LLM-outage degradation | 1.5w |
| Security: SAST/DAST/Trivy/gitleaks in CI, LLM Top 10 suite, ClamAV upload scanning | 2w |
| External penetration test + remediation | 3w |
| Runbooks, on-call rota, incident process, restore drill | 1.5w |

**Milestone:** load and chaos targets met, pentest findings closed.

### Phase 5 — Beta to GA (Weeks 35–40+)

Closed beta with 2–3 clients per §8.6, weekly iteration, GA exit criteria met. Pricing, licensing, branding, and multi-region enter planning here as separate workstreams once real usage data exists.

### Sequencing rationale

Observability before optimisation — you cannot fix contention you cannot measure. Control layer before capability plane — metering must exist before the LLM broker can enforce budgets. Both before load testing, because the noisy-neighbour test is meaningless until the mechanisms it tests are built.

---

## 10. Infrastructure Cost Model

Azure, Central India, single region, ~10–15 tenants. Monthly, USD, list prices — reserved instances cut compute 30–40%.

| Component | Configuration | Cost |
|---|---|---|
| AKS system + app node pool | 3 × `D4s_v5` | $420 |
| AKS memory pool (`model_serving`) | 2 × `E4s_v5` | $290 |
| GPU training pool | `NC4as_T4_v3` **spot**, ~60 h/mo, scale-to-zero | $30 |
| Postgres Flexible Server | GP `D4ds_v5`, 256 GB, zone-redundant HA | $520 |
| Postgres read replica | GP `D2ds_v5` | $140 |
| Azure Cache for Redis | Standard C1 | $75 |
| Blob Storage | 1 TB + geo-redundant backup | $45 |
| Container Registry | Standard | $20 |
| Front Door + WAF | Standard | $45 |
| Key Vault, Log Analytics, Monitor | ~40 GB logs/mo | $90 |
| **Subtotal, fixed** | | **~$1,675** |
| Azure OpenAI | 50k messages/mo, `gpt-4o` generation + `gpt-4o-mini` utility | $200–900 |
| Embeddings | `text-embedding-3-small`, 20k docs/mo | $15–40 |
| **Total** | | **~$1,900–2,600** |

Notes. Staging adds ~$400/month if kept always-on — recommended, and cheaper than the alternative of testing in production. Reserved instances plus scheduled staging shutdown brings the fixed subtotal to roughly $1,100. LLM spend is the only line that scales with tenants, which is exactly why §5.1.b meters it per tenant from day one.

The GPU line deserves emphasis given the no-budget constraint: spot T4 capacity at ~$0.15–0.30/hour makes on-demand training roughly $30/month at expected volume. The CPU-only fallback saves that $30 and costs 4–8 hours of wall clock per training job, which will become the bottleneck in the annotate→train→evaluate loop that tenants depend on. I recommend approving the GPU line.

---

## 11. Risks and Open Decisions

| Risk | Impact | Mitigation |
|---|---|---|
| **Team capacity.** 3 junior developers doing Azure, Kubernetes, OpenTelemetry, SSO, and a security programme simultaneously | High — the dominant risk in this plan | Phase strictly; buy managed services over self-hosted everywhere (Flexible Server not self-managed PG, Azure Monitor not self-hosted Prometheus); budget one external pentest; consider a part-time DevOps contractor for Phase 1 |
| **No QA or security resource** | Defects and vulnerabilities reach clients | Automated gates in CI as the substitute; blocking isolation tests; external pentest |
| Existing chatbots' behaviour is undocumented and their owners may be unavailable | Re-implementation misses use cases | Golden sets captured with owners in Phase 3, up front; treat owner availability as a scheduling dependency, not an assumption |
| NER model quality (open issue on v8: needs more and more varied training data) | Chatbot answers grounded on weak extraction | Out of scope by decision, but it caps answer quality. Track separately and visibly |
| LLM provider not confirmed | Rework if not Azure OpenAI | The `LLMAdapter` abstraction makes this a Phase 3 config change |
| Schema-per-tenant at scale | Migration time and catalogue bloat past ~200 tenants | Shard-aware tenant mapping designed in Phase 1; no code assumes a single database |
| Azure OpenAI TPM quota | Platform-wide throttling | Request quota increase early — lead times are real; separate interactive/batch deployments; circuit breaker |
| Cost overrun on LLM usage | Margin erosion | Hard per-tenant budgets from Phase 2; cost dashboards from Phase 1 |
| Deferred decisions (pricing, SLA, compliance, branding, multi-region) | Rework if they arrive late with strong constraints | Mechanisms built to be configurable; each deferral has a named reversal point in §2.4 |

**Decisions needed to start Phase 1:** Azure subscription and region confirmation; approval of the GPU spot line; whether staging runs always-on; confirmation that Azure OpenAI is the sanctioned provider.

**Decisions needed by Phase 3:** owner contacts for each existing chatbot; the list of file formats actually required, in priority order.

**Decisions needed by Phase 5:** pricing model, SLA commitment, beta cohort, compliance target.
