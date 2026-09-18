## MODIFIED Requirements

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
