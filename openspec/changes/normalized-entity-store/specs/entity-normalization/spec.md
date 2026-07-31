## ADDED Requirements

### Requirement: BIO sequence reconstruction

The system SHALL reconstruct complete logical entities from an ordered sequence of token predictions. A `B-<TYPE>` prediction SHALL open a new entity; each immediately following `I-<TYPE>` prediction of the same type SHALL extend that entity; any other prediction SHALL close it. The reconstructed entity's `entity_type` SHALL be the label with its `B-`/`I-` prefix stripped. Reconstruction SHALL operate on the ordered prediction sequence, never on a set or map keyed by token text.

#### Scenario: Consecutive B-I tokens merge into one entity

- **GIVEN** the ordered predictions `[(B-ORG, "Computer"), (I-ORG, "Science"), (I-ORG, "Engineering")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** exactly one entity SHALL be produced
- **AND** its `entity_type` SHALL be `ORG`
- **AND** its `entity_value` SHALL be `Computer Science Engineering`

#### Scenario: Consecutive B tags of the same type start separate entities

- **GIVEN** the ordered predictions `[(B-PER, "Alice"), (B-PER, "Bob")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** two entities SHALL be produced with values `Alice` and `Bob`

#### Scenario: An I tag of a different type closes the open entity

- **GIVEN** the ordered predictions `[(B-PER, "Arjun"), (I-ORG, "InApp")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** two entities SHALL be produced
- **AND** the first SHALL be `PER` with value `Arjun`
- **AND** the second SHALL be `ORG` with value `InApp`

#### Scenario: A dangling I tag with no preceding B tag opens an entity

- **GIVEN** the ordered predictions `[(I-LOC, "Kerala")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** one `LOC` entity with value `Kerala` SHALL be produced
- **AND** the normalizer SHALL NOT raise

#### Scenario: The same entity text occurring twice produces two entities

- **GIVEN** the ordered predictions `[(B-ORG, "InApp"), (B-LOC, "Kochi"), (B-ORG, "InApp")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** two separate `ORG` entities SHALL be produced, one per occurrence

### Requirement: WordPiece continuation merging

The system SHALL merge WordPiece continuation tokens into their preceding token before or during entity reconstruction. A token whose text begins with `##` SHALL be appended to the previous token without an intervening space, and its `##` prefix SHALL be removed. Merging SHALL apply within an entity regardless of whether the continuation token carries a `B-` or `I-` label.

#### Scenario: Subword tokens merge into a single word

- **GIVEN** the ordered predictions `[(B-PER, "A"), (B-PER, "##r"), (B-PER, "##jun"), (I-PER, "Jaya"), (I-PER, "##kumar")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** exactly one `PER` entity SHALL be produced
- **AND** its `entity_value` SHALL be `Arjun Jayakumar`

#### Scenario: Whole-word predictions are unaffected

- **GIVEN** the ordered predictions `[(B-LOC, "New"), (I-LOC, "York")]`
- **WHEN** the normalizer reconstructs entities
- **THEN** one `LOC` entity with value `New York` SHALL be produced

### Requirement: Entity-level confidence aggregation

The system SHALL compute one confidence score per reconstructed entity from the confidences of its constituent token predictions, using the **minimum** of those confidences. The aggregation strategy SHALL be implemented in a single documented function so it can be changed in one place.

#### Scenario: Entity confidence is the minimum of its tokens

- **GIVEN** an entity reconstructed from tokens with confidences `[0.99, 0.71, 0.88]`
- **WHEN** the normalizer aggregates confidence
- **THEN** the entity's `confidence` SHALL be `0.71`

#### Scenario: Single-token entity keeps its own confidence

- **GIVEN** an entity reconstructed from a single token with confidence `0.93`
- **WHEN** the normalizer aggregates confidence
- **THEN** the entity's `confidence` SHALL be `0.93`

### Requirement: Canonical value normalization

The system SHALL compute a `normalized_value` for every reconstructed entity while preserving the originally extracted text in `entity_value`. Normalization SHALL apply a deterministic fallback — Unicode casefold, collapse internal whitespace, strip surrounding punctuation — and SHALL additionally apply a static alias map that collapses known surface variants onto one canonical form. Normalization SHALL NOT call an LLM or any network service.

#### Scenario: Deterministic fallback normalization

- **GIVEN** an entity with `entity_value` `"Arjun  Jayakumar."`
- **WHEN** the normalizer computes the canonical value
- **THEN** `normalized_value` SHALL be `arjun jayakumar`
- **AND** `entity_value` SHALL remain `"Arjun  Jayakumar."`

#### Scenario: Alias map collapses surface variants

- **GIVEN** entities with values `ReactJS`, `React.js`, and `React JS`
- **WHEN** the normalizer computes canonical values
- **THEN** all three SHALL have `normalized_value` equal to `react`

#### Scenario: Acronym alias maps to the same canonical value as its expansion

- **GIVEN** entities with values `Amazon Web Services` and `AWS`
- **WHEN** the normalizer computes canonical values
- **THEN** both SHALL have `normalized_value` equal to `aws`

#### Scenario: Unknown value falls back to deterministic normalization

- **GIVEN** an entity with value `InApp` that has no alias-map entry
- **WHEN** the normalizer computes the canonical value
- **THEN** `normalized_value` SHALL be `inapp`

### Requirement: Location metadata on normalized entities

The system SHALL attach `page_number`, `char_start`, and `char_end` to each reconstructed entity by aligning the token stream back to the source document text spans. `char_start` SHALL be the start offset of the entity's first token and `char_end` the end offset of its last token. When a token cannot be aligned to a source span, the affected fields SHALL be stored as NULL and the document SHALL still be persisted.

#### Scenario: Entity carries offsets spanning its first and last token

- **GIVEN** a document whose text span on page 2 contains `Computer Science Engineering` starting at character offset 100
- **WHEN** the normalizer reconstructs that `ORG` entity
- **THEN** the entity SHALL have `page_number = 2`, `char_start = 100`, and `char_end = 128`

#### Scenario: Unalignable token yields NULL offsets rather than failure

- **GIVEN** a token stream that cannot be aligned to any source span
- **WHEN** the normalizer reconstructs entities
- **THEN** the affected entities SHALL have NULL `page_number`, `char_start`, and `char_end`
- **AND** the entities SHALL still be produced with their type, value, normalized value, and confidence

### Requirement: Normalized entity persistence

The system SHALL persist reconstructed entities into a per-tenant `document_entities` table with columns `id` (UUID primary key), `document_id`, `entity_type`, `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, `char_end`, and `created_at`. Each row SHALL represent one complete logical entity, never a single token prediction. The table SHALL carry indexes supporting lookup by `document_id`, by `entity_type`, and by `normalized_value`.

#### Scenario: One row per logical entity

- **GIVEN** a document whose predictions reconstruct to the entities `PER "Arjun Jayakumar"`, `ORG "InApp"`, and `SKILL "Kubernetes"`
- **WHEN** the entities are persisted
- **THEN** `document_entities` SHALL contain exactly three rows for that `document_id`
- **AND** no row SHALL contain a `B-`/`I-` prefixed `entity_type`
- **AND** no row SHALL contain a `##`-prefixed `entity_value`

#### Scenario: Normalized store is queryable by canonical value

- **GIVEN** `document_entities` rows exist for two documents mentioning `AWS` and `Amazon Web Services`
- **WHEN** a query filters on `normalized_value = 'aws'`
- **THEN** rows from both documents SHALL be returned

### Requirement: Raw BIO storage is preserved

The system SHALL leave the raw per-token `extracted_entities` table unchanged in schema and in write behaviour. Normalization SHALL be additive: raw token rows and normalized entity rows for a document SHALL be written in the same database transaction, so a document never has normalized entities without its raw predictions.

#### Scenario: Raw token rows still written

- **GIVEN** batch extraction runs for a document
- **WHEN** extraction completes
- **THEN** `extracted_entities` SHALL contain the same per-token rows it contained before this change, with BIO-prefixed `entity_id` values
- **AND** `document_entities` SHALL additionally contain the reconstructed entities

#### Scenario: Normalization failure does not leave a half-written document

- **GIVEN** persistence of normalized entities fails for a document
- **WHEN** the transaction is rolled back
- **THEN** neither the raw token rows nor the normalized rows for that document SHALL be committed
- **AND** the document SHALL be counted as failed in the run report

### Requirement: Backfill of previously extracted documents

The system SHALL provide a backfill utility that populates `document_entities` for documents extracted before this change. Because existing `extracted_entities` rows carry no ordering column and no offsets, the utility SHALL re-run inference for the document rather than reconstructing from stored rows. The utility SHALL be idempotent per document and SHALL NOT modify `extracted_entities`. Documents that have not been backfilled SHALL remain retrievable through every unchanged path.

#### Scenario: Backfill populates the normalized store

- **GIVEN** a document with existing `extracted_entities` rows and no `document_entities` rows
- **WHEN** the backfill utility runs for that document
- **THEN** `document_entities` SHALL contain its reconstructed entities
- **AND** its `extracted_entities` rows SHALL be unchanged

#### Scenario: Re-running backfill does not duplicate rows

- **GIVEN** a document already backfilled into `document_entities`
- **WHEN** the backfill utility runs again for that document
- **THEN** the document's `document_entities` row count SHALL be unchanged

#### Scenario: Un-backfilled documents still function

- **GIVEN** a document with no `document_entities` rows
- **WHEN** a user asks a semantic question answered from that document's chunks
- **THEN** the answer SHALL still cite that document
