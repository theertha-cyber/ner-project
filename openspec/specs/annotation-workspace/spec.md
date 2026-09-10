# Annotation Workspace

## Purpose

Annotator-facing workspace for creating and managing entity spans on documents, pre-labeling via base label mapping, annotation task management, and dataset export.

---
## Requirements
### Requirement: Span CRUD

The system SHALL expose endpoints to create, read, update, and delete entity spans on a document's text. Each span SHALL reference an entity type from the tenant's configured entity types, specify start and end character offsets into the document text, and carry a confidence score. Spans SHALL be stored in the tenant's isolated schema. Only confirmed (non-suggested) spans are returned by these endpoints; suggested spans from pre-labeling are managed separately. The portal SHALL issue at most one create-span request for each single-token click or multi-token drag annotation gesture.

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

#### Scenario: Single-token annotation is saved once

- **GIVEN** an entity type is armed and an unannotated token is clicked once
- **WHEN** the browser dispatches the token click and document mouseup events for that gesture
- **THEN** exactly one create-span request SHALL be issued
- **AND** exactly one optimistic span SHALL be confirmed from its response

#### Scenario: Multi-token drag annotation is saved once

- **GIVEN** an entity type is armed and the annotator drags from one token to another
- **WHEN** the drag gesture completes
- **THEN** exactly one create-span request SHALL be issued for the inclusive calculated range

### Requirement: Pre-labeling

The system SHALL generate suggested entity spans for a document using each entity type's `examples` configuration. Suggested spans SHALL be stored in a separate `suggested_spans` table with confidence scores and a `source` field indicating which mechanism produced them (`"keyword"` for the deterministic example-matching mock, `"llm"` for LLM-based pre-labeling per the `llm-prelabeling` capability). Pre-labeling SHALL replace all existing suggested spans for the document with newly generated ones, regardless of which mechanism produced the prior suggestions. For MVP, the keyword pre-labeling logic SHALL be a deterministic mock — it SHALL scan document text for case-insensitive matches against example phrases, using a longest-match-wins strategy when multiple examples overlap at the same position.

The system SHALL use the `examples` column from `entity_definitions` as the keyword source. The `base_label_mapping` column SHALL NOT be used for keyword derivation during MVP.

#### Scenario: Pre-label a processed document

- **GIVEN** a processed document with text "Vellore Institute of Technology is a deemed university" and a tenant with entity type `institute` having `examples: ["Vellore Institute of Technology"]`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a suggested span for "Vellore Institute of Technology" (entity_type: "institute")
- **AND** the suggested span SHALL have `confidence < 1.0`
- **AND** the suggested span SHALL have `char_start: 0` and `char_end: 31`
- **AND** the suggested span SHALL have `source: "keyword"`

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

#### Scenario: List suggested spans includes their source

- **GIVEN** a document with 2 suggested spans with `source: "keyword"` and 3 suggested spans with `source: "llm"`
- **WHEN** an annotator GETs `/api/v1/documents/{doc_id}/spans?type=suggested`
- **THEN** the response SHALL have status 200
- **AND** each of the 5 returned suggested spans SHALL include its `source` field

#### Scenario: Promote a suggested span to confirmed

- **GIVEN** a suggested span with ID "suggest-1" for entity type "institute" at offsets 10-31
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/spans/promote/suggest-1`
- **THEN** the response SHALL have status 201
- **AND** a new confirmed span SHALL be created with the same offsets, text, and entity_type
- **AND** the suggested span SHALL be removed

#### Scenario: Promoting an LLM-sourced suggested span behaves identically to a keyword-sourced one

- **GIVEN** a suggested span with ID "suggest-2" for entity type "person_name" at offsets 0-8 with `source: "llm"`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/spans/promote/suggest-2`
- **THEN** the response SHALL have status 201
- **AND** a new confirmed span SHALL be created with the same offsets, text, and entity_type
- **AND** the suggested span SHALL be removed

### Requirement: Annotation Task Management

The system SHALL allow Tenant Admins to create annotation tasks that assign a document to a specific annotator. Each task SHALL track status through `unannotated` → `in-progress` → `completed`. A document SHALL have at most one active (non-completed) task at any time. Tasks SHALL be stored in the tenant's isolated schema. Annotation tasks SHALL only be creatable for documents whose `purpose` is `training`.

`completed` SHALL be terminal: `PATCH /api/v1/annotation-tasks/{id}` SHALL reject any transition from `completed` to `unannotated` or `in-progress` with 422 and code `INVALID_TRANSITION`. A `PATCH` requesting `{status: "completed"}` on a task already `completed` SHALL be treated as an idempotent no-op and SHALL return 200 with the task's unchanged status, so that annotators can re-submit later edits without a state error.

The `NO_SPANS` guard SHALL continue to apply on every request that sets status to `completed`, including the idempotent re-completion case.

#### Scenario: Create an annotation task

- **GIVEN** a processed document with `purpose='training'` and an active annotator user
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

#### Scenario: Re-completing a completed task is idempotent

- **GIVEN** a task with ID "task-789" in status `completed` whose document has at least one confirmed span
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "completed"}`
- **THEN** the response SHALL have status 200
- **AND** the task status SHALL remain `completed`

#### Scenario: Reopening a completed task is rejected

- **GIVEN** a task with ID "task-789" in status `completed`
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "in-progress"}`
- **THEN** the response SHALL have status 422
- **AND** the error code SHALL be `INVALID_TRANSITION`

#### Scenario: Create task for a query-purpose document is rejected

- **GIVEN** a processed document with `purpose='query'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with that document's `document_id` and a valid `annotator_user_id`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the document's purpose must be `training` to be assigned for annotation

#### Scenario: Document picker only lists training-purpose documents

- **GIVEN** a tenant with 2 processed documents with `purpose='training'` and 3 with `purpose='query'`
- **WHEN** the annotation task assignment form requests the document list
- **THEN** only the 2 `purpose='training'` documents SHALL be offered as assignable

### Requirement: Annotation Export

The system SHALL export a tenant's annotations in HuggingFace Dataset format (JSON lines). Each line SHALL contain `tokens` (list of tokenized words) and `tags` (list of BIO-encoded entity tags for each token). The export SHALL include all confirmed spans for all documents. Unannotated documents SHALL appear with all-O tags.

The system SHALL emit one record per bounded window of a document rather than one record per document. A document whose token count exceeds the window budget SHALL produce multiple records. Consecutive windows of the same document SHALL overlap, so that an entity crossing a window boundary appears complete in at least one window. A document whose token count is within the window budget SHALL produce exactly one record.

The system SHALL derive each token's character offsets from the token's actual position in the source text. Tag alignment SHALL be correct for source text containing any whitespace form, including newlines, tabs, and repeated spaces. The system SHALL NOT assume a single space character separates adjacent tokens.

The system SHALL derive BIO tags from each span's `char_start` and `char_end` values. The system SHALL NOT read the stored `bio_tags` column when producing export output.

The system SHALL emit `imported_annotations` rows unchanged, without windowing or re-tokenisation.

#### Scenario: Export annotation dataset

- **GIVEN** a tenant with 2 annotated documents and 1 unannotated document, each within the window budget
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-export?format=datasets`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL be JSON lines (one JSON object per line)
- **AND** each line SHALL contain `tokens` and `tags` arrays
- **AND** there SHALL be 3 lines

#### Scenario: A document exceeding the window budget produces multiple records

- **GIVEN** a tenant with 1 annotated document whose token count is more than twice the window budget
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-export?format=datasets`
- **THEN** the response SHALL contain more than one line for that document
- **AND** every token of the document SHALL appear in at least one line

#### Scenario: Consecutive windows overlap

- **GIVEN** a document that produces two consecutive windows
- **WHEN** the export is generated
- **THEN** the trailing tokens of the first window SHALL also appear as the leading tokens of the second window

#### Scenario: An entity crossing a window boundary is complete in at least one window

- **GIVEN** a document with a two-token entity whose first token falls at the end of one window's non-overlapping region
- **WHEN** the export is generated
- **THEN** at least one record SHALL contain both tokens of that entity
- **AND** in that record the entity SHALL be tagged `B-` followed by `I-`, not truncated to `B-` alone

#### Scenario: Tags align correctly across a newline separator

- **GIVEN** a document with text `"John Doe
works at Acme Corp"` and a confirmed span for `"Acme Corp"` of type `organization`
- **WHEN** the export is generated
- **THEN** the tokens `"Acme"` and `"Corp"` SHALL be tagged `B-organization` and `I-organization` respectively
- **AND** the tokens `"works"` and `"at"` SHALL be tagged `O`

#### Scenario: Tags align correctly across repeated spaces and tabs

- **GIVEN** a document with text `"John  Doe	works at Acme Corp"` and a confirmed span for `"Acme Corp"` of type `organization`
- **WHEN** the export is generated
- **THEN** the tokens `"Acme"` and `"Corp"` SHALL be tagged `B-organization` and `I-organization` respectively
- **AND** no other token SHALL carry an `organization` tag

#### Scenario: Export ignores a stale stored bio_tags value

- **GIVEN** a confirmed span whose stored `bio_tags` column holds a value inconsistent with its `char_start` and `char_end`
- **WHEN** the export is generated
- **THEN** the emitted tags SHALL reflect the span's `char_start` and `char_end`
- **AND** the emitted tags SHALL NOT reflect the stored `bio_tags` value

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

#### Scenario: Imported annotation rows are passed through unwindowed

- **GIVEN** a tenant with 3 rows in `imported_annotations`, one of which has more tokens than the window budget
- **WHEN** the export is generated
- **THEN** exactly 3 lines SHALL be emitted for the imported rows
- **AND** the oversized imported row SHALL be emitted with its tokens and tags unchanged

