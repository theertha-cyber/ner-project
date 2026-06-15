## Why

SM-04 (Training Pipeline) produces fine-tuned NER models, but there is no mechanism to run those models against tenant documents to extract entities. SM-05 bridges that gap — it loads the tenant's promoted model, runs inference on document text (both real-time and batch), stores extracted entities in the database, and provides APIs to query, review, and correct extraction results. Without SM-05, model training produces artifacts that cannot be consumed, and the platform cannot fulfill its core value proposition of automated entity extraction from documents.

## What Changes

- New **Model Serving Layer** — shared in-memory pool of loaded ONNX models with per-tenant routing (per ADR-003). Loads the tenant's promoted model on first request, caches in memory, evicts on inactivity.
- New **Real-time Extraction API** — `POST /api/v1/tenants/{tid}/extract` accepts a text paragraph and returns extracted entities with confidence scores.
- New **Batch Extraction Engine** — Celery async job that processes documents already in `processed` status, skipping those already extracted with the current active model version (idempotent).
- New **Extracted Entity Storage** — persists extracted entities to the pre-staged `extraction_runs` and `extracted_entities` tables, linked to source document spans and model version.
- New **Entity Query & Review API** — `GET /api/v1/tenants/{tid}/entities` with filters for document, entity type, and review status; `PATCH` endpoint to correct/review entities.
- New **Post-Processing Validation** — configurable confidence threshold filtering and entity-level validation rules.

## Capabilities

### New Capabilities

- `extraction-service`: Real-time and batch entity extraction using the tenant's promoted model; entity storage, querying, review, and correction; post-processing validation and confidence filtering.
- `model-serving`: Shared in-memory model pool with per-tenant routing, on-demand loading, caching, and eviction; exposes internal inference endpoint consumed by extraction-service.

### Modified Capabilities

- *(none — this is the first extraction-related capability)*

## Impact

- **New services**: `src/model-serving/` (internal inference service), `src/extraction-service/` (public-facing extraction API + Celery worker)
- **Database**: Pre-staged tables `extraction_runs` and `extracted_entities` (migration 002) serve as the schema — no new migrations needed for MVP
- **Dependencies**: ONNX Runtime (model inference), transformers (tokenizer), torch (tensor ops)
- **Config**: `.env` entries for model-serving port, extraction Celery queue name, confidence thresholds
- **Downstream**: SM-06 (Chatbot) and SM-07 (Reports) consume extracted entities from this service

## Open Questions

- What confidence threshold should be applied by default? (Proposed: 0.50)
- Should pre-labeling (SM-03) be replaced by extraction-service inference for annotation pre-labeling?
- Are entity-level validation rules defined per entity type in SM-01 configuration, or as hardcoded rules in extraction-service?
