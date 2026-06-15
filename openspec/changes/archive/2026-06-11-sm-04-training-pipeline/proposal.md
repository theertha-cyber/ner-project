## Why

SM-03 provides annotated documents in HuggingFace Dataset format, but annotated data is useless without a model. SM-04 closes the loop by fine-tuning dslim/bert-base-NER on each tenant's annotated spans, producing a tenant-specific model that can be promoted to production for automated extraction. Without SM-04, the platform cannot deliver its core value proposition: custom NER extraction at scale.

## What Changes

- **New Training Orchestrator** — a Celery-based async GPU worker pool that receives training jobs, runs HuggingFace `Trainer` with BIO-tagged tenant data, and persists model artifacts
- **Training Job API** — submit, list, cancel, and monitor training jobs per tenant
- **Model Registry API** — list model versions, promote a version to production, query active model version
- **Training Job Status Tracking** — state machine (queued → running → completed/failed) with progress and metrics
- **Model Artifact Storage** — versioned model binaries in blob storage at `tenants/{tid}/models/v{version}/`
- **Training Pipeline Service** — standalone microservice at `src/training_service/` housing the API layer and Celery task definitions

## Capabilities

### New Capabilities

- `training-jobs`: Training job submission, status query, cancellation, and listing. Enforces 500-entity minimum dataset threshold.
- `model-registry`: Per-tenant model version listing, promotion/demotion of versions to/from production, active model query.
- `training-worker`: Celery task that loads tenant's Dataset from the export endpoint, initialises HuggingFace `Trainer` with tenant-specified hyperparameters, fine-tunes the base model, and persists artifacts.

### Modified Capabilities

- None — this is a greenfield capability.

## Impact

- **New microservice:** `src/training_service/` — FastAPI app with Celery integration, following SM-02/SM-03 conventions
- **New dependency:** Celery + RabbitMQ (or Redis broker for MVP) — adds operational surface area
- **New dependency:** `torch`, `transformers`, `datasets`, `evaluate` — Python ML stack (~2GB)
- **Blob storage:** New path convention `tenants/{tid}/models/v{version}/` for model artifacts
- **Database:** New tables in `tenant_template` schema — `training_jobs` (status, hyperparams, metrics, artifact_path) and `model_versions` (version_number, status, training_job_id, artifact_path, promoted_at)
- **SM-03 export contract:** Training worker fetches tenant's annotated data from `GET /api/v1/annotation-export` and ingests via `datasets.Dataset.from_json()`

## Open Questions

1. **Broker choice for MVP:** Should we use Redis (simpler setup, already in pyproject.toml deps) or RabbitMQ (as specified in ADR-006)? RabbitMQ is the ADR decision but adds operational overhead for local dev.
Answer - RabbitMQ
2. **GPU access for local dev:** Training won't work on a laptop without a GPU. Should the MVP worker support CPU fallback (slow but testable)?
Answer - keep fallback
3. **Training trigger:** Should training be triggered automatically when annotation tasks are completed, or only manually via API?
Answer - manually
