## ADDED Requirements

### Requirement: CSV file ingestion

The document ingestion pipeline SHALL accept CSV files (`.csv`) through the same upload contract as the other supported file types, and SHALL reject unsupported file types with the existing rejection path. The upload validation error message SHALL list `.csv` among the allowed extensions.

#### Scenario: Upload a CSV document

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a `.csv` file as multipart/form-data
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `filename`, `content_type`, and `status` with value `pending`

#### Scenario: Unsupported file type remains rejected

- **GIVEN** an authenticated tenant user
- **WHEN** they POST to `/api/v1/documents` with a `.exe` file
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate the file type is not supported
- **AND** the error message SHALL list the allowed extensions including `.csv`

### Requirement: CSV text extraction branch

The ingestion worker SHALL parse CSV rows into normalized text spans and SHALL flow them through the same chunking, embedding, and retrieval pipeline used for query documents. The parser SHALL handle delimiter and row-shape edge cases so that one malformed row does not fail the whole document.

#### Scenario: CSV processing writes spans and chunks

- **GIVEN** a `.csv` file uploaded with purpose `query` and processed by the ingestion worker
- **THEN** the file SHALL be recognized as a CSV media type
- **AND** text spans SHALL be written to `document_text_spans`, one per CSV row
- **AND** downstream chunks SHALL be generated through the existing chunking and embedding path

#### Scenario: CSV with quoted delimiters and ragged rows is normalized

- **GIVEN** a CSV file whose rows differ in column count and whose fields include commas inside quotes
- **WHEN** the ingestion worker processes the file
- **THEN** every row SHALL contribute a normalized text span
- **AND** the document SHALL reach `processed` status rather than `failed`