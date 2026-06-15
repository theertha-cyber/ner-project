## Why

Tenants need to annotate entities in their uploaded documents to produce training data for custom NER models. Currently the platform has ingestion (SM-02) but no annotation capability — documents sit in blob storage with no way for annotators to mark entities. SM-03 delivers the annotation workspace that SM-04 (Training) and SM-05 (Extraction) depend on.

## What Changes

- Create a new **Annotation Service** as a standalone FastAPI microservice at `src/annotation_service/`
- Pre-labeling pipeline that applies the base model's label mapping to generate candidate spans with confidence scores
- Span CRUD API — annotators can create, read, update, and delete entity spans on documents
- Annotation task management — split documents into annotator assignments with status tracking (unannotated → in-progress → completed)
- Annotation export API — emits tenant annotations in HuggingFace Dataset format (JSON lines with token-level BIO tags) for SM-04 training pipeline
- Reuse `src/shared/` utilities (config, database, auth, exceptions) — no duplication

## Capabilities

### New Capabilities

- `annotation-workspace`: Span-level annotation CRUD, pre-labeling with base label mapping, annotation task management, annotation export in HuggingFace Dataset format

### Modified Capabilities

- *(none — no existing specs to modify)*

## Impact

- **New service**: `src/annotation_service/` with its own FastAPI app, middleware, and dependencies
- **Database**: New tables in `tenant_template` schema for `annotation_tasks`, `spans`, `suggested_spans` (migration required)
- **Dependencies**: No heavy ML deps — pre-labeling is mocked for MVP (returns candidate spans from tenant label mapping without running a model)
- **Shared code**: Reuses `src/shared/config.py`, `src/shared/database.py`, `src/shared/auth.py`, `src/shared/exceptions.py`
- **Gateway impact**: No API changes — annotation service has its own FastAPI app; gateway will route to it in a future integration pass
- **Downstream**: SM-04 (Training Pipeline) imports the HuggingFace Dataset format exported here

## Open Questions

- Should pre-labeling run synchronously on upload or as a separate trigger? *(Assume: annotator triggers pre-labeling per document via POST endpoint; runs sync for MVP since it's a mock)*
- Should annotation tasks be auto-assigned to annotators or manually assigned by Tenant Admin? *(Assume: manually created by Tenant Admin via API for MVP)*
- Should multiple annotators be allowed on the same document simultaneously? *(Assume: no — a document assigned to one annotator is locked from others until completed)*
