# Annotation Workspace

## Purpose

Annotator-facing workspace for creating and managing entity spans on documents, pre-labeling via base label mapping, annotation task management, and dataset export.

---

## Requirements

### Requirement: Span CRUD

The system SHALL expose endpoints to create, read, update, and delete entity spans on a document's text. Each span SHALL reference an entity type from the tenant's configured entity types, specify start and end character offsets into the document text, and carry a confidence score. Spans SHALL be stored in the tenant's isolated schema. Only confirmed (non-suggested) spans are returned by these endpoints; suggested spans from pre-labeling are managed separately.

#### Scenario: Create a span on a processed document

- **GIVEN** a document with `status: "processed"` and known text content
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/spans` with `{entity_type: "PER", char_start: 10, char_end: 25, text: "John Doe"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `entity_type`, `char_start`, `char_end`, `text`, `confidence: 1.0`

#### Scenario: List spans on a document

- **GIVEN** a document with two existing confirmed spans
- **WHEN** an annotator GETs `/api/v1/documents/{doc_id}/spans`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain both spans with all fields

#### Scenario: Update a span

- **GIVEN** a span with ID "span-123" and entity_type "PER"
- **WHEN** an annotator PATCHes `/api/v1/documents/{doc_id}/spans/span-123` with `{entity_type: "ORG"}`
- **THEN** the response SHALL have status 200
- **AND** the span's entity_type SHALL be updated to "ORG"

#### Scenario: Delete a span

- **GIVEN** a span with ID "span-123"
- **WHEN** an annotator DELETEs `/api/v1/documents/{doc_id}/spans/span-123`
- **THEN** the response SHALL have status 204
- **AND** the span SHALL be removed from the database

#### Scenario: Create span with invalid entity type returns 422

- **GIVEN** a processed document and an entity type "INVALID" not in the tenant's configured types
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/spans` with `{entity_type: "INVALID", char_start: 0, char_end: 5, text: "hello"}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the entity type is not valid

### Requirement: Pre-labeling

The system SHALL generate suggested entity spans for a document using each entity type's `examples` configuration. Suggested spans SHALL be stored in a separate `suggested_spans` table with confidence scores. Pre-labeling SHALL replace all existing suggested spans for the document with newly generated ones. For MVP, the pre-labeling logic SHALL be a deterministic mock — it SHALL scan document text for case-insensitive matches against example phrases, using a longest-match-wins strategy when multiple examples overlap at the same position.

The system SHALL use the `examples` column from `entity_definitions` as the keyword source. The `base_label_mapping` column SHALL NOT be used for keyword derivation during MVP.

#### Scenario: Pre-label a processed document

- **GIVEN** a processed document with text "Vellore Institute of Technology is a deemed university" and a tenant with entity type `institute` having `examples: ["Vellore Institute of Technology"]`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a suggested span for "Vellore Institute of Technology" (entity_type: "institute")
- **AND** the suggested span SHALL have `confidence < 1.0`
- **AND** the suggested span SHALL have `char_start: 0` and `char_end: 31`

#### Scenario: Pre-label matching is case-insensitive

- **GIVEN** a processed document with text "Vellore INSTITUTE of Technology" and a tenant with entity type `institute` having `examples: ["Vellore Institute of Technology"]`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a suggested span for "Vellore INSTITUTE of Technology" (entity_type: "institute")

#### Scenario: Pre-label longest match wins for overlapping examples

- **GIVEN** a processed document with text "Apple Inc is based in Cupertino" and a tenant with entity type `organization` having `examples: ["Apple Inc", "Apple"]`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain exactly 1 suggested span for "Apple Inc" (char_start: 0, char_end: 9)
- **AND** there SHALL NOT be a separate span for "Apple"

#### Scenario: Pre-label replaces existing suggestions

- **GIVEN** a document with two existing suggested spans from a previous pre-label call
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel` again
- **THEN** the old suggested spans SHALL be removed
- **AND** the new suggested spans SHALL be returned

#### Scenario: List suggested spans

- **GIVEN** a document with 3 suggested spans from pre-labeling
- **WHEN** an annotator GETs `/api/v1/documents/{doc_id}/spans?type=suggested`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain the 3 suggested spans

#### Scenario: Promote a suggested span to confirmed

- **GIVEN** a suggested span with ID "suggest-1" for entity type "institute" at offsets 10-31
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/spans/promote/suggest-1`
- **THEN** the response SHALL have status 201
- **AND** a new confirmed span SHALL be created with the same offsets, text, and entity_type
- **AND** the suggested span SHALL be removed

### Requirement: Annotation Task Management

The system SHALL allow Tenant Admins to create annotation tasks that assign a document to a specific annotator. Each task SHALL track status through `unannotated` → `in-progress` → `completed`. A document SHALL have at most one active (non-completed) task at any time. Tasks SHALL be stored in the tenant's isolated schema.

#### Scenario: Create an annotation task

- **GIVEN** a processed document and an active annotator user
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with `{document_id: "doc-123", annotator_user_id: "user-456"}`
- **THEN** the response SHALL have status 201
- **AND** the task SHALL have `status: "unannotated"`

#### Scenario: Create task for already-assigned document returns 409

- **GIVEN** document "doc-123" already has an annotation task with status `in-progress`
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with `{document_id: "doc-123", annotator_user_id: "user-789"}`
- **THEN** the response SHALL have status 409
- **AND** the error SHALL indicate the document already has an active task

#### Scenario: List annotation tasks with status filter

- **GIVEN** 2 tasks with status `completed` and 1 with `unannotated`
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-tasks?status=unannotated`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain only the unannotated task

#### Scenario: Update annotation task status

- **GIVEN** a task with ID "task-789" and status `unannotated`
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "in-progress"}`
- **THEN** the response SHALL have status 200
- **AND** the task status SHALL be `in-progress`

#### Scenario: Complete a task that has spans

- **GIVEN** a task with ID "task-789" in status `in-progress` and the document has at least one confirmed span
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "completed"}`
- **THEN** the response SHALL have status 200
- **AND** the task status SHALL be `completed`

#### Scenario: Complete a task with no spans returns 422

- **GIVEN** a task with ID "task-789" in status `in-progress` and the document has no confirmed spans
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "completed"}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the document must have at least one span before completing

### Requirement: Annotation Export

The system SHALL export a tenant's annotations in HuggingFace Dataset format (JSON lines). Each line SHALL contain `tokens` (list of tokenized words) and `tags` (list of BIO-encoded entity tags for each token). The export SHALL include all confirmed spans for all documents. Unannotated documents SHALL appear with all-O tags.

#### Scenario: Export annotation dataset

- **GIVEN** a tenant with 2 annotated documents and 1 unannotated document
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-export?format=datasets`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL be JSON lines (one JSON object per line)
- **AND** each line SHALL contain `tokens` and `tags` arrays
- **AND** there SHALL be 3 lines (one per document)

#### Scenario: Export with entity type filter

- **GIVEN** a tenant with spans of types PER and ORG across documents
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-export?format=datasets&entity_types=PER`
- **THEN** the response SHALL have status 200
- **AND** only PER tags SHALL appear in the BIO encoding; ORG spans SHALL be encoded as O

#### Scenario: Export for specific documents only

- **GIVEN** a tenant with 5 documents, 2 of which are annotated
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-export?format=datasets&document_ids=doc-001,doc-002`
- **THEN** the response SHALL have status 200
- **AND** only the specified documents SHALL appear in the output
