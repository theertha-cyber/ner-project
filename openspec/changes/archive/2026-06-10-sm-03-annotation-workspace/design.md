## Context

SM-02 delivered a document ingestion service that stores uploaded documents in MinIO, runs async OCR, and persists text spans in tenant-scoped PostgreSQL schemas. Documents now exist in `processed` status with extractable text, but there is no mechanism for human annotators to label entities within that text.

The annotation workspace is Wave 3 of the platform build sequence (SM-01 → SM-02 → SM-03 → ...). Entity types are already configured (SM-01) and documents are ingested with OCR text (SM-02); SM-03 bridges the gap between raw text and training-ready annotated data.

## Goals / Non-Goals

**Goals:**
- Standalone annotation microservice at `src/annotation_service/` following SM-02 patterns
- Span-level CRUD API — annotators create, read, update, delete entity spans on document text
- Pre-labeling that generates candidate spans from the tenant's entity type label mapping (mocked for MVP — no model inference)
- Annotation task management — create tasks assigning documents to annotators with status lifecycle
- Annotation export in HuggingFace Dataset format (JSON lines, token-level BIO tags) for SM-04
- Tenant context enforcement via JWT (same pattern as SM-02 middleware)
- Reuse `src/shared/` config, database, auth, exceptions

**Non-Goals:**
- Real ML model inference for pre-labeling (mocked — returns predefined candidate spans)
- Real-time collaborative annotation (WebSocket) — deferred to post-MVP
- Inter-annotator agreement scoring — deferred to post-MVP
- Annotation UI SPA — this service provides the API layer only; the SPA is a separate deliverable
- CSV import/export of annotations — only HuggingFace Dataset format for MVP

## Currently-In-Force ADRs

All ADRs are in **Proposed** status and not yet formally Accepted. None are superseded.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | All annotation data stored in `tenant_{uuid}` schemas |
| ADR-002 | Single Curated Base Model Strategy | Pre-labeling uses only dslim/bert-base-NER label mapping (mocked for MVP) |
| ADR-005 | OpenCode Agent Boundaries | Agent may create new service directories and API endpoints following existing conventions |

## Decisions

### Decision 1: Standalone Microservice (not gateway extension)

**Choice:** New FastAPI microservice at `src/annotation_service/`.

**Rationale:** Same rationale as SM-02 — annotation processing has a different scaling profile (burst-y, memory-dependent for model loading) and dependency set than the gateway. Keeps deployment independent.

**Alternatives considered:**
- Gateway extension — ruled out because the gateway should remain a thin routing/auth layer; adding annotation logic couples scaling profiles.

### Decision 2: Mock Pre-labeling (no ML deps for MVP)

**Choice:** Pre-labeling endpoint returns candidate spans derived solely from the tenant's `base_label_mapping` config and simple regex/pattern matching on document text, without loading any ML model.

**Rationale:** The annotation workspace can be built, tested, and shipped without the complexity of model inference. Real model inference (transformers + torch) can be added in a follow-up change without changing the span data model — candidate spans already carry a `confidence_score` field.

**Alternatives considered:**
- Real model inference via transformers — ruled out for MVP because it adds ~2GB of dependencies (torch, tokenizers, model weights) and complicates the dev environment. The mock returns verifiable output and unblocks the UI and training pipeline.

### Decision 3: HuggingFace Dataset Format for Export

**Choice:** Export produces a JSON-lines file where each line is `{"tokens": [...], "tags": [...]}` with token-level BIO tags, directly consumable by `datasets.Dataset.from_json()`.

**Rationale:** SM-04's training pipeline uses HuggingFace `transformers.Trainer`, which accepts Dataset objects natively. No format conversion step needed. This matches the decomposition doc's implementation note.

**Alternatives considered:**
- CoNLL-2003 format — ruled out because it requires an additional parsing step in SM-04. JSON-lines is simpler and trivially convertible to CoNLL if ever needed.

### Decision 4: Manual Annotation Task Creation (no auto-assignment)

**Choice:** Tenant Admin creates annotation tasks via API by specifying `document_id`, `annotator_user_id`, and optional deadline. Tasks start in `unannotated` status.

**Rationale:** MVP simplicity. Auto-assignment (round-robin, workload-based) adds scheduling complexity with no user-facing value until multiple annotators exist per tenant.

**Alternatives considered:**
- Auto-assignment — ruled out for MVP. The task creation endpoint is a simple INSERT; assignment logic can be layered on later without schema changes.

### Decision 5: Document Locking Per Annotator

**Choice:** When an annotation task is in `in-progress` status for a given document, no other task can be created for that same document until the in-progress task completes.

**Rationale:** Prevents conflicting span edits. Annotator A adds a span at offsets 100-120; Annotator B adds a different span at overlapping offsets — resolving conflicts requires a merge strategy that is out of scope for MVP.

**Alternatives considered:**
- No locking (multiple annotators on same document) — ruled out because downstream SM-04 expects a single ground-truth label per token. Multi-annotator reconciliation is a future enhancement.

### Decision 6: Pre-labeling Stores Candidate Spans Separately

**Choice:** Suggested spans from pre-labeling are written to a `suggested_spans` table, separate from the `spans` table where annotator-confirmed spans live.

**Rationale:** Annotators need to see, accept, reject, or adjust suggested spans without mutating the same records. Separating the two allows tracking which suggestions were accepted vs rejected for future model fine-tuning.

**Alternatives considered:**
- Single spans table with `is_suggested` boolean flag — ruled out because it complicates queries (always need `WHERE is_suggested = false` for confirmed spans) and makes audit harder.

## Risks / Trade-offs

- [Mock pre-labeling may miss edge cases that real model inference would surface] → Draft the span data model and API contract to match what a real model would produce; swapping the implementation is a local change in one service function
- [Document locking per annotator limits throughput for tenants with many annotators] → Acceptable for MVP; unlock by removing the exclusive constraint when multi-annotator support is added
- [No UI SPA means the service cannot be end-to-end demonstrated without a client] → All acceptance criteria are verifiable via API tests; the SPA is tracked separately
- [HuggingFace Dataset format assumes SM-04's import path] → The format is well-documented and trivially convertible; if SM-04 changes requirements, the export endpoint is a single-function change

## Migration Plan

1. **Database migration:** Add `annotation_tasks`, `spans`, `suggested_spans` tables to `tenant_template` schema
2. **Create service scaffolding:** `src/annotation_service/main.py`, middleware, router wiring, `/health` endpoint
3. **Implement span CRUD:** endpoints at `/api/v1/documents/{doc_id}/spans` with tenant-scoped queries
4. **Implement pre-labeling:** `POST /api/v1/documents/{doc_id}/prelabel` — generates candidate spans from label mapping, persists to `suggested_spans`
5. **Implement annotation task management:** CRUD for tasks, status transitions, document-locking check
6. **Implement annotation export:** `GET /api/v1/annotation-export` — emits JSON-lines in HuggingFace Dataset format
7. **Tests:** Full test suite covering all acceptance criteria

Rollback: Revert the Alembic migration, remove `src/annotation_service/`, no impact on other services.

## Open Questions

- Should annotation tasks support batch creation (multiple documents + annotators in one call)? *(Assume: single-task creation for MVP; batch is a future enhancement)*
- Should pre-labeling overwrite existing suggested spans or append? *(Assume: replace — calling pre-label again re-generates all candidate spans for the document)*
