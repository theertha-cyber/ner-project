## Purpose

Allows annotators and tenant admins to bulk-import pre-labeled NER training data (CoNLL or JSONL) into a tenant's staging table via a guided upload flow: file picker → client-side parse preview → confirm → backend import → result summary.

## Requirements

### Requirement: Annotation File Import — Frontend Button

The system SHALL provide an "Import" button in the Task Queue header of the annotation page (`/annotation`). The button SHALL be visible to users with role `annotator` or `tenant_admin`. On click, the button SHALL open a native file picker filtered to `.txt`, `.json`, and `.jsonl` extensions. After the user selects a file, the system SHALL parse it client-side and display a preview slide-over before uploading.

#### Scenario: Import button visible for annotator role

- **GIVEN** a user with role `annotator` on the annotation page
- **WHEN** the annotation page renders
- **THEN** the Task Queue header SHALL display an "Import" button

#### Scenario: Import button visible for tenant_admin role

- **GIVEN** a user with role `tenant_admin` on the annotation page
- **WHEN** the annotation page renders
- **THEN** the Task Queue header SHALL display an "Import" button

#### Scenario: Import button hidden for business_user role

- **GIVEN** a user with role `business_user` on the annotation page
- **WHEN** the annotation page renders
- **THEN** the Task Queue header SHALL NOT display an "Import" button

#### Scenario: File picker opens on button click

- **GIVEN** an "Import" button is visible in the Task Queue header
- **WHEN** the user clicks the button
- **THEN** a native file picker SHALL open
- **AND** the picker SHALL default to showing `.txt`, `.json`, and `.jsonl` files

#### Scenario: Non-annotation file rejected at picker level

- **GIVEN** the file picker is open
- **WHEN** the user attempts to select a file with an extension other than `.txt`, `.json`, or `.jsonl`
- **THEN** the file SHALL be filtered out by the accept attribute (or rejected with a clear message)

### Requirement: Client-Side File Preview

The system SHALL parse the selected file client-side using pure TypeScript parsers for CoNLL (`.txt`) and JSONL (`.json`/`.jsonl`) formats. The parsed result SHALL be displayed in a slide-over panel showing: detected format, total row count, entity type breakdown with counts per type, and any unknown entity types (entity types present in the file that are not defined in the tenant's configured entity types).

#### Scenario: Preview shows CoNLL format breakdown

- **GIVEN** a user selects a `.txt` file containing valid CoNLL data with 5 sentences containing entity types PER and ORG
- **WHEN** the preview slide-over opens
- **THEN** the slide-over SHALL display "Format: CoNLL"
- **AND** SHALL display "Sentences: 5"
- **AND** SHALL display entity type counts: "PER" with count of spans found, "ORG" with count of spans found

#### Scenario: Preview shows JSONL format breakdown

- **GIVEN** a user selects a `.jsonl` file containing valid JSONL data with 10 rows containing entity types PER, ORG, and DATE
- **WHEN** the preview slide-over opens
- **THEN** the slide-over SHALL display "Format: JSONL"
- **AND** SHALL display "Rows: 10"
- **AND** SHALL display entity type counts for PER, ORG, and DATE

#### Scenario: Preview warns about unknown entity types

- **GIVEN** a user selects a file containing entity type "PRODUCT" which is not defined in the tenant's entity types
- **WHEN** the preview slide-over opens
- **THEN** the slide-over SHALL display a warning: "Unknown entity types: PRODUCT"
- **AND** SHALL indicate those rows will be skipped on import

#### Scenario: Preview shows parse error for malformed file

- **GIVEN** a user selects a file with malformed content (e.g., a CoNLL line missing the tag column)
- **WHEN** the client-side parser attempts to parse
- **THEN** the slide-over SHALL display a parse error message describing the issue
- **AND** the "Import" button SHALL be disabled

#### Scenario: Preview shows file too large error

- **GIVEN** a user selects a file larger than 50MB
- **WHEN** the client-side checks the file size
- **THEN** the slide-over SHALL display "File exceeds the 50MB maximum"
- **AND** the "Import" button SHALL be disabled

#### Scenario: Preview slide-over has confirm and cancel buttons

- **GIVEN** a valid file has been parsed and preview is displayed
- **WHEN** the preview slide-over is open
- **THEN** the slide-over SHALL display a "Cancel" button that closes the panel without uploading
- **AND** SHALL display an "Import N rows" button (where N is the total valid row count)

### Requirement: Annotation File Upload and Backend Import

When the user confirms the preview, the system SHALL upload the file to `POST /api/v1/annotation-import` as multipart/form-data. The backend SHALL parse the file, validate entity types, and import rows. Rows with valid entity types SHALL be stored in `{tenant_schema}.imported_annotations`. Rows with unknown entity types SHALL be skipped. The response SHALL include: `imported_count`, `skipped_count`, and a `warnings` array with per-row error details. The frontend SHALL display a result slide-over with imported count, skipped count, and any warnings.

#### Scenario: Successful import of all rows

- **GIVEN** a file with 100 rows, all entity types matching the tenant's configured types
- **WHEN** the user clicks "Import 100 rows" in the preview
- **THEN** the file SHALL be uploaded to `POST /api/v1/annotation-import`
- **AND** the response SHALL have status 201
- **AND** the response SHALL contain `imported_count: 100` and `skipped_count: 0`
- **AND** the frontend SHALL display a result slide-over with "100 rows imported"

#### Scenario: Partial import with some rows skipped

- **GIVEN** a file with 100 rows, 5 of which contain unknown entity types
- **WHEN** the backend processes the upload
- **THEN** the response SHALL have status 201
- **AND** SHALL contain `imported_count: 95` and `skipped_count: 5`
- **AND** SHALL contain a `warnings` array with 5 entries, each specifying the row index and "Unknown entity type: <type>"
- **AND** the frontend SHALL display "95 rows imported, 5 rows skipped" with the warning details

#### Scenario: File too large returns 413

- **GIVEN** a file larger than 50MB
- **WHEN** the backend receives the upload
- **THEN** the response SHALL have status 413
- **AND** the frontend SHALL display the error message from the response

#### Scenario: Unsupported MIME type returns 415

- **GIVEN** a file with an unsupported MIME type (e.g., `application/pdf`)
- **WHEN** the backend receives the upload
- **THEN** the response SHALL have status 415
- **AND** the frontend SHALL display the error message

### Requirement: Backend Partial Import Support

The backend endpoint `POST /api/v1/annotation-import` SHALL change its validation behavior from all-or-nothing reject to per-row filtering. Rows with entity types not present in `public.entity_definitions` for the tenant SHALL be skipped. All valid rows SHALL be inserted. The response SHALL include `imported_count`, `skipped_count`, and a `warnings` array. The existing import behavior (CoNLL/JSONL parsing, 50MB limit, MIME type validation) SHALL remain unchanged.

#### Scenario: Backend response schema change is backward-compatible

- **GIVEN** an existing caller that only reads `imported_count` from the response
- **WHEN** the modified endpoint returns a response with `imported_count`, `skipped_count`, and `warnings`
- **THEN** the existing caller SHALL still see the `imported_count` field with the correct value

#### Scenario: Backend skips rows with unknown entity types

- **GIVEN** a file with 3 rows, where row 1 has valid entity types, row 2 has unknown entity type "FOO", and row 3 has valid entity types
- **WHEN** the backend processes the import
- **THEN** row 1 SHALL be inserted into `imported_annotations`
- **AND** row 2 SHALL be skipped (not inserted)
- **AND** row 3 SHALL be inserted into `imported_annotations`
- **AND** the response SHALL have `imported_count: 2` and `skipped_count: 1`
- **AND** the `warnings` array SHALL contain an entry for row 2

#### Scenario: Backend returns entity type breakdown

- **GIVEN** a file with rows containing entity types PER, ORG, and DATE
- **WHEN** the backend successfully imports
- **THEN** the response SHALL include `entity_type_counts` with counts for each entity type found

### Requirement: Import Result Feedback

After the import completes, the system SHALL display a result slide-over with: the number of rows imported, the number of rows skipped (if any), a list of per-row warnings (if any), and a "Done" button to close the panel. The annotation page and task queue SHALL remain unaffected (import is a staging operation only).

#### Scenario: Result slide-over shows success

- **GIVEN** an import completed with 200 rows imported and 0 skipped
- **WHEN** the result slide-over opens
- **THEN** it SHALL display "200 rows imported"
- **AND** SHALL NOT display any warnings section
- **AND** the "Done" button SHALL close the panel

#### Scenario: Result slide-over shows warnings

- **GIVEN** an import completed with 195 rows imported and 5 skipped
- **WHEN** the result slide-over opens
- **THEN** it SHALL display "195 rows imported, 5 rows skipped"
- **AND** SHALL list each warning by row index and message
- **AND** the "Done" button SHALL close the panel

#### Scenario: Import does not create annotation tasks

- **GIVEN** an import of 100 rows completes successfully
- **WHEN** the user views the task queue after import
- **THEN** the task queue SHALL show the same tasks as before the import
- **AND** no new annotation tasks SHALL have been created