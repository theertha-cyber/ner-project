# PROJECT.md — Multi-Tenant Custom Named Entity Recognition Platform

> **Single source of project-specific context for every agent session.**

---

## [REQUIRED] 1. Project Overview

**Name**: Multi-Tenant Custom Named Entity Recognition Platform
**Purpose**: A multi-tenant document intelligence platform where each tenant can define domain-specific named entities, train a tenant-specific NER model, deploy that model in an isolated runtime, and use extracted structured data for workflows, reporting, and agentic conversations. Delivery is AI-native: OpenSpec governs requirements/design/tasks/evidence as the source of truth; OpenCode is the agentic engineering interface for planning, implementation, review, and validation under human approval gates.
**Stage**: Greenfield
**Team size**: 1-3

---

## [REQUIRED] 2. Tech Stack

| Layer | Technology | Version |
|---|---|---|---|
| Language(s) | Python, TypeScript | Python 3.12+, Node.js 22 LTS |
| ML framework | PyTorch + Hugging Face Transformers | PyTorch 2.x |
| Base NER model | dslim/bert-base-NER | Latest |
| Web framework (backend) | FastAPI | Latest |
| Web framework (frontend) | React / Next.js (App Router) | Latest |
| ORM / query builder | SQLAlchemy | Latest |
| Primary database | PostgreSQL + pgvector | 16 |
| Object storage | MinIO (dev) → S3 (prod) | Latest (MinIO) |
| Search / vector index | pgvector (in-DB) | Bundled with PG 16 |
| Cache | Redis | 7 |
| Message broker | RabbitMQ | Latest |
| Test framework | pytest (Python), Vitest (TS) | Latest |
| Lint / format | ruff (Python), ESLint + Prettier (TS) | Latest |
| Container runtime | Docker + Kubernetes | Latest |
| Infrastructure-as-code | Terraform | Latest |
| CI/CD | GitHub Actions | Latest |
| Observability (metrics) | Prometheus | Latest |
| Observability (tracing) | OpenTelemetry + Jaeger | Latest |
| Observability (logging) | JSON structured logs | — |
| OCR | Tesseract | Latest |

---

## [REQUIRED] 3. Repository Structure

```
ner-project/
├── src/
│   ├── portal/              ← Web/admin portal (React/Next.js frontend)
│   ├── gateway/             ← API gateway and backend (FastAPI)
│   ├── document-service/    ← Document processing, OCR, text extraction
│   ├── annotation-service/  ← Label task management, pre-labeling, dataset export
│   ├── training-orchestrator/ ← Training job creation, GPU worker management
│   ├── model-registry/      ← Model versioning, metrics, approval, artifact URI
│   ├── model-serving/       ← Per-tenant model endpoint/serving layer
│   ├── extraction-service/  ← Runtime extraction with post-processing & validation
│   ├── analytics-chatbot/   ← SQL/reporting, RAG/agent tools over extracted data
│   └── shared/              ← Shared types, utilities, base classes, tenant context
│   tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
│   openspec/
│   ├── project.md           ← OpenSpec project context
│   ├── specs/               ← Durable source-of-truth feature specs
│   └── changes/             ← Change packages (proposal, design, spec, tasks, evidence)
│   docs/
│   ├── adr/                 ← Architecture Decision Records
│   ├── workflow/            ← SDD pipeline, skills catalog, OpenSpec artifacts
│   ├── architecture/        ← Microservice patterns, ADR discipline
│   ├── standards/           ← Coding standards, commit conventions
│   └── agents/              ← Context hygiene, guardrails
│   .opencode/
│   ├── agents/              ← OpenCode role definitions
│   ├── skills/              ← OpenCode skills
│   └── commands/            ← Custom OpenCode commands
│   .claude/
│   ├── skills/              ← Legacy Claude skills (migrating to .opencode/)
│   └── commands/            ← Legacy Claude commands
```

**Monorepo**: Yes
**Package manager**: npm (frontend), pip/uv (Python)
**Workspace tool**: None (separate service directories)

---

## [REQUIRED] 4. Service Topology

| Service | Responsibility | Data Store | Publishes Events | Consumes Events | Sync Callers |
|---|---|---|---|---|---|
| API Gateway & Backend | Tenant-aware authz, orchestration, validation, audit logging, async job submission | PostgreSQL (metadata) | DocumentUploaded, TrainingRequested | ExtractionCompleted | Portal UI |
| Document Processing Service | File validation, malware scan, OCR, text extraction, chunking, tokenization, layout metadata | Object storage, PostgreSQL (spans) | DocumentProcessed | DocumentUploaded | — |
| Annotation Service | Label task management, pre-labeling, reviewer workflow, BIO/IOB2 dataset export | PostgreSQL (annotations) | DatasetApproved | DocumentProcessed | Portal UI |
| Training Orchestrator | Creates tenant training jobs, records lineage, manages GPU workers, persists metrics | PostgreSQL (jobs), Object storage (artifacts) | ModelTrained, TrainingFailed | DatasetApproved | — |
| Model Registry | Stores base model reference, tenant model versions, metrics, approval, artifact URI | PostgreSQL (registry), Object storage (model artifacts) | ModelPromoted | ModelTrained | Portal UI |
| Model Serving Layer | Per-tenant endpoint/service with version pinning, autoscaling, warmup | In-memory model cache | — | ModelPromoted | Extraction Service |
| Extraction Service | Runs active model, post-processing, validation, stores entities and normalized records | PostgreSQL (extracted entities) | ExtractionCompleted | DocumentUploaded | — |
| Analytics & Chatbot | SQL/reporting, semantic search (where needed), RAG/agent tools constrained to tenant data | PostgreSQL, Vector index | — | ExtractionCompleted | Portal UI |

**Communication style**: Async-first (event-driven via message broker); sync calls for UI-facing CRUD
**Service discovery**: Kubernetes DNS / API gateway routing

---

## [REQUIRED] 5. Architecture Decision Records

All ADRs are located in `docs/adr/` in Markdown Any Decision Records (MADR) format.

| ADR | Title | Status | Summary |
|---|---|---|---|
| ADR-001 | [Tenant Data Isolation via Separate Database Schemas](docs/adr/001-tenant-data-isolation.md) | Proposed | Separate PostgreSQL schemas per tenant with `search_path` enforcement, prefix-based object storage isolation. |
| ADR-002 | [Single Curated Base Model Strategy (No BYOM)](docs/adr/002-base-model-strategy.md) | Proposed | All tenants fine-tune from dslim/bert-base-NER. No bring-your-own-model. |
| ADR-003 | [Per-Tenant Model Serving Topology](docs/adr/003-model-serving-topology.md) | Proposed | Shared serving pool with tenant-aware routing, version pinning, on-demand model loading, path to dedicated pods. |
| ADR-004 | [OpenSpec Spec-Driven Development Governance](docs/adr/004-openspec-governance.md) | Proposed | Mandatory gates: proposal → design → spec → tasks → evidence → archive. Exceptions for trivial changes. |
| ADR-005 | [OpenCode Agent Permissions and Boundaries](docs/adr/005-opencode-agent-boundaries.md) | Proposed | Role-specific agents with bounded tool access, human approval gates, audit logging of agent actions. |
| ADR-006 | [Training Infrastructure with Asynchronous GPU Workers](docs/adr/006-training-infrastructure.md) | Proposed | Celery + RabbitMQ async workers on K8s GPU node pools. Scale-to-zero, checkpoint-based resume. |
| ADR-007 | [Chatbot Architecture with Full RAG and Guardrails](docs/adr/007-chatbot-architecture.md) | Proposed | Three-source RAG (SQL + pgvector + NER). SQL validation layer, source citation enforcement, disclaimer. |

---

## [REQUIRED] 6. Infrastructure Available

### Message Broker
- **Type**: RabbitMQ
- **Topics/queues naming convention**: `<tenant_id>.<service>.<event>` in snake_case
- **Delivery guarantee**: at-least-once
- **Outbox relay**: needs to be built

### Cache
- **Type**: Redis 7
- **Cluster or standalone**: standalone (evaluating cluster for production)
- **Client library**: redis-py
- **Key namespace convention**: `<tenant_id>:<entity>:<id>`
- **Default TTL policy**: 5m (configurable per use case)

### Database
- **Type**: PostgreSQL 16
- **Connection pooling**: PgBouncer
- **Migration tool**: Alembic (Python), Prisma (Node.js services)
- **Schema-per-service**: Yes (logical schema separation within shared cluster for MVP; dedicated DB instances per service in production)

### Secret Management
- **Tool**: HashiCorp Vault
- **Convention**: Secrets injected as environment variables via Kubernetes Secrets / External Secrets Operator

### Feature Flags
- **Tool**: Unleash
- **How to gate new features**: Feature flags for per-tenant rollout of model versions and extraction pipeline changes

---

## [REQUIRED] 7. Resilience Defaults

| Pattern | Default Configuration |
|---|---|
| HTTP connect timeout | 5s |
| HTTP read timeout | 30s |
| DB query timeout | 10s |
| Retry count | 3 |
| Retry backoff | exponential, base 200ms, max 10s, jitter |
| Non-retryable HTTP status codes | 400, 401, 403, 404, 422 |
| Circuit breaker threshold | 10 errors in 30s window |
| Circuit breaker recovery window | 60s half-open probe |
| Circuit breaker fallback | return 503 with retry-after header |
| Idempotency TTL | 24h (for document upload and extraction requests) |

---

## [REQUIRED] 8. Observability Standards

**Metrics system**: Prometheus
**Tracing**: OpenTelemetry + Jaeger (or equivalent)
**Log format**: JSON structured
**Correlation ID header**: `X-Request-ID` (propagated across all services)
**Log levels used**: error (failures requiring human intervention), warn (degraded but handled), info (state transitions, job lifecycle), debug (trace-level detail, off in production)

Required signals per pattern:

| Pattern | Required Metric / Log / Trace |
|---|---|
| Retries | `retry_count` counter, labelled by operation and outcome |
| Circuit Breaker | `circuit_state` gauge (0=closed, 1=open, 0.5=half-open) |
| Cache | `cache_hit_total` and `cache_miss_total` counters, labelled by entity |
| Outbox | `outbox_pending_count` gauge, `outbox_relay_lag_seconds` histogram |
| Saga | Log entry per step with: saga_id, step_name, status, duration |
| Training | `training_duration_seconds` histogram, `model_f1_score` gauge, labelled by tenant and model version |
| Extraction | `extraction_latency_seconds` histogram, `extraction_confidence` gauge, labelled by tenant and entity type |

---

## [RECOMMENDED] 9. Coding Conventions

### Naming
- **Files**: snake_case (Python), kebab-case (TypeScript/React)
- **Classes**: PascalCase
- **Functions/methods**: snake_case (Python), camelCase (TypeScript)
- **DB tables**: snake_case plural (e.g. `entity_definitions`, `extracted_entities`)
- **Events**: PascalCase with past tense (e.g. `DocumentProcessed`, `ModelPromoted`)
- **Environment variables**: UPPER_SNAKE_CASE
- **API routes**: kebab-case (e.g. `/api/v1/tenants/{tenant_id}/documents`)

### Error handling
- **Error base class**: `AppError` extends `Exception` (Python), `AppError` extends `Error` (TS)
- **HTTP error response schema**: `{ "error": { "code": "string", "message": "string", "request_id": "string" } }`
- **Transient vs permanent error classification**: Transient errors are retryable (5xx, network timeouts); permanent errors (4xx, validation failures) are not retried

### Dependency injection
- **DI container**: FastAPI built-in dependency injection (Python), Next.js built-in / React context + custom hooks (TypeScript)
- **Registration location**: Per-service `main.py` or `app.py`

### API design
- **Style**: REST (primary) with gRPC evaluated for inter-service communication
- **Versioning**: URL path (`/api/v1/`)
- **Auth**: JWT Bearer tokens with tenant context embedded
- **Pagination**: cursor-based for lists; offset-based for small datasets
- **Error codes**: Defined per service, returned in error response body

### Test conventions
- **Test file location**: Co-located `tests/` directory per service
- **Test file naming**: `test_<module>.py` (Python), `<module>.test.ts` (TypeScript)
- **Mock library**: pytest-mock (Python), vi.mock / Vitest (TypeScript)
- **DB test strategy**: Testcontainers for integration tests
- **Factory/fixture tool**: factory_boy (Python), fishery (TypeScript)

---

## [RECOMMENDED] 10. Build, Run, and Test Commands

> TBD — project is greenfield. Once the initial service scaffolding is created, populate this section with actual commands.

```bash
# Install dependencies
# Python: uv pip install -e "src/<service>[dev]"
# TypeScript: npm install --workspaces

# Start in development mode
# docker compose up -d    (for local dependencies: DB, broker, cache)
# uvicorn src.<service>.main:app --reload
# npm run dev --workspace=<service>

# Run all tests
# pytest
# npm test --workspaces

# Lint
# ruff check src/
# npm run lint

# Format
# ruff format src/
# npm run format

# Build for production
# docker build -f src/<service>/Dockerfile -t <image> .

# Run DB migrations
# alembic upgrade head

# Seed the database
# alembic seed  (Alembic seed scripts using factory_boy)
```

---

## [RECOMMENDED] 11. Environment Setup

**Required environment variables**: TBD (will be documented in `.env.example` per service)
**Local infrastructure**: Docker Compose (PostgreSQL, Redis, MinIO, message broker)

```bash
# How to spin up local dependencies (DB, broker, cache, etc.)
# docker compose up -d
```

**Known setup gotchas**: TBD

---

## [RECOMMENDED] 12. Per-Service Overrides

> TBD — populate as service implementations reveal deviations from defaults.

### Service: Model Serving Layer
- **Resilience overrides**: Lower connect timeout (2s) for inference requests; higher retry count (5) for cold-start model loading
- **Cache TTL overrides**: Model artifacts cached indefinitely until version change

### Service: Training Orchestrator
- **Resilience overrides**: DB query timeout 30s (long-running status polls); no circuit breaker for job submission (manual intervention preferred)
- **Non-standard patterns**: GPU queue with backpressure (tracked via ADR)

---

## 13. Changelog

| Date | Change | Author |
|---|---|---|
| 2026-06-03 | Initial PROJECT.md created from PRD v0.2 and template | OpenCode |
| 2026-06-04 | Updated ADR section with 7 finalized ADRs (ADR-001 through ADR-007) linked to docs/adr/ | OpenCode |
| 2026-06-04 | Resolved open decisions: team size (1-3), pgvector, RabbitMQ, Terraform, Tesseract, Vault, Unleash, Next.js built-in DI. Updated §1, §2, §6, §9 accordingly. | OpenCode |
| 2026-06-04 | Resolved remaining TBDs: latest stable versions for all packages, redis-py, Prisma for Node.js migrations, Alembic seeds + factory_boy for DB seeding. | OpenCode |
