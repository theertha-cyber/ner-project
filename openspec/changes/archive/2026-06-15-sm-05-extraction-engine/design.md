## Context

SM-01 through SM-04 provide tenant provisioning, document ingestion, annotation, and model training capabilities. Tenants can now upload documents, annotate spans, train a custom NER model, and promote a model version. However, there is no mechanism to run that model against documents to extract entities — the core value proposition of the platform.

The pre-staged `extraction_runs` and `extracted_entities` tables in `tenant_template` (migration 002) define the storage schema. ADR-003 mandates a shared model-serving pool with per-tenant routing and version pinning. The extraction service needs both real-time (single paragraph) and batch (existing documents) modes, with idempotency, confidence filtering, and a review/correction workflow.

## Goals / Non-Goals

**Goals:**

- New `src/model-serving/` FastAPI microservice — internal inference endpoint (`POST /internal/v1/tenants/{tid}/infer`) that loads the tenant's promoted ONNX model into an in-memory cache and runs token classification inference
- New `src/extraction-service/` FastAPI microservice — real-time extraction API (`POST /api/v1/tenants/{tid}/extract`), batch extraction trigger (`POST /api/v1/tenants/{tid}/extract-batch`), entity query/review API
- Celery async worker for batch extraction jobs (Redis broker, `extraction` queue)
- Entity storage in `extraction_runs` and `extracted_entities` tables
- Post-processing: confidence threshold filtering, entity deduplication within a run, validation rule hooks
- Entity review/correction API — list, filter, and patch extracted entities
- Model warmup on promotion — pre-load the newly promoted model into the serving cache
- Reuse `src/shared/` config, database, auth, exceptions, tenant context middleware

**Non-Goals:**

- ONNX Runtime GPU acceleration — MVP uses CPU inference (ONNX CPU provider). GPU support deferred.
- Hyperparameter optimization for extraction (confidence thresholds) — MVP uses a single configurable threshold
- Automated re-extraction on model promotion — MVP requires manual batch re-trigger
- Entity-level validation rules engine — MVP supports a simple hook interface; complex rules deferred to post-MVP
- Streaming extraction results — MVP uses polling for batch jobs

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | All extraction data stored in `tenant_{uuid}` schemas |
| ADR-002 | Single Curated Base Model Strategy | Models are fine-tuned from dslim/bert-base-NER; ONNX export uses the same tokenizer/config |
| ADR-003 | Model Serving Topology | Shared serving pool with per-tenant routing; internal inference endpoint; version pinning; model warmup on promotion; autoscale on P95 latency |
| ADR-005 | OpenCode Agent Boundaries | Agent may create new service directories and API endpoints following existing conventions |
| ADR-006 | Training Infrastructure | Model artifacts stored at `tenants/{tid}/models/v{version}/`; consumed by model-serving layer |

## Decisions

### Decision 1: Two Microservices (model-serving + extraction-service)

**Choice:** Split into two FastAPI microservices — `model-serving` (internal inference) and `extraction-service` (public-facing extraction APIs + batch worker).

**Rationale:** Model serving has a unique dependency profile (ONNX Runtime, transformers, torch = heavy) and scaling pattern (in-memory GPU/CPU cache, latency-sensitive). The extraction service handles business logic — entity validation, storage, review workflow — which has a lighter dependency profile. Separating them allows independent scaling: the model-serving pool can scale based on inference latency, while extraction-service scales based on extraction request volume. Gateway routes tenant-facing requests to extraction-service; only extraction-service calls model-serving internally.

**Alternatives considered:**
- Single extraction service with embedded model inference — couples heavy ML deps with CRUD logic; cannot scale inference independently
- Embed model inference in the gateway — violates gateway's responsibility as a thin routing layer; bloats gateway with ML deps

### Decision 2: ONNX Runtime for Inference (CPU)

**Choice:** Export trained PyTorch models to ONNX format and run inference via ONNX Runtime with CPU execution provider.

**Rationale:** ONNX Runtime provides 2-4x faster inference than raw PyTorch eager mode, smaller memory footprint, and a stable C++ inference engine. The training service (SM-04) already exports to ONNX as part of the model artifact pipeline. CPU inference avoids GPU contention during MVP — GPU resources are reserved for training jobs.

**Alternatives considered:**
- Raw PyTorch `model.forward()` — simpler integration but slower inference and higher memory per model instance
- ONNX with CUDA provider — deferred until GPU inference is needed for latency targets

### Decision 3: In-Memory Model Cache with LRU Eviction

**Choice:** Shared in-memory `dict[keyed by model_id]` cache with LRU eviction when memory exceeds configurable threshold (default: 2GB). Models loaded on first request for a tenant, evicted on inactivity (configurable TTL, default: 30 min).

**Rationale:** ADR-003 mandates shared model pool. In-memory dict is the simplest correct implementation for MVP — no external cache service, no serialization overhead. LRU eviction with a memory threshold prevents OOM under load. Warmup on promotion (SM-04 `ModelPromoted` event → pre-load model) mitigates cold-start latency for newly promoted models.

**Alternatives considered:**
- Redis-backed model cache — adds serialization/deserialization overhead for large model weights; no benefit for single-node MVP
- Filesystem cache with mmap — more complex; premature optimization for MVP

### Decision 4: Redis Broker for Batch Extraction (Celery)

**Choice:** Reuse the existing Redis-backed Celery infrastructure (same as SM-04) with a dedicated `extraction` queue for batch jobs.

**Rationale:** The project already has Redis running and Celery configured with `--pool=solo` for Windows. Adding a separate queue avoids head-of-line blocking between training and extraction jobs. The extraction worker shares the same `celery_app` configuration from `src.shared.celery_app` (or equivalent).

**Alternatives considered:**
- RabbitMQ per ADR-006 — deferred for same reasons as SM-04 (operational overhead for MVP)
- In-process batch processing — blocks the API process for long-running extraction runs

### Decision 5: Idempotent Batch Extraction

**Choice:** Batch extraction skips documents that have already been extracted with the current active model version. Each document is checked against `extraction_runs` before processing. Re-extraction requires a new batch trigger after model promotion.

**Rationale:** Ensures idempotency — re-triggering a batch job for the same model version does not duplicate entities. This matches the decomposition doc's requirement that "entities extracted with a superseded model version remain in the database."

**Alternatives considered:**
- Always re-extract — violates idempotency; duplicates entities on retry
- Delete-and-reinsert — loses audit trail of which model version extracted which entity

## Risks / Trade-offs

- [Cold-start latency on first extraction request for a tenant] → Model warmup on promotion; loading spinner / queued status for first request
- [In-memory cache OOM with many tenants] → LRU eviction with configurable memory threshold; per-model memory tracking
- [ONNX export mismatch between training and serving] → Validate ONNX export during training (SM-04 already does this); version the ONNX opset in model metadata
- [CPU inference too slow for real-time extraction] → Target <500ms per paragraph; if violated, add GPU execution provider path
- [Batch extraction conflicts with concurrent re-extraction] → Lock document-level extraction runs; skip if another run is in progress

## Migration Plan

1. Create `src/model-serving/` — FastAPI scaffolding, model cache, inference endpoint
2. Create `src/extraction-service/` — FastAPI scaffolding, real-time extraction API, entity CRUD API
3. Implement Celery batch extraction worker in extraction-service
4. Add model warmup: consume `ModelPromoted` event → pre-load model in serving cache
5. Wire gateway routes for extraction-service endpoints
6. Add extraction-service router to gateway (unlike training-service which was skipped, extraction needs gateway routing for tenant context enforcement)
7. Manual test: trigger batch extraction on a tenant with a promoted model

Rollback: Remove gateway routes, stop extraction-service and model-serving containers; extracted entities remain in database and can be queried directly if needed.

## Open Questions

- Should pre-labeling in SM-03 be re-pointed to extraction-service instead of the current keyword-based approach? (Would make pre-labeling match runtime extraction quality.)
- What is the default confidence threshold? (Proposed 0.50 for MVP, configurable per-tenant in future.)
- Should entity query API support pagination beyond the MVP cursor? (Proposed: offset/limit pagination for MVP.)
