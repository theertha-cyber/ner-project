## 1. Service Scaffolding & Shared Code

- [x] 1.1 Create `src/annotation_service/` with FastAPI app factory, `main.py` — reuse `src/shared/` imports (config, database, auth, exceptions)
- [x] 1.2 Wire `/health` endpoint, global exception handler, and CORS middleware
- [x] 1.3 Add JWT security scheme (Authorize button in Swagger) via `add_bearer_security()`
- [x] 1.4 Create `src/annotation_service/middleware/tenant_context.py` — validates JWT, extracts `tenant_id` from payload, looks up tenant in `public.tenants`, returns 401/403/404 (copied from SM-02, reused)

## 2. Database Migrations

- [x] 2.1 Create Alembic migration `004_annotation_service_tables.py` — ALTERs `annotation_tasks` to add `annotator_user_id`, `updated_at` columns; creates `spans` and `suggested_spans` tables; adds unique partial index for document locking
- [x] 2.2 Creates `spans` table with `id`, `document_id`, `entity_type`, `char_start`, `char_end`, `text_content`, `confidence`, `created_at`, `updated_at`
- [x] 2.3 Creates `suggested_spans` table with `id`, `document_id`, `entity_type`, `char_start`, `char_end`, `text_content`, `confidence`, `created_at`
- [x] 2.4 Adds unique partial index `idx_task_active_document` on `annotation_tasks(document_id)` WHERE status IN ('unannotated', 'in-progress')

## 3. Span CRUD Endpoints

- [x] 3.1 POST `/api/v1/documents/{doc_id}/spans` — create confirmed span, validate entity_type against tenant's configured types, store in `tenant_{tid}.spans`
- [x] 3.2 GET `/api/v1/documents/{doc_id}/spans` — list confirmed spans with optional `?type=suggested` filter
- [x] 3.3 PATCH `/api/v1/documents/{doc_id}/spans/{span_id}` — update span fields
- [x] 3.4 DELETE `/api/v1/documents/{doc_id}/spans/{span_id}` — hard-delete span, return 204
- [x] 3.5 Entity type validation — reject spans with entity_type not in tenant's configured types (422)

## 4. Pre-labeling

- [x] 4.1 POST `/api/v1/documents/{doc_id}/prelabel` — generate suggested spans from tenant's `base_label_mapping` using whole-word matching against document text
- [x] 4.2 Pre-label logic: iterate label mapping keywords, find exact whole-word matches, calculate char offsets, assign confidence (e.g., 0.85 for keyword match), persist to `suggested_spans`
- [x] 4.3 Replace existing suggestions — DELETE all existing suggested spans for the document before inserting new ones (single transaction)
- [x] 4.4 POST `/api/v1/documents/{doc_id}/spans/promote/{suggest_id}` — insert confirmed span from suggestion, delete suggested span (transactional)

## 5. Annotation Task Management

- [x] 5.1 POST `/api/v1/annotation-tasks` — create task, check document-locking constraint (no active task for same document), return 409 on conflict
- [x] 5.2 GET `/api/v1/annotation-tasks` — list tasks with optional `?status=` filter
- [x] 5.3 PATCH `/api/v1/annotation-tasks/{task_id}` — update status (unannotated → in-progress → completed)
- [x] 5.4 Validate task completion — reject with 422 if status=completed and document has zero confirmed spans

## 6. Annotation Export

- [x] 6.1 GET `/api/v1/annotation-export` — full export of all documents in HuggingFace Dataset format (JSON lines)
- [x] 6.2 Tokenize document text via `str.split()` and map spans to BIO2 token tags
- [x] 6.3 Support `?entity_types=PER,ORG` filter — non-matching entity types encoded as O
- [x] 6.4 Support `?document_ids=id1,id2` filter — export only specified documents

## 7. Tests

- [x] 7.1 Span CRUD — create span returns 201 with correct metadata
- [x] 7.2 Span CRUD — list spans returns all spans for document
- [x] 7.3 Span CRUD — update span modifies fields
- [x] 7.4 Span CRUD — delete span returns 204 and removes record
- [x] 7.5 Span CRUD — create with invalid entity type returns 422
- [x] 7.6 Pre-labeling — generate suggested spans from label mapping
- [x] 7.7 Pre-labeling — re-running replaces existing suggestions
- [x] 7.8 Pre-labeling — list suggested spans via `?type=suggested`
- [x] 7.9 Pre-labeling — promote suggested span creates confirmed span and removes suggestion
- [x] 7.10 Task management — create task in unannotated status
- [x] 7.11 Task management — create task for already-assigned document returns 409
- [x] 7.12 Task management — list tasks with status filter
- [x] 7.13 Task management — update task status
- [x] 7.14 Task management — complete task with spans succeeds
- [x] 7.15 Task management — complete task without spans returns 422
- [x] 7.16 Annotation export — exports all documents as JSON lines with tokens/tags
- [x] 7.17 Annotation export — export with entity type filter
- [x] 7.18 Annotation export — export for specific document IDs only

## 8. Verification & Evidence

- [x] 8.1 Run all 18 acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass — 57/57 tests pass (39 existing + 18 new)
- [x] 8.2 Collect functional evidence for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register — 1 variance flagged (Risk 1: pre-labeling uses substring match not whole-word)
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance — 3/3 ADRs verified compliant
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 8.6 Run `openspec validate sm-03-annotation-workspace --type change --strict` and confirm it exits clean before archive — Change is valid
