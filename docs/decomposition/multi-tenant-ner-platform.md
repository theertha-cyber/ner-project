# Feature Decomposition: Multi-Tenant Custom NER Platform

## Summary

A greenfield multi-tenant SaaS platform that lets tenants define custom entity types, upload documents (PDF/images/CSV), OCR them, annotate entities with pre-labeling assistance from a base NER model, train a fine-tuned tenant-specific model via async GPU jobs, extract entities at scale via that model, query extracted entities through a RAG chatbot (internal dashboard + external embeddable widget), and explore entity data via an ad-hoc analytics/reporting builder. Built on PostgreSQL per-tenant schema isolation with a shared model-serving pool and Celery-managed GPU workers.

---

## Sub-Modules

### [SM-01] Identity, Tenant & Entity Configuration

| Field | Value |
|---|---|
| **OpenSpec Domain** | Foundation / Identity & Configuration |
| **Scope** | Tenant provisioning (subdomain/URL allocation, schema creation), user management (RBAC: System Admin, Tenant Admin, Annotator), authentication (JWT with tenant context), entity type CRUD, base-model label mapping configuration. |
| **Key Requirements** | FR-02 (Multi-tenant isolation), FR-03 (User roles & auth), FR-04 (Entity type config) |
| **Contracts/Interfaces** | Tenant provisioning API (`POST /api/v1/admin/tenants`); User CRUD API (`/api/v1/admin/tenants/{tid}/users`); Entity type API (`/api/v1/tenants/{tid}/entity-types`); JWT token issued at login scoped to `{tenant_id, user_id, role}`; Tenant context middleware that extracts tenant from URL path or subdomain and injects into request scope. |
| **Prerequisites** | None — this is the foundation module. |
| **Implementation Notes** | Tenant provisioning must execute DDL (`CREATE SCHEMA IF NOT EXISTS tenant_{tid}`) and run tenant-scoped migrations. JWT should encode tenant_id in the `sub` claim namespace (e.g., `"tenant_user": "{tid}:{uid}"`). Entity type API must support a `base_label_mapping` field (e.g., `{"PER": ["customer_name", "vendor_name"], "ORG": ["company_name"]}`) for FR-05 pre-labeling. The System Admin console (FR-15) is built here as a separate admin SPA. |

---

### [SM-02] Document Ingestion & Processing Pipeline

| Field | Value |
|---|---|
| **OpenSpec Domain** | Content / Ingestion |
| **Scope** | Document upload (PDF, images, text), OCR orchestration (Tesseract), structured CSV import (schema validation, column mapping), document status tracking (uploaded → processed → ready), storage management (blob storage path, reference in tenant schema). |
| **Key Requirements** | FR-08 (Document upload), FR-09 (OCR processing) |
| **Contracts/Interfaces** | Document upload API (`POST /api/v1/tenants/{tid}/documents` — multipart/form-data); Document status API (`GET /api/v1/tenants/{tid}/documents/{docId}`); OCR callback/webhook (`POST /api/v1/internal/documents/{docId}/ocr-complete`); CSV import API (`POST /api/v1/tenants/{tid}/documents/import-csv` with schema definition); Blob storage: per-tenant prefix (`tenants/{tid}/documents/{docId}.{ext}`). |
| **Prerequisites** | SM-01 (tenant + user context needed for ownership and schema) |
| **Implementation Notes** | OCR should be async — upload returns immediately, webhook updates status. PDFs require Poppler/pdftotext or similar library. Image OCR via Tesseract. CSV import validates header row against target entity type schema before ingesting rows into tenant's structured tables. Document processing triggers pre-labeling (see SM-03 dependency). Supported formats: PDF, JPEG, PNG, TIFF, CSV. |

---

### [SM-03] Annotation Workspace

| Field | Value |
|---|---|
| **OpenSpec Domain** | Human-in-the-Loop / Annotation |
| **Scope** | Annotation task creation (splitting documents into annotator assignments), pre-labeling using the base model (dslim/bert-base-NER) with tenant's label mapping, span-level annotation UI (entity tag, start/end offset), annotation status tracking (unannotated → in-progress → completed), inter-annotator agreement (optional), annotation export for training. |
| **Key Requirements** | FR-05 (Annotation interface + pre-labeling) |
| **Contracts/Interfaces** | Annotation task API (`POST /api/v1/tenants/{tid}/annotation-tasks`); Span CRUD API (`POST /api/v1/tenants/{tid}/documents/{docId}/spans`); Pre-label trigger (`POST /api/v1/internal/prelabel/{docId}`); Annotation export (`GET /api/v1/tenants/{tid}/annotation-export?format=conll`); WebSocket for real-time collaborative annotation (optional). |
| **Prerequisites** | SM-01 (entity types for label definitions), SM-02 (documents to annotate) |
| **Implementation Notes** | Pre-labeling runs the base model on document text and converts standard labels to candidate spans via the tenant's `base_label_mapping`. Candidates are stored as `suggested_spans` with confidence scores — annotator can accept, reject, or adjust. Annotation UI is a dedicated SPA with side-by-side document rendering and entity palette. Export format must match HuggingFace `Dataset` format for SM-04 consumption. |

---

### [SM-04] Training Pipeline

| Field | Value |
|---|---|
| **OpenSpec Domain** | ML / Training |
| **Scope** | Training job submission (triggered by Tenant Admin), GPU job orchestration (Celery worker pool on K8s with GPU nodes), fine-tuning of dslim/bert-base-NER on tenant's annotated data, model versioning (v1, v2, ...), model registry (per-tenant model list), training metrics dashboard (loss curves, F1 per entity type), model promotion to production. |
| **Key Requirements** | FR-06 (Model training & versioning) |
| **Contracts/Interfaces** | Training job API (`POST /api/v1/tenants/{tid}/training-jobs`); Job status API (`GET /api/v1/tenants/{tid}/training-jobs/{jobId}`); Model registry API (`GET /api/v1/tenants/{tid}/models`, `POST /api/v1/tenants/{tid}/models/{modelId}/promote`); Celery task queue: `train_tenant_model(tid, export_id, hyperparams) → model_uri`; Training callback webhook: `POST /api/v1/internal/training-complete`. |
| **Prerequisites** | SM-03 (annotated data in CoNLL/Dataset format) |
| **Implementation Notes** | ADR-006 mandates Celery + RabbitMQ for GPU job management. Each training job runs in an isolated container pod with GPU access. Hyperparameters: tenant can adjust learning rate, batch size, epochs (with sensible defaults). Model artifacts stored in blob storage (`tenants/{tid}/models/v{version}/`). On promotion, the model binary is loaded into the shared model-serving pool (SM-05). Training uses the transformers `Trainer` API with the tenant's annotated spans as token-level BIO tags. |

---

### [SM-05] Extraction Engine

| Field | Value |
|---|---|
| **OpenSpec Domain** | Inference / Extraction |
| **Scope** | Model serving (shared pool — loaded models from all tenants), batch extraction on existing documents, real-time extraction API (single document/paragraph), entity storage (extracted spans linked to documents and model version), confidence filtering, extraction audit trail (which model version extracted which entity at what time). |
| **Key Requirements** | FR-06 (model serving — downstream of training), FR-10 (Extraction API) |
| **Contracts/Interfaces** | Real-time extraction API (`POST /api/v1/tenants/{tid}/extract` — body: text/paragraph); Batch extraction trigger (`POST /api/v1/tenants/{tid}/extract-batch?documentIds=...`); Extracted entity query API (`GET /api/v1/tenants/{tid}/entities?documentId=...&type=...`); Internal: Model router (tenant_id → active model version → model object in shared pool). |
| **Prerequisites** | SM-04 (at least one model version must be trained and promoted for the tenant) |
| **Implementation Notes** | ADR-003 mandates a shared model-serving pool (in-memory inference workers). Models are loaded into a dict/slot keyed by model_id. Tenant context middleware routes extraction requests to the tenant's active model version. Batch extraction runs as an async job, processing documents that are in `processed` status and skipping those already extracted with the current active model (idempotent). Entities extracted with a superseded model version remain in the database with the model version tag — SM-04 rollback does not remove them (confirmed Phase 1 decision). |

---

### [SM-06] RAG Chatbot (Internal + Embeddable)

| Field | Value |
|---|---|
| **OpenSpec Domain** | Applications / Chatbot |
| **Scope** | Internal chat UI for tenant admins, embeddable widget (JS snippet/iframe) for tenant's end customers, RAG pipeline combining SQL question-answering (natural language → SQL), semantic search (pgvector on document chunks), and NER-based entity lookup, conversational guardrails (ADR-007), conversation history per user. |
| **Key Requirements** | FR-11 (RAG chatbot), FR-13 (API scalability — chatbot endpoint may experience high concurrency from external widget) |
| **Contracts/Interfaces** | Chat API (`POST /api/v1/tenants/{tid}/chat` — body: `{message: string, conversation_id?: string}`); Embeddable widget API (`GET /api/v1/public/widget.js` per tenant); Conversation history API (`GET /api/v1/tenants/{tid}/chat/history`); Internal: SQL generator (LLM prompt → safe SQL filtered by tenant_id), pgvector similarity search (`text_embedding` column on document chunks), NER entity lookup (extracted entity table). |
| **Prerequisites** | SM-05 (extracted entities needed for NER lookup in chatbot answers) |
| **Implementation Notes** | ADR-007 mandates guardrails: SQL generation must be scoped to tenant schema (never cross-tenant), no DML generation, output sanitization. The chatbot uses pgvector for semantic search over document chunks (chunked at upload time or during extraction). The embeddable widget is a hosted JS file that the tenant includes on their site — it communicates via CORS-safe endpoints with tenant-specific API keys (not user JWT). The SQL-to-NL pipeline translates natural language questions into parameterized SQL queries scoped to the tenant's extracted entity tables. |

---

### [SM-07] Analytics & Reporting

| Field | Value |
|---|---|
| **OpenSpec Domain** | Applications / Analytics |
| **Scope** | Ad-hoc query builder (date range, entity type, confidence score, document source, annotator), pre-built dashboard widgets (entity coverage %, confidence distribution histogram, extraction volume over time, per-document entity counts), report export (CSV, JSON), scheduled report delivery (email — optional). |
| **Key Requirements** | FR-12 (Reporting & Analytics) |
| **Contracts/Interfaces** | Ad-hoc query API (`POST /api/v1/tenants/{tid}/analytics/query` — body: filter object → paginated result); Dashboard API (`GET /api/v1/tenants/{tid}/analytics/dashboard`); Export API (`POST /api/v1/tenants/{tid}/analytics/export` → CSV/JSON download); Aggregation queries are executed within the tenant's isolated schema. |
| **Prerequisites** | SM-05 (extracted entities must exist in the tenant schema before analytics are meaningful) |
| **Implementation Notes** | The ad-hoc query builder exposes a structured filter JSON: `{entity_types: [...], confidence: {min, max}, date_from, date_to, document_sources: [...], annotators: [...]}`. The backend translates this into parameterized SQL within the tenant's schema. Dashboard widgets are lightweight pre-computed aggregations (materialized views refreshed on new extraction jobs or on-demand). No cross-tenant aggregation. |

---

## Dependency Waves

| Wave | Sub-modules | Description |
|---|---|---|
| **Wave 1** | SM-01 — Identity, Tenant & Entity Configuration | Foundation: tenant provisioning, auth, entity types. Nothing else works without it. |
| **Wave 2** | SM-02 — Document Ingestion | Content ingestion pipeline. Tenant needs to upload documents before annotating. |
| **Wave 3** | SM-03 — Annotation Workspace | Human annotation with pre-labeling. Needs both entity types and documents. |
| **Wave 4** | SM-04 — Training Pipeline | GPU training on annotated data. Core value — transforms annotated data into a custom model. |
| **Wave 5** | SM-05 — Extraction Engine | Model serving and entity extraction. The primary ROI — automated extraction at scale. |
| **Wave 6** | SM-06 — RAG Chatbot, SM-07 — Analytics & Reporting | Both depend on extracted entities; they can be built in parallel as they address different user needs. |

```
SM-01 ──→ SM-02 ──→ SM-03 ──→ SM-04 ──→ SM-05 ──→ SM-06
                                                   └──→ SM-07
```

---

## Cross-Cutting Concerns

| Concern | Approach |
|---|---|
| **Authentication & Tenant Context** | JWT with embedded `{tenant_id, user_id, role}`. Tenant context middleware in API gateway extracts tenant from URL path prefix or subdomain. Every database query includes `WHERE tenant_id = ...` or is executed within the tenant's isolated schema. |
| **Tenant Data Isolation** | ADR-001: Separate PostgreSQL schema per tenant (`tenant_{tid}`). Connection pooling via PgBouncer with `SET search_path TO tenant_{tid}` on each connection checkout. DDL migrations iterate over all tenant schemas. |
| **API Gateway** | Single gateway route: `/api/v1/admin/*` (System Admin), `/api/v1/tenants/{tid}/*` (tenant-scoped), `/api/v1/public/*` (embeddable widget, CORS-enabled). Rate limiting per tenant and per endpoint class. |
| **Async Job Orchestration** | ADR-006: Celery + RabbitMQ. Queues: `ocr` (CPU-bound), `training` (GPU-bound, serially per tenant — one training at a time per tenant), `extraction-batch` (CPU-bound). Priority queues for real-time extraction vs batch. |
| **Observability** | Structured JSON logging with `tenant_id` and `request_id` in every log line. Prometheus metrics per endpoint (latency, error rate, request count) labeled by tenant. Celery task monitoring via Flower. |
| **Shared Model Pool** | ADR-003: In-memory dict of loaded models keyed by `model_id`. Warm on promotion (SM-04) and on pod startup (load last promoted model per tenant). Eviction policy: LRU when memory threshold crossed, reload on next request. |
| **Error Handling** | All APIs return RFC 7807 Problem Details JSON. Tenant-not-found → 404, quota-exceeded → 429, model-not-ready → 503 with retry-after. Extraction requests for tenants without a promoted model return 400 with actionable message. |
| **Database Migrations** | One Alembic (or equivalent) migration chain. Tenant-scoped tables land in `tenant_template` schema; global tables (tenants, users, entity type definitions) in `public` schema. On tenant creation, `CREATE SCHEMA tenant_{tid} TEMPLATE tenant_template`. |

---

## Recommended Next Step

Generate a **spec-generator** OpenSpec change folder for **Wave 1 (SM-01)** — the Identity, Tenant & Entity Configuration sub-module. This is the foundation that all other modules depend on and can be independently developed, tested, and deployed.
