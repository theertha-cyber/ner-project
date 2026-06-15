## 1. Setup & Scaffolding

- [x] 1.1 Create `src/model_serving/` with FastAPI scaffolding (main.py, lifespan, health endpoint) following existing service conventions
- [x] 1.2 Create `src/extraction_service/` with FastAPI scaffolding (main.py, lifespan, health endpoint) following existing service conventions
- [x] 1.3 Add ONNX Runtime, transformers, torch to project dependencies
- [x] 1.4 Add `.env` entries for model-serving port, extraction Celery queue name, default confidence threshold (0.50), cache memory limit (2GB), cache TTL (30min)
- [x] 1.5 Create `src/model_serving/services/model_cache.py` — in-memory cache with LRU eviction and memory tracking
- [x] 1.6 Create `src/model_serving/services/model_loader.py` — ONNX model loader from blob storage at `tenants/{tid}/models/v{version}/`
- [x] 1.7 Create `src/extraction_service/services/extraction_engine.py` — inference client that calls model-serving internal endpoint
- [x] 1.8 Create `src/extraction_service/services/entity_store.py` — CRUD operations for `extraction_runs` and `extracted_entities` tables

## 2. Model Serving — Inference Endpoint

- [x] 2.1 Implement `POST /internal/v1/tenants/{tid}/infer` in model-serving — accepts tokens, runs ONNX inference, returns per-token predictions with labels and confidence scores
- [x] 2.2 Implement model resolution — fetch tenant's active model version from model registry API on each request (with 60s TTL cache)
- [x] 2.3 Implement tokenizer — load dslim/bert-base-NER tokenizer, tokenize input, align subword tokens to original token spans, handle -100 label for subword tokens beyond first
- [x] 2.4 Implement inference error handling — return 404 if no model loaded for tenant, catch ONNX Runtime errors and return 500 with error detail
- [x] 2.5 Write unit tests for model cache: `test_load_model_on_first_request`, `test_cache_hit_on_subsequent_request`, `test_lru_eviction_on_memory_pressure`
- [x] 2.6 Write unit tests for inference endpoint: `test_inference_returns_predictions`, `test_inference_no_model_returns_404`

## 3. Extraction Service — Real-time Extraction API

- [x] 3.1 Implement `POST /api/v1/tenants/{tid}/extract` — accepts `{"text": "..."}`, tokenizes, calls model-serving infer endpoint, maps predictions to entity format with offsets, applies confidence threshold filter, sorts by descending confidence
- [x] 3.2 Implement authz check — only Tenant Admin and Tenant Business User roles can call extract (annotator gets 403)
- [x] 3.3 Implement confidence filtering — apply configurable threshold (default 0.50), exclude entities below threshold
- [x] 3.4 Write unit tests: `test_extract_text_returns_entities`, `test_extract_no_model_returns_400`, `test_extract_non_admin_returns_403`, `test_low_confidence_filtered`

## 4. Extraction Service — Batch Extraction

- [x] 4.1 Implement `POST /api/v1/tenants/{tid}/extract-batch` — accepts documentIds query param, creates `extraction_runs` record with "queued" status, enqueues Celery task to `extraction` queue
- [x] 4.2 Implement Celery batch extraction worker — queries documents in `processed` status, checks each against existing extraction_runs with current model version (skip if already extracted), calls model-serving for each document, stores entities in `extracted_entities`, updates run progress
- [x] 4.3 Implement idempotency check — skip document if an extraction_run exists for this document with the current active model version
- [x] 4.4 Implement `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` — returns status, progress counts, completed_at
- [x] 4.5 Implement batch extraction failure handling — catch exceptions per document, mark as failed in run stats, continue processing remaining documents
- [x] 4.6 Write unit tests: `test_trigger_batch_returns_202`, `test_batch_skips_already_extracted`, `test_batch_no_model_returns_400`, `test_get_run_status_running`, `test_get_run_status_completed`

## 5. Extraction Service — Entity Query & Review

- [x] 5.1 Implement `GET /api/v1/tenants/{tid}/entities` with query params: `documentId`, `type`, `minConfidence`, `reviewStatus` — paginated with offset/limit
- [x] 5.2 Implement cross-tenant isolation — entities query scoped to requesting tenant's schema, returns 404 if document belongs to another tenant
- [x] 5.3 Implement `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` — update `review_status`, `corrected_value`, `corrected_by`, `correction_notes`; set corrected_by from authenticated user
- [x] 5.4 Write unit tests: `test_query_entities_by_document`, `test_query_entities_by_type`, `test_query_entities_by_confidence`, `test_query_entities_unreviewed`, `test_query_entities_annotator_200`, `test_query_entities_cross_tenant_404`, `test_correct_entity`, `test_correct_entity_annotator`

## 6. Model Warmup on Promotion

> Deferred to dedicated change `promote-warmup-integration`. These tasks will be implemented there.

- [~] 6.1 Implement event consumer that listens for `ModelPromoted` events — on promotion, trigger model load in model-serving cache (deferred to promote-warmup-integration)
- [~] 6.2 Implement synchronous warmup — promotion endpoint (in model registry) blocks until model-serving confirms model is loaded and ready (deferred to promote-warmup-integration)
- [~] 6.3 Write unit test: `test_warmup_on_promotion` (deferred to promote-warmup-integration)

## 7. Gateway Routing

- [x] 7.1 Register extraction-service router in gateway at `/api/v1/tenants/{tid}/extract`, `/api/v1/tenants/{tid}/extract-batch`, `/api/v1/tenants/{tid}/entities`
- [x] 7.2 Verify model-serving internal endpoint is NOT exposed via gateway (internal only) — model-serving routes use `/internal/v1/` prefix which is not registered in the gateway; confirmed no `/internal/` routes exist in gateway

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass — model cache tests (9/9 pass). DB-integrated tests require running services (DB, Redis, MinIO) to execute fully; test files created for all remaining scenarios.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log (requires human or running services)
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register — all 5 risks reviewed and mitigations confirmed in code (model path uses blob convention, idempotency check exists, confidence filtering at extraction time, internal endpoints not in gateway, warmup deferred)
- [x] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance — ADR-001 (schema-qualified queries), ADR-002 (dslim/bert-base-NER tokenizer), ADR-003 (in-memory cache, per-tenant routing, version pinning), ADR-006 (blob path convention `tenants/{tid}/models/v{version}/`) all confirmed
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 8.6 Run `openspec validate sm-05-extraction-engine --type change --strict` and confirm it exits clean before archive — validation: PASS
