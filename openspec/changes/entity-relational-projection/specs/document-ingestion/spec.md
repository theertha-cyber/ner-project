## MODIFIED Requirements

### Requirement: Document Metadata API

The system SHALL expose endpoints to list, get, and delete document metadata. Listing SHALL support pagination and optional `?status=` filter. Getting a single document SHALL return metadata including current status and file size. Deleting a document SHALL soft-delete by setting `status: "deleted"` and SHALL NOT remove the blob from MinIO.

Deletion SHALL additionally remove the document's rows from every generated relational entity table, including its `subject` row, inside the same transaction that already clears `document_chunks`, `document_text_spans`, `extracted_entities`, and `document_entities`. The delete statements SHALL be produced by the shared pure statement builder used by the extraction worker, so the synchronous and asynchronous callers execute identical statements. Because the generated child tables declare no foreign key to `documents`, this propagation is the mechanism that maintains referential integrity; without it a deleted document would continue to answer generated SQL queries.

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

#### Scenario: Deletion clears the document's relational rows

- **GIVEN** an extracted document with a `subject` row and rows in two generated child tables
- **WHEN** a tenant user DELETEs that document
- **THEN** the document SHALL have no rows in any generated child table
- **AND** it SHALL have no `subject` row
- **AND** its `document_entities` rows SHALL also be gone

#### Scenario: Relational deletion shares the document's transaction

- **GIVEN** a document delete that raises after the `document_entities` delete
- **WHEN** the transaction rolls back
- **THEN** the document's relational rows SHALL still be present
- **AND** the document's `status` SHALL NOT be `"deleted"`

#### Scenario: A deleted document stops answering generated SQL

- **GIVEN** a deleted document that previously contributed rows to a generated child table
- **WHEN** that table is queried
- **THEN** it SHALL return no rows for that document

#### Scenario: Deletion tolerates a document with no relational rows

- **GIVEN** a document that was uploaded but never extracted
- **WHEN** a tenant user DELETEs it
- **THEN** the response SHALL have status 200
- **AND** the delete SHALL NOT raise despite there being no `subject` row
