## ADDED Requirements

### Requirement: Imported Documents List View

The system SHALL provide an "Imported Documents" view listing `imported_annotations` rows document-wise, one row per list entry, visible to users with role `annotator` or `tenant_admin`. The list SHALL be paginated and SHALL support filtering by `source_file` and by entity type present in the row. Each list entry SHALL display at minimum: `source_file`, `row_index`, the set of distinct entity types present, and whether the row has been reviewed.

#### Scenario: List view visible to annotator and tenant_admin

- **GIVEN** a user with role `annotator` or `tenant_admin`
- **WHEN** they open the Imported Documents view
- **THEN** the list SHALL render, showing one entry per `imported_annotations` row for their tenant

#### Scenario: List view hidden for business_user role

- **GIVEN** a user with role `business_user`
- **WHEN** they attempt to access the Imported Documents view
- **THEN** access SHALL be denied (view not shown / API returns 403)

#### Scenario: List is paginated

- **GIVEN** a tenant with 3,000 imported rows
- **WHEN** the Imported Documents list is requested
- **THEN** the response SHALL return a bounded page of results with pagination metadata (e.g. page, per_page, total)

#### Scenario: Filter by source file

- **GIVEN** imported rows exist from two different source files, "batch1.txt" and "batch2.jsonl"
- **WHEN** the list is filtered by `source_file=batch1.txt`
- **THEN** only rows imported from "batch1.txt" SHALL be returned

#### Scenario: Filter by entity type

- **GIVEN** imported rows exist with a mix of entity types (PER, ORG, DATE)
- **WHEN** the list is filtered by entity type "ORG"
- **THEN** only rows containing at least one `B-ORG`/`I-ORG` tag SHALL be returned

### Requirement: Token-Level Rendering with Entity Colors

When a user opens an imported row, the system SHALL render every token in `tokens[]`. Tokens tagged `O` SHALL render as plain, unselected text. Contiguous runs of `B-<TYPE>` followed by zero or more `I-<TYPE>` tokens SHALL render as a single selected span, colored using the same client-side entity-color scheme used in the interactive annotation workspace (color assigned by the tenant's entity type order, not persisted).

#### Scenario: O tokens render unselected

- **GIVEN** an imported row with tags `["O", "B-PER", "O"]`
- **WHEN** the row is opened for review
- **THEN** the first and third tokens SHALL render as plain, unselected text

#### Scenario: B/I run renders as one colored span

- **GIVEN** an imported row with tokens `["Jane", "Doe", "works"]` and tags `["B-PER", "I-PER", "O"]`
- **WHEN** the row is opened for review
- **THEN** "Jane" and "Doe" SHALL render together as a single selected span
- **AND** the span SHALL be colored using the "PER" entity type's color from the tenant's entity-color scheme
- **AND** "works" SHALL render as plain, unselected text

#### Scenario: Entity color matches the interactive workspace

- **GIVEN** the tenant's entity type "PER" is assigned a color of `#6366f1` in the interactive annotation workspace
- **WHEN** a "PER"-tagged span is rendered in the Imported Documents review surface
- **THEN** the span SHALL use the same `#6366f1` color

### Requirement: Editing Imported Row Annotations

Annotators and tenant admins SHALL be able to change annotations on an imported row: retype an existing span's entity type, delete a span (its tokens revert to `O`), and create a new span by selecting a contiguous token range and assigning it an entity type. Entity types used SHALL be validated against the tenant's configured entity types (`entity_definitions`), using the same validation as import-time. Saved edits SHALL be persisted by updating the row's `tags[]` array in place.

#### Scenario: Retype a span's entity type

- **GIVEN** an imported row with a span tagged as "PER" over tokens 0-1
- **WHEN** the user changes the span's entity type to "ORG"
- **THEN** the row's `tags[]` SHALL be updated so tokens 0-1 read `["B-ORG", "I-ORG"]`

#### Scenario: Delete a span

- **GIVEN** an imported row with a span tagged as "PER" over tokens 0-1
- **WHEN** the user deletes the span
- **THEN** the row's `tags[]` SHALL be updated so tokens 0-1 read `["O", "O"]`

#### Scenario: Create a new span from unselected tokens

- **GIVEN** an imported row where tokens 3-4 are tagged `["O", "O"]`
- **WHEN** the user selects tokens 3-4 and assigns entity type "DATE"
- **THEN** the row's `tags[]` SHALL be updated so tokens 3-4 read `["B-DATE", "I-DATE"]`

#### Scenario: Reject unknown entity type on edit

- **GIVEN** the tenant's configured entity types do not include "PRODUCT"
- **WHEN** the user attempts to assign entity type "PRODUCT" to a token range
- **THEN** the edit SHALL be rejected with a validation error
- **AND** the row's `tags[]` SHALL remain unchanged

### Requirement: Review Progress Tracking

The system SHALL track whether an imported row has been reviewed. `imported_annotations` SHALL gain `reviewed` (boolean, default false), `reviewed_at`, and `reviewed_by` fields. Saving any edit to a row, or explicitly marking it reviewed without edits, SHALL set `reviewed = true` along with `reviewed_at` and `reviewed_by`. The list view SHALL allow filtering by reviewed state.

#### Scenario: Saving an edit marks the row reviewed

- **GIVEN** an unreviewed imported row
- **WHEN** the user saves any tag edit to the row
- **THEN** the row's `reviewed` field SHALL become `true`
- **AND** `reviewed_at` and `reviewed_by` SHALL be set

#### Scenario: Marking reviewed without edits

- **GIVEN** an unreviewed imported row the user has inspected but not changed
- **WHEN** the user explicitly marks the row as reviewed
- **THEN** the row's `reviewed` field SHALL become `true` without altering `tags[]`

#### Scenario: Filter list by reviewed state

- **GIVEN** a tenant with both reviewed and unreviewed imported rows
- **WHEN** the list is filtered to show only unreviewed rows
- **THEN** only rows with `reviewed = false` SHALL be returned

### Requirement: Imported Rows Remain Decoupled from the Annotation Task Pipeline

Reviewing or editing an imported row through this surface SHALL NOT create or modify any `documents`, `annotation_tasks`, or `spans` record. This surface operates exclusively on `imported_annotations`.

#### Scenario: Editing an imported row does not create a task

- **GIVEN** an imported row with no associated annotation task
- **WHEN** the user edits and saves the row's annotations through the Imported Documents review surface
- **THEN** no new `annotation_tasks` row SHALL be created
- **AND** no new `documents` or `spans` row SHALL be created
