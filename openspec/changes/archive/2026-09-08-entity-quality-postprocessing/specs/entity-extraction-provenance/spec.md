## ADDED Requirements

### Requirement: Original BERT output survives post-processing

`document_entities` SHALL retain enough information to answer, for any row, what the deterministic BERT pipeline originally produced. When post-processing changes a row's value or type, the original SHALL be preserved on that row. When post-processing changes nothing, the original SHALL NOT be duplicated.

#### Scenario: A modified value retains its original

- **GIVEN** the deterministic pipeline produced `entity_value = 'HANNAH'` with `entity_type = 'COMPANY'`
- **WHEN** post-processing changes the type to `NAME`
- **THEN** the persisted row SHALL carry `entity_type = 'NAME'`
- **AND** `source_entity_type` SHALL be `COMPANY`
- **AND** `source_entity_value` SHALL be `HANNAH`

#### Scenario: An unchanged row does not duplicate its value

- **GIVEN** post-processing returns `keep` for a candidate
- **WHEN** the row is persisted
- **THEN** `source_entity_value` and `source_entity_type` SHALL be NULL
- **AND** `postprocess_status` SHALL be `kept`

#### Scenario: A row that was never post-processed is distinguishable

- **GIVEN** a batch run executed in `bert_only` mode
- **WHEN** its entities are persisted
- **THEN** every row SHALL carry `postprocess_status = 'not_applied'`
- **AND** `source_entity_value`, `source_entity_type`, `postprocess_model`, and `postprocess_prompt_version` SHALL be NULL

### Requirement: Post-processing changes are attributable to a model and prompt version

Every row whose value or type was produced by post-processing SHALL record the post-processor model identifier, the prompt template version, and the time of processing, so a quality change can be traced to a specific model or prompt revision.

#### Scenario: Model and prompt version are recorded

- **GIVEN** post-processing modifies a row
- **WHEN** the row is persisted
- **THEN** `postprocess_model` SHALL contain the provider deployment identifier actually used
- **AND** `postprocess_prompt_version` SHALL contain the prompt template version
- **AND** `postprocess_at` SHALL contain the processing timestamp

#### Scenario: All rows changed by a given prompt version are queryable

- **GIVEN** rows produced under two different `postprocess_prompt_version` values
- **WHEN** a query filters on one version
- **THEN** only rows produced under that version SHALL be returned

### Requirement: Rows record which extraction pipeline produced them

Each `document_entities` row SHALL record an extraction schema version identifying the pipeline that produced it, so rows carrying uncalibrated confidence from the pre-change pipeline are distinguishable from rows carrying calibrated probabilities. Confidence-gated logic SHALL only act on rows marked as calibrated.

#### Scenario: Newly extracted rows are marked calibrated

- **GIVEN** an extraction run executed after this change is deployed
- **WHEN** its entities are persisted
- **THEN** each row SHALL carry the current `extraction_schema_version`

#### Scenario: Pre-existing rows are not rewritten

- **GIVEN** rows persisted before this change, holding uncalibrated confidence values
- **WHEN** the migration is applied
- **THEN** their `confidence` values SHALL NOT be modified
- **AND** their `extraction_schema_version` SHALL indicate the pre-change pipeline

#### Scenario: Confidence-gated selection ignores uncalibrated rows

- **GIVEN** a tenant holding both pre-change and post-change rows
- **WHEN** candidate selection evaluates the confidence rule
- **THEN** only rows marked with the calibrated schema version SHALL be evaluated against the confidence threshold

### Requirement: Repeated mentions collapse to one row with an occurrence count

Entities identical on `document_id`, `entity_type`, and `normalized_value` within a single document SHALL be persisted as one row carrying an occurrence count and the span of the first mention, so counting queries measure distinct facts rather than repetition.

#### Scenario: Repeated mentions produce one row

- **GIVEN** a document in which the deterministic pipeline produces `TOOL_FRAMEWORK` / `node.js` eight times
- **WHEN** the document's entities are persisted
- **THEN** exactly one row SHALL exist for that document, type, and normalized value
- **AND** `occurrence_count` SHALL be 8

#### Scenario: The first mention's span is retained

- **GIVEN** repeated mentions collapsed into one row
- **WHEN** the row is inspected
- **THEN** `page_number`, `char_start`, and `char_end` SHALL be those of the first mention in document order

#### Scenario: Distinct values are not collapsed

- **GIVEN** a document containing `COMPANY` values that canonicalize differently
- **WHEN** the entities are persisted
- **THEN** each distinct normalized value SHALL occupy its own row

#### Scenario: Collapsing does not cross documents

- **GIVEN** the same normalized value extracted from two different documents
- **WHEN** the entities are persisted
- **THEN** two rows SHALL exist, one per document
