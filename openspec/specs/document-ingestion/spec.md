# Document Ingestion

## Purpose

Handles document upload, async OCR/text extraction, and document metadata management within tenant-isolated storage.

---
## Requirements
### Requirement: Document Upload

The system SHALL accept document uploads via multipart/form-data for PDF, JPEG, PNG, and TIFF files. On successful upload, the system SHALL submit the document to the application ingestion operation, which SHALL resolve the tenant's retention mode, write the bytes to the durable content store under `platform_blob` retention or to the working content store under `ephemeral` retention, create a metadata record in `tenant_{tid}.documents`, and return HTTP 201 with the document metadata. The system SHALL reject files larger than 50MB with HTTP 413. Uploads SHALL accept an optional `purpose` field (`query` or `training`), defaulting to `query` when omitted, recorded on the document's metadata record.

#### Scenario: Upload a PDF document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a PDF file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status: "pending"`, `file_size`

#### Scenario: Upload a DOCX document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a `.docx` file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, `status: "pending"`, `file_size`

#### Scenario: Upload a DOC document

- **GIVEN** an authenticated tenant user with a valid JWT
- **WHEN** they POST to `/api/v1/documents` with a `.doc` file as multipart/form-data
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

#### Scenario: Upload without a purpose field defaults to query

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a PDF file and no `purpose` field
- **THEN** the response SHALL have status 201
- **AND** the document's stored `purpose` SHALL be `query`

#### Scenario: Upload with an explicit training purpose

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a PDF file and `purpose=training`
- **THEN** the response SHALL have status 201
- **AND** the document's stored `purpose` SHALL be `training`

#### Scenario: Upload with an invalid purpose value is rejected

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a PDF file and `purpose=invalid-value`
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate `purpose` must be `query` or `training`

#### Scenario: Platform retention stores the original durably

- **GIVEN** a tenant whose profile selects `platform_blob` retention
- **WHEN** a document is uploaded
- **THEN** the bytes SHALL be written to the durable content store
- **AND** the document's persisted storage reference SHALL be the value that store returned
- **AND** the document's `retention_mode` SHALL be `platform_blob`

#### Scenario: Ephemeral retention stores no durable original

- **GIVEN** a tenant whose profile selects `ephemeral` retention
- **WHEN** a document is uploaded and processing completes
- **THEN** the response SHALL have status 201
- **AND** the document's `retention_mode` SHALL be `ephemeral`
- **AND** the document's persisted storage reference SHALL be NULL after processing reaches a terminal state

### Requirement: Async OCR Processing

The system SHALL process ingested documents asynchronously. The processing worker SHALL be dispatched with the document identity and tenant identity only, and SHALL obtain the document's bytes by applying the content resolution implied by the document's recorded `retention_mode` — from the durable content store for `platform_blob`, from the working content store for `ephemeral`, and by asking the originating source adapter for `source_only`. The worker SHALL NOT read a storage path supplied by its caller.

The system SHALL select the extraction strategy from the document's resolved media type — resolving in order from the declared media type, then the filename extension, then content inspection — and SHALL NOT derive it from the storage reference. For PDF documents, the system SHALL extract text using PyMuPDF, falling back to rasterised OCR when no text layer is present. For image documents (JPEG, PNG, TIFF), the system SHALL run OCR using Tesseract via `pytesseract`. Text spans SHALL be stored in `tenant_{tid}.document_text_spans` with character offsets.

The document status SHALL transition from `pending` → `processing` → `processed` on success, or `pending` → `processing` → `failed` on error. The transition to `processing` SHALL only apply to a document still in `pending`, so that a repeated dispatch performs no work. Before reprocessing a document, the system SHALL delete that document's existing text spans and chunks so that reprocessing SHALL NOT duplicate them; this deletion SHALL occur only after the bytes have been successfully resolved.

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

#### Scenario: DOCX text extraction succeeds

- **GIVEN** a document with `status: "pending"` and content type `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- **WHEN** the OCR processing worker runs
- **AND** `python-docx` successfully extracts text from the DOCX
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans` with extracted text and character offsets

#### Scenario: DOC text extraction succeeds

- **GIVEN** a document with `status: "pending"` and content type `application/msword`
- **WHEN** the OCR processing worker runs
- **AND** `antiword` successfully extracts text from the DOC
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans` with extracted text and character offsets

#### Scenario: OCR processing fails

- **GIVEN** a corrupt PDF document with `status: "pending"`
- **WHEN** the OCR processing worker runs
- **AND** PyMuPDF raises an extraction error
- **THEN** the document status SHALL be updated to `"failed"`
- **AND** the document record SHALL contain an error message describing the failure

#### Scenario: The worker resolves bytes from persisted state alone

- **GIVEN** a dispatched processing job carrying only a document id and tenant id
- **WHEN** the worker runs
- **THEN** it SHALL resolve the bytes using the document's recorded `retention_mode`
- **AND** it SHALL NOT require a storage path, media type, or bytes from the dispatcher

#### Scenario: Declared media type selects the extractor

- **GIVEN** a document whose declared media type is `image/png` and whose storage reference ends in `.bin`
- **WHEN** the OCR processing worker runs
- **THEN** the image OCR path SHALL be selected
- **AND** the storage reference SHALL NOT be inspected to make that choice

#### Scenario: Filename extension is the fallback when the declared type is generic

- **GIVEN** a PDF uploaded with content type `application/octet-stream` and filename `report.pdf`
- **WHEN** the OCR processing worker runs
- **THEN** the PDF extraction path SHALL be selected
- **AND** the outcome SHALL match the behaviour before this change

#### Scenario: Repeated dispatch performs no second extraction

- **GIVEN** a document that has already transitioned out of `pending`
- **WHEN** processing is dispatched for it a second time
- **THEN** no extraction SHALL run
- **AND** the document's text spans SHALL be unchanged in number

#### Scenario: Reprocessing does not duplicate spans or chunks

- **GIVEN** a processed `purpose='query'` document under `platform_blob` retention, with a known number of text spans and chunks
- **WHEN** the document is reprocessed
- **THEN** the resulting number of text spans SHALL equal the number produced by a single run
- **AND** the resulting number of chunks SHALL equal the number produced by a single run

#### Scenario: Reprocessing one document does not affect another

- **GIVEN** two processed documents in the same tenant schema
- **WHEN** one of them is reprocessed
- **THEN** the other document's text spans and chunks SHALL be unchanged

#### Scenario: Derived data is not deleted when bytes cannot be resolved

- **GIVEN** a processed document whose bytes are no longer resolvable
- **WHEN** reprocessing is attempted
- **THEN** the attempt SHALL fail before any deletion
- **AND** the document's existing text spans and chunks SHALL be unchanged

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

### Requirement: Document provenance and retention metadata

The system SHALL record, on every document, its origin, `source_type`, `source_id`, and `retention_mode`, and SHALL record where available its external identity, source version, source-created timestamp, source-modified timestamp, and opaque source metadata. `retention_mode` SHALL hold exactly one of `platform_blob`, `ephemeral`, or `source_only`, and SHALL NOT be inferred from the storage reference. These fields SHALL be added additively with defaults so that existing rows, existing queries, and existing API responses continue to function unchanged. No uniqueness constraint SHALL be placed on the external identity by this change. This change SHALL persist the storage reference in the existing `blob_path` column and SHALL NOT introduce a second column for the same value; renaming it is the responsibility of the named `document-metadata-column-reconciliation` change.

#### Scenario: Existing documents remain valid after migration

- **GIVEN** a tenant schema containing documents created before this change
- **WHEN** the migration is applied
- **THEN** every existing row SHALL remain readable
- **AND** its `source_type` SHALL default to `platform_upload`
- **AND** its `source_id` SHALL default to `platform-upload`
- **AND** its `retention_mode` SHALL default to `platform_blob`

#### Scenario: The migration reaches every existing tenant schema

- **GIVEN** a database with several provisioned tenant schemas
- **WHEN** the migration is applied
- **THEN** every `tenant_%` schema's `documents` table SHALL carry the new columns
- **AND** `tenant_template.documents` SHALL carry them

#### Scenario: A newly provisioned tenant inherits the columns

- **GIVEN** the migration has been applied
- **WHEN** a new tenant is provisioned
- **THEN** its `documents` table SHALL carry the new columns

#### Scenario: Retention mode is constrained to the declared values

- **GIVEN** an attempt to write a document row whose `retention_mode` is not one of `platform_blob`, `ephemeral`, or `source_only`
- **WHEN** the write is performed
- **THEN** it SHALL be rejected

#### Scenario: Duplicate external identities are permitted

- **GIVEN** two documents in one tenant carrying the same `source_id` and external identity
- **WHEN** both are inserted
- **THEN** both inserts SHALL succeed
- **AND** no constraint violation SHALL be raised

#### Scenario: No second storage-reference column is introduced

- **GIVEN** the migration
- **WHEN** the columns it adds are enumerated
- **THEN** none SHALL duplicate the existing `blob_path` column's purpose

### Requirement: Document visibility by ingesting actor

The system SHALL record an ingesting actor on every document, distinguishing a human user from a source system. Listing SHALL restrict a non-administrative user to documents ingested by that user **only when the ingesting actor is a human**. A document whose ingesting actor is a source system SHALL be visible to every user of that tenant, so that document listing and chat retrieval agree on what a user may see.

#### Scenario: A user sees their own uploads

- **GIVEN** a non-administrative user who has uploaded a document
- **WHEN** they list documents
- **THEN** their own document SHALL be listed

#### Scenario: A user does not see another user's upload

- **GIVEN** two non-administrative users in one tenant, each having uploaded a document
- **WHEN** the first lists documents
- **THEN** the second user's document SHALL NOT be listed

#### Scenario: A system-ingested document is visible tenant-wide

- **GIVEN** a document whose ingesting actor is a source system rather than a human
- **WHEN** a non-administrative user lists documents
- **THEN** that document SHALL be listed

#### Scenario: Listing and retrieval agree

- **GIVEN** a `purpose='query'` document whose ingesting actor is a source system, and a non-administrative user
- **WHEN** that user asks a question whose answer cites that document
- **THEN** the cited document SHALL also be listable by that user

#### Scenario: Administrators are unaffected

- **GIVEN** a user whose role is `tenant_admin`
- **WHEN** they list documents
- **THEN** every non-deleted document in the tenant SHALL be listed regardless of ingesting actor

### Requirement: Document Content Hashing and Duplicate Identification

The system SHALL compute a deterministic SHA-256 content hash over the raw bytes of every successfully uploaded document and persist it as a 64-character lowercase hex digest in the `checksum` column of `tenant_{tid}.documents`. The hash SHALL depend only on the file's byte content — never on its filename, upload time, uploading user, `purpose`, or document ID — so that byte-identical files always produce the same hash and any difference in bytes produces a different hash.

Before inserting the new document record, the system SHALL look up the earliest existing document in the same tenant schema whose `checksum` equals the newly computed hash and whose `status` is not `deleted`. When such a document exists, the upload response SHALL include `duplicate_of` set to that document's ID; otherwise `duplicate_of` SHALL be `null`. The lookup SHALL be scoped to the caller's tenant schema and SHALL additionally filter on `tenant_id`, so that documents belonging to other tenants can never be reported as duplicates.

A duplicate upload SHALL NOT be rejected, merged, or deduplicated. The upload SHALL still return HTTP 201 with its own new document ID and `status: "pending"`, SHALL store its own blob, and SHALL leave the previously uploaded document's record, ownership, extraction history, and annotations entirely unmodified.

The upload response SHALL include the computed `checksum`, and the document-metadata GET response SHALL include the stored `checksum`.

#### Scenario: Upload persists a SHA-256 content hash

- **GIVEN** an authenticated tenant user
- **WHEN** they POST a PDF file to `/api/v1/documents`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `checksum` that is the 64-character lowercase SHA-256 hex digest of the uploaded bytes
- **AND** the stored `checksum` column for that document SHALL hold the same value

#### Scenario: Identical content produces the same deterministic hash

- **GIVEN** the same file bytes are hashed twice
- **WHEN** the content hash is computed for each
- **THEN** both hashes SHALL be identical
- **AND** the hash SHALL be a 64-character lowercase hex string

#### Scenario: Different filenames with identical content are recognised as identical content

- **GIVEN** an authenticated tenant user has already uploaded a file as `original.pdf`
- **WHEN** they upload the exact same bytes as `renamed-copy.pdf`
- **THEN** the response SHALL have status 201 with a new document ID distinct from the first
- **AND** both documents' stored `checksum` values SHALL be equal
- **AND** the second response's `duplicate_of` SHALL be the first document's ID

#### Scenario: Different content is not reported as a duplicate

- **GIVEN** an authenticated tenant user has already uploaded a file
- **WHEN** they upload a different file whose bytes differ
- **THEN** the two documents' stored `checksum` values SHALL differ
- **AND** the second response's `duplicate_of` SHALL be `null`

#### Scenario: Duplicate upload does not modify the original document

- **GIVEN** an authenticated tenant user has already uploaded a file that is now in `processed` status
- **WHEN** they upload the exact same bytes again
- **THEN** the original document SHALL still exist with its original ID, filename, `uploaded_by`, and status
- **AND** the new document SHALL have its own distinct ID and `status: "pending"`

#### Scenario: Duplicate detection does not cross tenant boundaries

- **GIVEN** tenant A has uploaded a file
- **WHEN** a user of tenant B uploads the exact same bytes
- **THEN** tenant B's response `duplicate_of` SHALL be `null`

#### Scenario: A soft-deleted document is not reported as a duplicate

- **GIVEN** an authenticated tenant user uploaded a file and then deleted it, leaving it in `deleted` status
- **WHEN** they upload the exact same bytes again
- **THEN** the response `duplicate_of` SHALL be `null`

#### Scenario: Document metadata exposes the stored checksum

- **GIVEN** a document that was uploaded after content hashing was introduced
- **WHEN** a tenant user GETs `/api/v1/documents/{doc_id}`
- **THEN** the response's `document` object SHALL include the stored `checksum`

