## MODIFIED Requirements

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

- **GIVEN** a document with text `"John Doe\nworks at Acme Corp"` and a confirmed span for `"Acme Corp"` of type `organization`
- **WHEN** the export is generated
- **THEN** the tokens `"Acme"` and `"Corp"` SHALL be tagged `B-organization` and `I-organization` respectively
- **AND** the tokens `"works"` and `"at"` SHALL be tagged `O`

#### Scenario: Tags align correctly across repeated spaces and tabs

- **GIVEN** a document with text `"John  Doe\tworks at Acme Corp"` and a confirmed span for `"Acme Corp"` of type `organization`
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
