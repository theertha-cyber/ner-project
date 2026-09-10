## ADDED Requirements

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
SHALL offer a "Request training" action for eligible files that calls
`POST /api/v1/training-retrain-requests`. There SHALL be no "review annotations" gate
imposed on the Tenant Admin between an eligible import and a training request.

#### Scenario: Request training from an eligible import

- **GIVEN** a training-eligible imported file
- **WHEN** a Tenant Admin clicks "Request training"
- **THEN** a training job SHALL be created in `pending_approval`
- **AND** no annotation-review step SHALL have been required first

## MODIFIED Requirements

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
