## Context

SM-01 through SM-03 provide tenant provisioning, document ingestion, and annotation capabilities. Tenants can now configure entity types, upload documents, and annotate spans. However, the platform has no mechanism to train a custom NER model from those annotations — without which the automated extraction (SM-05) and downstream capabilities (SM-06, SM-07) cannot function.

The training pipeline bridges annotation (SM-03) and extraction (SM-05). It accepts tenant-annotated data in HuggingFace Dataset format, fine-tunes dslim/bert-base-NER via the HuggingFace `Trainer` API, versions the resulting model, and makes it available for promotion to production.

## Goals / Non-Goals

**Goals:**
- Standalone microservice at `src/training_service/` housing the API layer and Celery task definitions
- Training job API — submit (with hyperparameters), list, get status, cancel
- Async GPU training via Celery worker (Redis broker for MVP)
- HuggingFace `Trainer` fine-tuning using tenant's annotated spans as BIO tags
- Model registry — list versions, promote/demote to/from production, query active model
- Model artifacts stored in blob storage at `tenants/{tid}/models/v{version}/`
- Enforce 500-entity minimum dataset threshold before training
- Tenant-scoped data isolation (schema-per-tenant pattern)
- Reuse `src/shared/` config, database, auth, exceptions

**Non-Goals:**
- Real GPU orchestration with K8s node pools (MVP uses Celery worker on CPU with enough memory; GPU acceleration deferred)
- Hyperparameter sweep / Optuna integration — deferred to post-MVP
- Training progress streaming via WebSocket — MVP uses polling
- Automated re-training on new annotations — MVP requires manual trigger
- Model evaluation beyond built-in Trainer metrics (precision, recall, F1 per epoch)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | All training data (jobs, model versions) stored in `tenant_{uuid}` schemas |
| ADR-002 | Single Curated Base Model Strategy | Fine-tuning only dslim/bert-base-NER; no BYOM |
| ADR-003 | Model Serving Topology | Promoted model artifacts must be loadable by a shared in-memory pool (SM-05); versioned blob path convention `tenants/{tid}/models/v{version}/` |
| ADR-005 | OpenCode Agent Boundaries | Agent may create new service directories and API endpoints following existing conventions |
| ADR-006 | Training Infrastructure | Celery-based async GPU workers; 500-entity minimum; training artifacts at `s3://ner-platform/tenant-<uuid>/models/v<version>/` |

## Decisions

### Decision 1: Standalone Microservice

**Choice:** New FastAPI microservice at `src/training_service/` following SM-02/SM-03 directory conventions.

**Rationale:** Training has a unique dependency profile (torch, transformers, datasets = ~2GB) and scaling characteristics (burst-y GPU jobs) that differ from the gateway, document service, and annotation service. Keeping it isolated avoids bloating other services with ML dependencies.

**Alternatives considered:**
- Extending the annotation service — ruled out because training adds ~2GB of ML deps that have nothing to do with annotation; couples deployment cycles
- Gateway extension — ruled out for the same reasons plus the gateway should remain a thin auth/routing layer

### Decision 2: Redis Broker for MVP (Celery)

**Choice:** Use Redis as the Celery message broker (instead of RabbitMQ from ADR-006). The existing `pyproject.toml` already lists `redis` as a dependency. The worker module is structured identically regardless of broker — only the Celery config string changes.

**Rationale:** RabbitMQ adds operational complexity (another service to run in Docker, management UI, queue management). Redis is already available in the project dependencies and provides equivalent functionality for the MVP (single queue, no complex routing). Switch to RabbitMQ post-MVP when multiple queues (OCR, training, batch extraction) require routing and priority.

**Alternatives considered:**
- RabbitMQ — ADR-006 compliant but adds operational overhead for MVP; deferred
- In-process training — ruled out because training blocks the API process for minutes/hours

### Decision 3: CPU Training for Local Dev (GPU Optional)

**Choice:** The Celery worker defaults to CPU training with `device="cpu"`. GPU support is configurable via `TRAINING_DEVICE=cuda` env var.

**Rationale:** Most developers don't have a local GPU. CPU training is slow but functional for small datasets (100-500 documents at seq_len 128). GPU acceleration is a config change when deploying to K8s GPU node pools.

**Alternatives considered:**
- Require GPU — blocks local development entirely
- Cloud-only training (no local mode) — prevents offline testing and CI integration

### Decision 4: Polling-Based Job Status (no WebSocket)

**Choice:** Training job status is polled via `GET /api/v1/training-jobs/{id}`. No WebSocket streaming for MVP.

**Rationale:** Reduces implementation complexity. Training runs for minutes/hours, not sub-second — polling every 5-10 seconds is sufficient. Status updates are persisted to DB by the Celery worker via result backend.

**Alternatives considered:**
- WebSocket streaming — adds complexity (connection management, auth, reconnection); deferred
- Server-Sent Events — simpler than WebSocket but still adds persistent connection overhead; deferred

### Decision 5: HuggingFace Dataset Loaded from Annotation Service Export

**Choice:** The Celery worker fetches annotated data by calling the annotation service's `GET /api/v1/annotation-export` endpoint and loads it via `datasets.Dataset.from_json(lines=...)`.

**Rationale:** The annotation export endpoint already produces the correct format (JSON lines with `tokens` + `tags`). This avoids duplicating the export logic in the training service. The worker authenticates via a service-to-service JWT.

**Alternatives considered:**
- Direct DB query — would duplicate the export logic; coupling training to the annotation schema directly
- Shared file export — adds a file-based handoff step; unnecessary for MVP

### Decision 6: Database Tables in tenant_template Schema

**Choice:** `training_jobs` and `model_versions` tables are created in the `tenant_template` schema via an Alembic migration (005), consistent with SM-01→SM-03 pattern.

**Rationale:** Keeps the tenant schema pattern consistent. New tenants created after migration 005 automatically get these tables. Existing tenants are synced via `scripts/migrate_existing_tenants.py`.

**Alternatives considered:**
- Global `public` tables with `tenant_id` column — violates ADR-001's schema-per-tenant isolation

## Risks / Trade-offs

- [**GPU not available in dev**] → CPU fallback with `device="cpu"` flag; slow but functional for small datasets
- [**Training job takes hours**] → Polling status endpoint; results persisted to DB; worker reports progress via Celery's `current_task.update_state()`
- [**Model artifact storage grows unbounded**] → MVP stores all versions; post-MVP add retention policy (keep last N versions, delete intermediate checkpoints)
- [**Annotation export format changes in SM-03**] → Training spec declares the expected JSONL schema as a contract; any SM-03 changes to export format require a coordinated release
- [**Redis broker unreachable**] → Training job submission fails immediately with 503; jobs in-flight survive worker restart if Celery acks_late=True
- [**Worker crashes mid-training**] → Checkpointing at each epoch (ADR-006); failed job can be retried from last checkpoint via a new API call

## Migration Plan

1. Apply Alembic migration 005 to create `training_jobs` and `model_versions` in `tenant_template`
2. Run `scripts/migrate_existing_tenants.py` to sync existing tenant schemas
3. Deploy `src/training_service/` — FastAPI app with Celery worker process
4. Start Redis in Docker (`docker compose up -d redis`)
5. No migration of existing data — this is a greenfield capability

**Rollback:** Remove `src/training_service/`, revert migration 005, stop Redis.

## Open Questions

1. ~~**Service-to-service auth:** Should the training worker use a long-lived service JWT or mutual TLS to call the annotation export endpoint?~~ → **Resolved by Decision 5**: service-to-service JWT (long-lived, scoped to `training-service`).
2. **Base model download:** dslim/bert-base-NER is ~400MB. Should it be pre-downloaded in the Docker image or downloaded at worker startup and cached?
3. **Training timeout:** What's the maximum training job duration before auto-fail? 2 hours (ADR-006)? 24 hours?
