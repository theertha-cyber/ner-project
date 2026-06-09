## Why

Tenants need to upload documents (PDFs, images) for entity extraction. Currently the platform has no ingestion pipeline — documents cannot be uploaded, stored, or processed. SM-02 delivers the document ingestion and processing foundation that SM-03 (Annotation) and SM-05 (Extraction) depend on.

## What Changes

- Create a new **Document Ingestion Service** as a standalone FastAPI microservice at `src/document-service/`
- Document upload API with multipart/form-data support (PDF, JPEG, PNG, TIFF)
- Async OCR pipeline: upload returns immediately with `status: "pending"`, OCR via Tesseract runs in background, status updated to `"processed"` or `"failed"`
- Document text storage in tenant schema (`tenant_template.documents`, `tenant_template.document_text_spans` tables)
- MinIO/S3-compatible blob storage for original files and OCR artifacts
- Document metadata API (list, get, delete)
- Document status tracking through lifecycle: `pending` → `processing` → `processed` / `failed`
- Reuse `src/shared/` utilities (config, database, auth, exceptions) — no duplication

## Capabilities

### New Capabilities

- `document-ingestion`: Document upload, async OCR processing (Tesseract), text storage, MinIO-based blob storage, document metadata CRUD, status lifecycle tracking

### Modified Capabilities

- *(none — no existing specs to modify)*

## Impact

- **New service**: `src/document-service/` with its own Dockerfile, dependencies, and Alembic migrations
- **Database**: New tables in `tenant_template` schema for documents and text spans (migration required)
- **Infrastructure**: MinIO container added to `docker-compose.yml`; existing `tenant_template` migration updated with document tables
- **Dependencies**: `pytesseract` / `tesseract`, `Pillow`, `pdf2image` / `PyMuPDF`, `boto3` / `minio-py`
- **Shared code**: Reuses `src/shared/config.py`, `src/shared/database.py`, `src/shared/exceptions.py` from existing codebase
- **Gateway impact**: No API changes — document service has its own FastAPI app; gateway will route to it in a future integration pass
- **Message broker**: RabbitMQ queue for async OCR jobs (`document.ocr`) — broker is already declared in infrastructure

## Open Questions

- Should the document service validate JWT tokens itself or trust the gateway (internal network)? *(Assume: validates JWT directly for now, uses shared `src/shared/auth.py`)*
- Chunking strategy for long documents — fixed-size chunks or sentence-level? *(Assume: fixed-size 512-token chunks with configurable overlap for now)*
- Should MinIO be versioned (retain all uploads) or overwrite on re-upload? *(Assume: versioned — append UUID suffix on filename collision)*
