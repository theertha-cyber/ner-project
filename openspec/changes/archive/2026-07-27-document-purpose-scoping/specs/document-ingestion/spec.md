## MODIFIED Requirements

### Requirement: Document Upload

The system SHALL accept document uploads via multipart/form-data for PDF, JPEG, PNG, and TIFF files. On successful upload, the system SHALL store the file in MinIO at path `tenants/{tid}/documents/{docId}.{ext}`, create a metadata record in `tenant_{tid}.documents`, and return HTTP 201 with the document metadata. The system SHALL reject files larger than 50MB with HTTP 413. Uploads SHALL accept an optional `purpose` field (`query` or `training`), defaulting to `query` when omitted, recorded on the document's metadata record.

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
