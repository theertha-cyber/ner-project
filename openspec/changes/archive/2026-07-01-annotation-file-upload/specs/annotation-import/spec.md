## ADDED Requirements

### Requirement: Accept JSONL annotation file uploads

The system SHALL accept multipart file uploads in JSONL format, where each line is a JSON object with `tokens` (array of strings) and `tags` (array of BIO-encoded tag strings). The system SHALL parse each line, validate that every non-O tag references a configured entity type for the tenant, and persist valid rows to the `imported_annotations` table. Rows with unknown entity types SHALL cause the entire upload to be rejected with a 422 error and a list of invalid entity types found.

#### Scenario: Upload valid JSONL file

- **GIVEN** a tenant with entity types `PER`, `ORG`, `LOC` configured
- **WHEN** a Tenant Admin uploads a JSONL file via `POST /api/v1/annotation-import` with content:
  ```
  {"tokens": ["John", "lives", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-LOC"]}
  {"tokens": ["Google", "is", "hiring"], "tags": ["B-ORG", "O", "O"]}
  ```
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `imported_count: 2`
- **AND** the `imported_annotations` table SHALL contain 2 new rows

#### Scenario: Upload JSONL with invalid entity type

- **GIVEN** a tenant with entity types `PER`, `ORG` configured
- **WHEN** a Tenant Admin uploads a JSONL file containing a line with `tags: ["B-PRODUCT", "O"]`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL list `PRODUCT` as an unrecognized entity type
- **AND** no rows SHALL be persisted to `imported_annotations`

#### Scenario: Upload JSONL with malformed JSON

- **GIVEN** a tenant with any entity types
- **WHEN** a Tenant Admin uploads a file with content `{invalid json here}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the parse failure and the line number

#### Scenario: Upload empty file

- **GIVEN** a tenant with any entity types
- **WHEN** a Tenant Admin uploads an empty file
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the file contains no valid annotation rows

### Requirement: Accept CoNLL TXT annotation file uploads

The system SHALL accept multipart file uploads in CoNLL format, where each line contains a token and its BIO tag separated by a tab, and sentences are separated by blank lines. The system SHALL parse the file, group lines into sentences, validate entity types, and persist rows to `imported_annotations`.

#### Scenario: Upload valid CoNLL file

- **GIVEN** a tenant with entity types `PER`, `ORG`, `LOC` configured
- **WHEN** a Tenant Admin uploads a TXT file via `POST /api/v1/annotation-import` with content:
  ```
  John	B-PER
  lives	O
  in	O
  NYC	B-LOC

  Google	B-ORG
  hires	O
  engineers	O
  ```
- **THEN** the response SHALL have status 201
- **AND** `imported_count: 2`

### Requirement: Store imported annotations in tenant-isolated table

The system SHALL store imported annotations in a table named `imported_annotations` within each tenant's schema (`tenant_{tid}`). The table SHALL have columns: `id UUID PRIMARY KEY`, `tokens TEXT[]`, `tags TEXT[]`, `source_file VARCHAR NOT NULL`, `row_index INTEGER NOT NULL`, `created_at TIMESTAMPTZ DEFAULT NOW()`.

#### Scenario: Table exists in tenant schema

- **GIVEN** a tenant schema `tenant_{tid}`
- **WHEN** inspecting the schema
- **THEN** the `imported_annotations` table SHALL exist
- **AND** it SHALL have all required columns

### Requirement: Export endpoint includes imported annotations

The `GET /api/v1/annotation-export` endpoint SHALL append rows from the `imported_annotations` table to its JSONL output. Each imported row SHALL produce one JSONL line with its `tokens` and `tags` arrays. Imported rows SHALL appear after all document-derived rows.

#### Scenario: Export includes both sources

- **GIVEN** a tenant with 1 annotated document (produces 1 JSONL line) and 2 imported annotation rows
- **WHEN** GET `/api/v1/annotation-export`
- **THEN** the response SHALL contain 3 JSONL lines
- **AND** the first line SHALL be from the document span
- **AND** the last 2 lines SHALL match the imported rows' `tokens` and `tags` values

#### Scenario: Export with entity type filter applies to both sources

- **GIVEN** a tenant with imported rows containing PER, ORG, and LOC tags
- **WHEN** GET `/api/v1/annotation-export?entity_types=PER`
- **THEN** imported rows with only PER and O tags SHALL appear unchanged
- **AND** imported rows with non-PER tags SHALL have those tags replaced with O

#### Scenario: Export with no document annotations and no imported annotations

- **GIVEN** a tenant with zero spans and zero imported_annotations rows
- **WHEN** GET `/api/v1/annotation-export`
- **THEN** the response SHALL have status 200
- **AND** the body SHALL be empty string

### Requirement: Validate file size and content type

The import endpoint SHALL reject files larger than 50MB with a 413 status. The endpoint SHALL accept files with MIME types `application/json`, `application/jsonl`, `text/plain`, `application/octet-stream`, or any MIME type ending in `+json`.

#### Scenario: Upload exceeds size limit

- **GIVEN** a file larger than 50MB
- **WHEN** a Tenant Admin uploads it to `POST /api/v1/annotation-import`
- **THEN** the response SHALL have status 413
- **AND** the error SHALL indicate the file exceeds the maximum size
