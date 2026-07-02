## MODIFIED Requirements

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
