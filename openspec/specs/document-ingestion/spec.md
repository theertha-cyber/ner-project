# Document Ingestion

## Purpose

Handles document upload, async OCR/text extraction, and document metadata management within tenant-isolated storage.

---

## Requirements

### Requirement: Document Upload

The system SHALL accept document uploads via multipart/form-data for PDF, JPEG, PNG, and TIFF files. On successful upload, the system SHALL store the file in MinIO at path `tenants/{tid}/documents/{docId}.{ext}`, create a metadata record in `tenant_{tid}.documents`, and return HTTP 201 with the document metadata. The system SHALL reject files larger than 50MB with HTTP 413.

#### Scenario: Upload a PDF document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a PDF file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status: "pending"`, `file_size`

#### Scenario: Upload an unsupported file type

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a `.exe` file
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate the file type is not supported

#### Scenario: Upload exceeds file size limit

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a 100MB file
- **THEN** the response SHALL have status 413
- **AND** the error message SHALL indicate the file exceeds the 50MB limit

### Requirement: Async OCR Processing

The system SHALL process uploaded documents asynchronously. For PDF documents, the system SHALL extract text using PyMuPDF. For image documents (JPEG, PNG, TIFF), the system SHALL run OCR using Tesseract via `pytesseract`. Text spans SHALL be stored in `tenant_{tid}.document_text_spans` with character offsets. The document status SHALL transition from `pending` → `processing` → `processed` on success, or `pending` → `processing` → `failed` on error.

#### Scenario: PDF text extraction succeeds

- **GIVEN** a document with `status: "pending"` and content type `application/pdf`
- **WHEN** the OCR processing worker runs
- **AND** PyMuPDF successfully extracts text from the PDF
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans` with extracted text and character offsets

#### Scenario: Image OCR succeeds

- **GIVEN** a document with `status: "pending"` and content type `image/png`
- **WHEN** the OCR processing worker runs
- **AND** Tesseract successfully extracts text from the image
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans`

#### Scenario: OCR processing fails

- **GIVEN** a corrupt PDF document with `status: "pending"`
- **WHEN** the OCR processing worker runs
- **AND** PyMuPDF raises an extraction error
- **THEN** the document status SHALL be updated to `"failed"`
- **AND** the document record SHALL contain an error message describing the failure

### Requirement: Document Metadata API

The system SHALL expose endpoints to list, get, and delete document metadata. Listing SHALL support pagination and optional `?status=` filter. Getting a single document SHALL return metadata including current status and file size. Deleting a document SHALL soft-delete by setting `status: "deleted"` and SHALL NOT remove the blob from MinIO.

#### Scenario: List documents with status filter

- **GIVEN** two documents in status `"processed"` and one in `"pending"`
- **WHEN** a tenant user GETs `/api/v1/documents?status=processed`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain only the two processed documents

#### Scenario: Get document metadata

- **GIVEN** a document with ID "doc-123" that was previously uploaded
- **WHEN** a tenant user GETs `/api/v1/documents/doc-123`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status`, `file_size`, `created_at`

#### Scenario: Delete a document

- **GIVEN** a document with ID "doc-123" in status `"processed"`
- **WHEN** a tenant user DELETEs `/api/v1/documents/doc-123`
- **THEN** the response SHALL have status 200
- **AND** the document's `status` SHALL be `"deleted"`

#### Scenario: Get deleted document returns 200 with deleted status

- **GIVEN** a document with ID "doc-123" that was soft-deleted
- **WHEN** a tenant user GETs `/api/v1/documents/doc-123`
- **THEN** the response SHALL have status 200
- **AND** the document `status` SHALL be `"deleted"`

### Requirement: Tenant Context Enforcement

The system SHALL enforce tenant context on all document endpoints. The JWT token SHALL be validated on every request. The tenant SHALL be resolved from the JWT `tenant_id` claim directly — there is no URL slug parameter. An inactive tenant SHALL return HTTP 403. A tenant ID that does not exist in `public.tenants` SHALL return HTTP 404.

#### Scenario: Authenticated request with valid tenant

- **GIVEN** a valid JWT with `tenant_id` matching an active tenant in `public.tenants`
- **WHEN** a tenant user GETs `/api/v1/documents`
- **THEN** the response SHALL have status 200

#### Scenario: Request with inactive tenant

- **GIVEN** a valid JWT with `tenant_id` for a deactivated tenant
- **WHEN** a tenant user GETs `/api/v1/documents`
- **THEN** the response SHALL have status 403
- **AND** the error SHALL indicate the tenant is inactive

#### Scenario: Request for unknown tenant

- **GIVEN** a valid JWT with a `tenant_id` that does not exist in `public.tenants`
- **WHEN** a tenant user GETs `/api/v1/documents`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL indicate the tenant was not found
