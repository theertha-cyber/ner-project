## MODIFIED Requirements

### Requirement: Document Upload

The system SHALL accept document uploads via multipart/form-data for PDF, JPEG, PNG, and TIFF files. On successful upload, the system SHALL submit the document to the application ingestion operation, which SHALL resolve the tenant's retention mode, write the bytes to the durable content store under `platform_blob` retention or to the working content store under `ephemeral` retention, create a metadata record in `tenant_{tid}.documents`, and return HTTP 201 with the document metadata. The system SHALL reject files larger than 50MB with HTTP 413. Uploads SHALL accept an optional `purpose` field (`query` or `training`), defaulting to `query` when omitted, recorded on the document's metadata record.

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

## ADDED Requirements

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
