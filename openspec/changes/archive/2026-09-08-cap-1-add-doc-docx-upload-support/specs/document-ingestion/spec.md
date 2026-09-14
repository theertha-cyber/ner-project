## MODIFIED Requirements

### Requirement: Document Upload

The system SHALL accept document uploads via multipart/form-data for PDF, JPEG, PNG, TIFF, DOC, and DOCX files. On successful upload, the system SHALL store the file in MinIO at path `tenants/{tid}/documents/{docId}.{ext}`, create a metadata record in `tenant_{tid}.documents`, and return HTTP 201 with the document metadata. The system SHALL reject files larger than 50MB with HTTP 413. Uploads SHALL accept an optional `purpose` field (`query` or `training`), defaulting to `query` when omitted, recorded on the document's metadata record.

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

### Requirement: Async OCR Processing

The system SHALL process uploaded documents asynchronously. For PDF documents, the system SHALL extract text using PyMuPDF. For image documents (JPEG, PNG, TIFF), the system SHALL run OCR using Tesseract via `pytesseract`. For DOCX documents, the system SHALL extract text using `python-docx` by iterating paragraphs. For DOC documents, the system SHALL extract text using `antiword` subprocess, falling back to an error if `antiword` is unavailable. Text spans SHALL be stored in `tenant_{tid}.document_text_spans` with character offsets. The document status SHALL transition from `pending` → `processing` → `processed` on success, or `pending` → `processing` → `failed` on error.

#### Scenario: PDF text extraction succeeds

- **GIVEN** a document with `status: "pending"` and content type `application/pdf`
- **WHEN** the OCR processing worker runs
- **AND** PyMuPDF successfully extracts text from the PDF
- **THEN** the document status SHALL be updated to `"processed"`
- **AND** text spans SHALL be inserted into `document_text_spans` with extracted text and character offsets

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
