# BIO Tag Storage

## Purpose

TBD — persist computed BIO tag sequences on the `spans` table at write time to avoid runtime recomputation during export.

---

## Requirements

### Requirement: BIO Tag Persistence on Spans

The annotation service SHALL compute and store BIO tag sequences on the `spans` table at write time. The `spans` table SHALL include a `bio_tags TEXT[]` column (nullable). When a span is created via `POST /documents/{id}/spans`, the service SHALL compute the BIO tag array for the span's tokens using the document's stored text and persist it alongside the span. When a span's entity type is changed via `PATCH /documents/{id}/spans/{span_id}`, the `bio_tags` column SHALL be recomputed with the new entity type. The BIO computation SHALL use whitespace-split tokenization consistent with the existing export tokenizer: the first token in the span range receives a `B-{entity_type}` tag and subsequent tokens receive `I-{entity_type}` tags.

#### Scenario: BIO tags are stored when a span is created

- **GIVEN** a document with text "John Smith works here" and entity type "PER"
- **WHEN** `POST /documents/{id}/spans` is called with `{entity_type: "PER", char_start: 0, char_end: 10}`
- **THEN** the new span row SHALL have `bio_tags = ["B-PER", "I-PER"]`
- **AND** the `bio_tags` value SHALL be returned in the POST response

#### Scenario: Single-token span gets a B-tag only

- **GIVEN** a document with text "Acme Corp" and entity type "ORG"
- **WHEN** `POST /documents/{id}/spans` is called with `{entity_type: "ORG", char_start: 0, char_end: 4}` (token "Acme" only)
- **THEN** the span row SHALL have `bio_tags = ["B-ORG"]`

#### Scenario: BIO tags are recomputed on entity type retype

- **GIVEN** a span with `bio_tags = ["B-PER", "I-PER"]` (entity_type "PER")
- **WHEN** `PATCH /documents/{id}/spans/{span_id}` is called with `{entity_type: "ORG"}`
- **THEN** the span row SHALL be updated to `bio_tags = ["B-ORG", "I-ORG"]`
- **AND** the PATCH response SHALL include the updated `bio_tags`

#### Scenario: Export reads stored bio_tags from spans

- **GIVEN** a document with two spans, both having non-NULL `bio_tags` columns
- **WHEN** `GET /api/v1/annotation-export` is called for that document
- **THEN** the JSONL output SHALL use the stored `bio_tags` values for tagged tokens
- **AND** no runtime BIO computation SHALL be performed for spans with stored tags

#### Scenario: Export falls back to computed BIO for legacy spans with NULL bio_tags

- **GIVEN** a document with a span that has `bio_tags = NULL` (created before this migration)
- **WHEN** `GET /api/v1/annotation-export` is called for that document
- **THEN** the export SHALL compute BIO tags for that span using the existing `_bio_tags()` logic
- **AND** the output SHALL be correct (no data loss for legacy rows)

### Requirement: BIO Tag Schema Migration

The `tenant_template.spans` table SHALL be extended with a `bio_tags TEXT[]` column via a non-breaking Alembic migration. The column SHALL be nullable to preserve backward compatibility with existing span rows. No existing rows SHALL be modified by the migration itself.

#### Scenario: Migration adds nullable column without data loss

- **GIVEN** an existing `spans` table with rows that have no `bio_tags` column
- **WHEN** migration `009_add_bio_tags_to_spans` is applied
- **THEN** all existing span rows SHALL retain their data unchanged
- **AND** the new `bio_tags` column SHALL be NULL for all pre-migration rows
- **AND** the migration SHALL be reversible (downgrade removes the column without error)
