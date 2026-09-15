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

The backend endpoint `POST /api/v1/annotation-import` SHALL require the `tenant_admin` role.
It SHALL store every parsed row. Rows whose tags reference entity types not present in
`public.entity_definitions` for the tenant SHALL be stored **marked as pending mapping**
rather than skipped, and the endpoint SHALL return an `unmapped_types` array. The response
SHALL continue to include `imported_count` (rows stored and immediately usable — i.e. with
no unmapped type), and SHALL add `unmapped_types` and `pending_count`. The existing parsing
behaviour (CoNLL/JSONL, 50MB limit, MIME-type validation) SHALL remain unchanged. The
endpoint SHALL create or update an `annotation_imports` header row for the file.

#### Scenario: Backend response schema change is backward-compatible

- **GIVEN** an existing caller that only reads `imported_count` from the response
- **WHEN** the modified endpoint returns a response with `imported_count`, `pending_count`, `unmapped_types`, and `warnings`
- **THEN** the existing caller SHALL still see the `imported_count` field, now carrying the count of immediately-usable rows (rows with no unmapped type)

#### Scenario: Backend skips rows with unknown entity types

- **GIVEN** a file with 3 rows, where row 1 has valid entity types, row 2 has unknown entity type "FOO", and row 3 has valid entity types
- **WHEN** the backend processes the import
- **THEN** all 3 rows SHALL be inserted into `imported_annotations`
- **AND** row 2 SHALL be marked pending mapping rather than dropped
- **AND** row 1 and row 3 SHALL be immediately usable
- **AND** the response SHALL have `imported_count: 2`, `pending_count: 1`, and `unmapped_types` naming `FOO`

#### Scenario: Backend returns entity type breakdown

- **GIVEN** a file with rows containing entity types PER, ORG, and DATE (all known)
- **WHEN** the backend successfully imports
- **THEN** the response SHALL include `entity_type_counts` with counts for each

#### Scenario: Import requires tenant_admin

- **GIVEN** a valid annotation file
- **WHEN** a user with the `annotator` role calls `POST /api/v1/annotation-import`
- **THEN** the response SHALL have status 403

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

### Requirement: Unmapped Entity Types Are Held, Not Dropped

When an imported file contains rows whose tags reference entity types not present in
`public.entity_definitions` for the tenant, the system SHALL still store those rows (marked
as pending mapping) and SHALL return an `unmapped_types` array naming each unknown type and
the number of rows affected. The system SHALL NOT silently discard those rows and SHALL NOT
create an entity type as a side effect of import.

#### Scenario: Import surfaces unmapped types instead of skipping rows

- **GIVEN** a tenant whose active entity types are `person` and `org`
- **WHEN** a Tenant Admin imports a file of 100 rows where 12 rows use the tag `JOB_TITLE`
- **THEN** the response SHALL have status 201
- **AND** all 100 rows SHALL be stored
- **AND** the response SHALL contain `unmapped_types` including `{ "type": "JOB_TITLE", "row_count": 12 }`
- **AND** no entity type `JOB_TITLE` SHALL have been created

#### Scenario: A fully-known file reports no unmapped types

- **GIVEN** a file whose every tag matches an active entity type
- **WHEN** it is imported
- **THEN** `unmapped_types` SHALL be empty
- **AND** the file's `annotation_imports` row SHALL be created with `training_eligible_at` set

### Requirement: Entity Type Mapping

The system SHALL provide `POST /api/v1/annotation-imports/{source_file}/type-map` accepting
a mapping from each unmapped type to either (a) the name of an existing active entity type
or (b) a request to create a new entity type. For (a) the system SHALL rewrite the stored
tags on the affected rows to the target type, retaining the original value in the file's
`type_map` record. For (b) the system SHALL create the entity type through the existing
`entity-config` creation API and then apply it as in (a). When no unmapped type remains,
the system SHALL set the file's `training_eligible_at`.

#### Scenario: Map an unknown type to an existing entity type

- **GIVEN** an imported file with unmapped type `JOB_TITLE` on 12 rows and an active entity type `job_title`
- **WHEN** a Tenant Admin maps `JOB_TITLE` → `job_title`
- **THEN** those 12 rows' tags SHALL be rewritten to reference `job_title`
- **AND** the file's `type_map` SHALL record `JOB_TITLE → job_title`
- **AND** the file SHALL become training-eligible if no other unmapped type remains

#### Scenario: Map an unknown type by creating a new entity type

- **GIVEN** an imported file with unmapped type `contract_id` and no matching entity type
- **WHEN** a Tenant Admin maps `contract_id` by choosing "create new"
- **THEN** an entity type `contract_id` SHALL be created through the entity-config API at version 1
- **AND** the affected rows SHALL reference it
- **AND** the created type SHALL carry import provenance

#### Scenario: Mapping never creates a type implicitly

- **GIVEN** an imported file with an unmapped type
- **WHEN** the Tenant Admin has not submitted a type-map
- **THEN** no entity type SHALL have been created for that unmapped type
- **AND** the file SHALL NOT be training-eligible

#### Scenario: Type mapping requires tenant_admin

- **GIVEN** an imported file with an unmapped type
- **WHEN** a user with the `annotator` role calls the type-map endpoint
- **THEN** the response SHALL have status 403

### Requirement: Imported Files Are Training Data

The training dataset export SHALL include rows from `imported_annotations` belonging to
files whose `annotation_imports.training_eligible_at` is set, in the same token/tag row
shape it emits for span-derived data, tagged with an import source marker. A file that is
not training-eligible SHALL contribute no rows.

#### Scenario: Eligible imported rows appear in the export

- **GIVEN** a training-eligible imported file of 40 rows
- **WHEN** the annotation export runs
- **THEN** the export SHALL contain 40 rows derived from that file
- **AND** each SHALL have equal-length `tokens` and `tags`

#### Scenario: A file pending mapping contributes nothing

- **GIVEN** an imported file with an unresolved unmapped type
- **WHEN** the annotation export runs
- **THEN** no row from that file SHALL appear in the export

### Requirement: Request Training From an Import

The `/imported-documents` surface SHALL show, per file, whether it is training-eligible, and
SHALL offer a "Train model" action for eligible files that navigates directly to
`/training-jobs?source=import` (Models & Training, scoped to the import source) — the same
hand-off the Import landing page's own "2. Train model" step uses. The action SHALL NOT call
`POST /api/v1/training-retrain-requests` or otherwise create a System-Admin-approval request as
a side effect of the click; submitting the job remains an explicit, separate step on the
Training Jobs screen. There SHALL be no "review annotations" gate imposed on the Tenant Admin
between an eligible import and reaching that hand-off.

#### Scenario: Request training from an eligible import

- **GIVEN** a training-eligible imported file
- **WHEN** a Tenant Admin clicks "Train model"
- **THEN** the browser SHALL navigate to `/training-jobs?source=import`
- **AND** no training job SHALL have been created by the click itself
- **AND** no annotation-review step SHALL have been required first

### Requirement: Bulk-Accept Unmapped Types

For a file with one or more rows pending mapping, the `/imported-documents` file-summary list
SHALL offer an "Accept all as new types" action that submits every currently-unmapped type on
that file to `POST /api/v1/annotation-imports/{source_file}/type-map` as a `{"create": true}`
mapping, in a single request — without requiring the Tenant Admin to open each row or choose a
mapping per type first. To support this, `GET /api/v1/annotation-imports` SHALL include, per
file, an `unmapped_types` array (type name and row count) of the file's currently-unmapped
types, in the same shape the import-time response already uses.

#### Scenario: Accept all as new types creates every unmapped type in one call

- **GIVEN** an imported file with 2 unmapped types, `NAME` (3 rows) and `EMAIL` (2 rows)
- **WHEN** a Tenant Admin clicks "Accept all as new types"
- **THEN** a single `POST .../type-map` request SHALL be sent with
  `{"NAME": {"create": true}, "EMAIL": {"create": true}}`
- **AND** both entity types SHALL be created with import provenance
- **AND** the file SHALL become training-eligible once no unmapped type remains

#### Scenario: The file list reports current unmapped types

- **GIVEN** a file with 1 row still pending mapping, referencing an unknown type `XX`
- **WHEN** `GET /api/v1/annotation-imports` is called
- **THEN** that file's entry SHALL include `unmapped_types: [{"type": "XX", "row_count": 1}]`

#### Scenario: A file with nothing pending reports no unmapped types

- **GIVEN** a file with zero rows pending mapping
- **WHEN** `GET /api/v1/annotation-imports` is called
- **THEN** that file's entry SHALL include `unmapped_types: []`
