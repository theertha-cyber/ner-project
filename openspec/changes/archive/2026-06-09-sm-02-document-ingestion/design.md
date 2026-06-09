## Context

Currently the platform has SM-01 (Identity, Tenant & Entity Configuration) — tenant provisioning, auth, entity types — running as an API gateway at `src/gateway/`. There is no way to upload documents, process them for text, or store them. SM-02 is Wave 2 in the dependency chain: tenants need to upload documents before they can annotate (SM-03) or extract entities (SM-05). The document service must be a standalone microservice (`src/document-service/`) that shares utilities with the existing gateway but operates independently.

## Goals / Non-Goals

**Goals:**

- Document upload via multipart/form-data for PDF, JPEG, PNG, TIFF
- Async OCR pipeline using Tesseract — upload returns immediately, processing happens in background
- Text extraction from PDFs (PyMuPDF) and images (Tesseract via pytesseract)
- Blob storage in MinIO with tenant-prefixed paths
- Document text spans stored in tenant-scoped DB schema
- Document CRUD API (list, get, delete) with status tracking
- Document status lifecycle: `pending` → `processing` → `processed` / `failed`
- Reuse `src/shared/` utilities (config, database, auth, exceptions)

**Non-Goals:**

- Pre-labeling / entity annotation — belongs in SM-03
- CSV import — deferred to a later iteration
- Document editing or version management
- Multi-page TIFF/PDF splitting or reordering
- Webhook notifications on document status change
- Gateway integration — document service is standalone; API routing integration is future work

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via separate PostgreSQL schemas + object storage prefix isolation | Document text spans stored in `tenant_<uuid>.document_text_spans`. Blob storage path: `tenants/{tid}/documents/{docId}.{ext}` |
| ADR-004 | OpenSpec SDD with mandatory artifact gates | This change follows the proposal → design → spec → tasks → evidence → archive pipeline |

## Decisions

### Decision 1: Standalone Microservice vs Gateway Extension

**Choice:** Standalone FastAPI microservice at `src/document-service/`

**Rationale:** The decomposition doc and repo structure both call for a separate service. Document processing is I/O-heavy (OCR, file I/O, blob storage) and has different scaling and dependency profiles than the gateway (tenant management, auth). A standalone service avoids coupling and allows independent scaling.

**Alternatives considered:**
- Gateway extension (add routes to `src/gateway/`) — simpler but couples scaling profiles and introduces heavy OCR/PDF dependencies to the gateway's dependency tree

### Decision 2: Async OCR via Message Broker vs Inline

**Choice:** Async — upload returns `status: "pending"` immediately, background worker picks up the job and updates status

**Rationale:** OCR on PDFs and images is CPU-bound and can take seconds to minutes. A synchronous upload would block the API process and cause timeouts for large files. Async decouples upload from processing and aligns with the project's event-driven architecture (RabbitMQ already declared in infrastructure).

**Alternatives considered:**
- Inline/sync processing — simpler but blocks the request for the duration of OCR
- Celery worker — full-blown task queue, overkill for a single CPU-bound task at this stage; will evaluate Celery for SM-04 training jobs

### Decision 3: Blob Storage Provider

**Choice:** MinIO with S3-compatible API, using `boto3` for uploads

**Rationale:** MinIO is already declared in the project's tech stack for dev, with a path to S3 in production. Using `boto3` means the production migration requires only a config change (endpoint URL + credentials). Path structure: `tenants/{tid}/documents/{docId}.{ext}` (matching ADR-001's prefix convention).

**Alternatives considered:**
- Local filesystem storage — simpler for dev but would require a rewrite for production

### Decision 4: PDF Text Extraction Library

**Choice:** PyMuPDF (`fitz`) for PDF text extraction + `pdf2image` + `pytesseract` for image-based PDF pages

**Rationale:** PyMuPDF provides fast text extraction with layout preservation for text-based PDFs. For scanned/image PDFs, `pdf2image` converts pages to PIL images, then `pytesseract` runs OCR. This dual approach handles both born-digital and scanned documents.

**Alternatives considered:**
- Poppler/pdftotext — CLI-based, no async Python binding
- Apache Tika — heavier dependency, overkill for text extraction

### Decision 5: Message Queue Pattern

**Choice:** Simple in-process background task via `asyncio.create_task` for MVP, with a `document.ocr` queue designed for later migration to RabbitMQ

**Rationale:** RabbitMQ is declared in the project infrastructure but not yet deployed in the dev environment. Using an in-process async task keeps the MVP simple while designing the interface so a future swap to RabbitMQ requires only changing the worker implementation, not the service logic.

**Alternatives considered:**
- RabbitMQ from day one — adds deployment complexity before it's needed
- Thread pool executor — `asyncio.create_task` is simpler and sufficient for single-worker MVP

## Risks / Trade-offs

- [**Processing fails mid-way** (e.g., corrupt PDF, OCR timeout)] → Document marked as `failed` with error message stored; upload is retained in MinIO for manual recovery
- [**Large file uploads (50MB+)** consume memory during processing] → Stream to disk during upload; process from temp file rather than in-memory buffer
- [**No concurrent processing queue** for MVP in-process worker] → If a document is still processing and a new upload arrives, the new upload waits. Acceptable for single-tenant MVP; RabbitMQ migration resolves this
- [**MinIO not yet in docker-compose**] → Will be added as part of this change

## Migration Plan

1. Add `tenant_template` migration with `documents` and `document_text_spans` tables
2. Add MinIO container to `docker-compose.yml`
3. Create `src/document-service/` with FastAPI app, shared utility imports, and dependencies
4. Implement file upload endpoint with MinIO blob storage + DB metadata persistence
5. Implement async OCR worker with PyMuPDF + pytesseract
6. Implement document CRUD endpoints (list, get, delete)
7. Add tests for upload, processing, and CRUD
8. Run existing SM-01 tests to confirm no regression

Rollback: Remove the new service directory, revert the migration, remove MinIO from docker-compose.

## Open Questions

- Should the document service validate JWT tokens itself or trust the gateway in an internal network? *Assume: validates JWT directly using `src/shared/auth.py` for now — allows standalone usage without the gateway.*
- Chunking strategy for long documents? *Assume: fixed-size 512-token chunks with 128-token overlap, stored in `document_text_spans` table.*
- MinIO bucket name? *Assume: `ner-documents` (single bucket, tenant-prefixed paths).*
