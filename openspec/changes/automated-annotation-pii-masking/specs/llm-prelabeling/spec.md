## MODIFIED Requirements

### Requirement: Extraction Scope

The system SHALL instruct the LLM to extract all spans of all the tenant's active `open`-sensitivity entity types present in the document text on every call, regardless of which entity types have QA pairs configured. The system SHALL NOT restrict extraction to only the entity types referenced by configured QA pairs. QA pairs, where present on an entity type, SHALL be included in the LLM prompt as few-shot context for that entity type only, and SHALL NOT be treated as questions to answer against the specific document being processed. `pattern`- and `local_only`-sensitivity entity types SHALL NOT be named in the entity-type list sent to the external LLM provider and SHALL NOT be extracted by it under any circumstance; those types are extracted exclusively through local detection (see Safe-Copy Generation).

#### Scenario: Entity types without QA pairs are still extracted

- **GIVEN** a tenant with entity type `institute` (has QA pairs configured) and entity type `person_name` (has only `examples`, no QA pairs), both `open`-sensitivity
- **WHEN** LLM pre-labeling runs on a document containing both an institute name and a person name
- **THEN** the completed job's suggested spans SHALL include spans for both `institute` and `person_name`

#### Scenario: QA pairs do not limit extraction to their literal topic

- **GIVEN** a tenant with entity type `years_experience` whose only configured QA pair is "How many years of experience does X have? -> X has 10 years of experience"
- **AND** a document containing two distinct mentions of years of experience for two different people
- **WHEN** LLM pre-labeling runs on that document
- **THEN** the completed job's suggested spans SHALL include a span for each mention, not only one matching the QA pair's literal question

#### Scenario: A local_only entity type is never named in the external prompt

- **GIVEN** a tenant with `open`-sensitivity entity type `organization` and `local_only`-sensitivity entity type `child_name`, both active
- **WHEN** LLM pre-labeling runs on a document containing both an organization and a child's name
- **THEN** the payload sent to the external LLM provider SHALL name only `organization` in its entity-type list
- **AND** the completed job's suggested spans SHALL still include a `child_name` span, sourced locally

#### Scenario: A pattern entity type is never named in the external prompt

- **GIVEN** a tenant with `pattern`-sensitivity entity type `ssn` (`validation_rule: "^\\d{3}-\\d{2}-\\d{4}$"`) and `open`-sensitivity entity type `document_date`
- **WHEN** LLM pre-labeling runs on a document containing an SSN and a date
- **THEN** the payload sent to the external LLM provider SHALL name only `document_date` in its entity-type list
- **AND** the completed job's suggested spans SHALL still include an `ssn` span, sourced locally

### Requirement: Grounding and Verification

The system SHALL, for each entity the LLM returns, locate the character offsets of that entity's quoted text within the masked copy of the document text (see Safe-Copy Generation) using an exact, case-insensitive match, before storing it as a suggested span. The system SHALL discard any returned entity whose quote cannot be located via exact match in the masked copy — it SHALL NOT store an approximate, nearest-match, or best-effort offset. When a quote matches more than one location in the masked copy, the system SHALL select the first (lowest character offset) occurrence that does not overlap a location already claimed by another grounded suggestion for that document. A location grounded in the masked copy SHALL be translated to the corresponding offset in the original document text before storage; if no such correspondence exists (the location falls within a masked/placeholder region), the system SHALL discard the suggestion exactly as if it had failed to ground.

#### Scenario: Quote grounds to exactly one location

- **GIVEN** a document with text "John Doe joined as Senior Engineer" (no `pattern`/`local_only` entity types active, so the masked copy is identical to the original) and an LLM-returned entity `{"entity_type": "person_name", "quote": "John Doe"}`
- **WHEN** the grounding step runs
- **THEN** a suggested span SHALL be stored with `entity_type: "person_name"`, `char_start: 0`, `char_end: 8`, `text: "John Doe"`

#### Scenario: Quote cannot be found in the document text

- **GIVEN** a document with text "John Doe joined as Senior Engineer" and an LLM-returned entity `{"entity_type": "person_name", "quote": "Jane Smith"}`
- **WHEN** the grounding step runs
- **THEN** no suggested span SHALL be stored for that entity
- **AND** the discarded entity SHALL be counted in the job's ungrounded-suggestion count

#### Scenario: Quote matches multiple locations in the document

- **GIVEN** a document with text "Acme Corp hired John. Acme Corp also promoted John." and an LLM-returned entity `{"entity_type": "organization", "quote": "Acme Corp"}`
- **WHEN** the grounding step runs
- **THEN** a suggested span SHALL be stored for the first occurrence of "Acme Corp" (`char_start: 0`)
- **AND** no suggested span SHALL be stored for the second occurrence unless it is also independently returned by the LLM and grounds to a location not already claimed

#### Scenario: A grounded offset in the masked copy translates to the real document's offset

- **GIVEN** a document whose text at original offset 40 reads "Jimmy Smith" (a `local_only` `child_name` masked to `⟦PERSON_1⟧` at offset 40 in the masked copy) followed by "is a resident of Example House"
- **AND** the LLM returns `{"entity_type": "residence_type", "quote": "Example House"}` for an `open`-sensitivity type
- **WHEN** the grounding step runs
- **THEN** the stored suggested span's `char_start`/`char_end` SHALL point at "Example House" within the *original* document text, not the masked copy
- **AND** the stored span's `text` SHALL be the real substring "Example House"

### Requirement: Suggested Span Storage and Source Tracking

The system SHALL write every grounded, entity-type-valid suggestion to `{tenant_schema}.suggested_spans`, replacing all existing suggested spans for that document (matching the replace-not-merge behavior of keyword pre-labeling). Each stored span SHALL include `id`, `document_id`, `entity_type`, `char_start`, `char_end`, `text`, `confidence`, and `source`. `source` SHALL be `"llm"` for a span produced by the external LLM provider and translated back to original-document offsets, `"pattern"` for a span found by local regex detection against a `validation_rule`, or `"local_model"` for a span found by the tenant's locally-hosted extraction model. All three sources SHALL be merged into one suggestion set per document using the same overlap rule Grounding and Verification already applies (first-claimed, lowest-offset span wins; a later-claimed overlapping span from any source is dropped).

#### Scenario: LLM pre-labeling replaces existing suggestions for the document

- **GIVEN** a document with 2 existing suggested spans with `source: "keyword"`
- **WHEN** LLM pre-labeling completes successfully for that document
- **THEN** the prior 2 suggested spans SHALL be removed
- **AND** the newly stored suggested spans SHALL have `source` of `"llm"`, `"pattern"`, or `"local_model"` as appropriate

#### Scenario: Locally and externally sourced spans coexist for one document

- **GIVEN** a tenant with `open`-sensitivity `organization`, `pattern`-sensitivity `ssn`, and `local_only`-sensitivity `child_name`, all present in one document
- **WHEN** LLM pre-labeling completes for that document
- **THEN** the suggested spans SHALL include at least one span with `source: "llm"` (the organization), one with `source: "pattern"` (the SSN), and one with `source: "local_model"` (the child's name)

#### Scenario: An overlapping locally-detected span wins over a later-claimed external one

- **GIVEN** a `pattern`-sensitivity span already claims characters 10-20 of a document
- **AND** the external LLM independently returns a quote for an `open`-sensitivity type that grounds, after translation, to a location overlapping characters 10-20
- **WHEN** spans are merged
- **THEN** the `pattern`-sourced span SHALL be stored
- **AND** the overlapping `llm`-sourced span SHALL be dropped, the same way two overlapping LLM-only suggestions are resolved today

### Requirement: Result Caching

The system SHALL cache LLM pre-labeling results keyed on the document's content hash and the tenant's current entity-type configuration version (entity types, their `examples`, their QA pairs, their `sensitivity`, their `validation_rule`, and their `base_label_mapping`, taken together). The system SHALL serve a cached result without invoking the LLM when a valid cache entry exists for the current key. The system SHALL treat any change to the tenant's entity-type configuration — including a change to any entity type's `sensitivity`, `validation_rule`, or `base_label_mapping` — as invalidating previously cached results for that tenant, since each of those fields governs what local detection finds and therefore what the final merged result is, even when it changes nothing about the external prompt itself.

#### Scenario: Re-triggering on an unchanged document and configuration uses the cache

- **GIVEN** a document that was successfully LLM pre-labeled, with no changes to the document content or the tenant's entity-type configuration since
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm` again
- **THEN** the response SHALL indicate the result was served from cache
- **AND** no new LLM call SHALL be made

#### Scenario: Configuration change invalidates the cache

- **GIVEN** a document that was successfully LLM pre-labeled
- **AND** the tenant subsequently adds a QA pair to one of their entity types
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm` again
- **THEN** the system SHALL invoke the LLM again rather than serving the prior cached result

#### Scenario: Reclassifying an entity type's sensitivity invalidates the cache

- **GIVEN** a document that was successfully LLM pre-labeled while entity type `child_name` was `open`
- **AND** the Tenant Admin subsequently reclassifies `child_name` to `local_only`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm` again
- **THEN** the system SHALL invoke the pipeline again rather than serving the prior cached result
- **AND** the new external LLM payload SHALL NOT name `child_name` in its entity-type list

#### Scenario: Changing a pattern type's validation_rule invalidates the cache

- **GIVEN** a document that was successfully LLM pre-labeled while `pattern`-sensitivity entity type `ssn` had `validation_rule: "\\d{3}-\\d{2}-\\d{4}"`
- **AND** the Tenant Admin subsequently tightens `ssn`'s `validation_rule`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm` again
- **THEN** the system SHALL invoke the pipeline again rather than serving the prior cached result

#### Scenario: Changing a local_only type's base_label_mapping invalidates the cache

- **GIVEN** a document that was successfully LLM pre-labeled while `local_only`-sensitivity entity type `child_name` had `base_label_mapping: {"PER": ["child_name"]}`
- **AND** the Tenant Admin subsequently changes that mapping
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm` again
- **THEN** the system SHALL invoke the pipeline again rather than serving the prior cached result

## ADDED Requirements

### Requirement: Safe-Copy Generation

Before any call to the external LLM provider, the system SHALL detect every span of every active `pattern`- and `local_only`-sensitivity entity type directly against the real document text: `pattern` types via their `validation_rule` regex, and `local_only` types via the tenant's locally-hosted extraction model, with its returned base-model-class predictions mapped to entity types through each type's `base_label_mapping`. The system SHALL then construct a masked copy of the document text in which every detected span is replaced with a placeholder token identifying its entity type. The system SHALL retain a mapping from each unmasked region's offsets in the masked copy to its offsets in the original document text. The system SHALL send only the masked copy — never the original document text — to the external LLM provider.

#### Scenario: A tenant with no pattern or local_only types sends the original text unchanged

- **GIVEN** a tenant whose active entity types are all `open`-sensitivity
- **WHEN** LLM pre-labeling runs on a document
- **THEN** the masked copy SHALL be identical to the original document text
- **AND** the payload sent to the external LLM provider SHALL contain the full original text

#### Scenario: Detected spans are replaced with placeholders before the external call

- **GIVEN** a document containing the text "Jimmy Smith was placed with the Doe family", where `child_name` (`local_only`) matches "Jimmy Smith"
- **WHEN** LLM pre-labeling runs
- **THEN** the payload sent to the external LLM provider SHALL contain a placeholder in place of "Jimmy Smith"
- **AND** the payload sent to the external LLM provider SHALL NOT contain the substring "Jimmy Smith"

#### Scenario: A pattern match is replaced with a placeholder before the external call

- **GIVEN** a document containing the text "SSN: 123-45-6789 on file" and entity type `ssn` (`pattern`, `validation_rule: "\\d{3}-\\d{2}-\\d{4}"`)
- **WHEN** LLM pre-labeling runs
- **THEN** the payload sent to the external LLM provider SHALL NOT contain the substring "123-45-6789"

### Requirement: Local-Only Type Coverage Requirement

The system SHALL refuse to trigger LLM pre-labeling for a tenant that has an active `local_only`-sensitivity entity type with no `base_label_mapping` configured, since no local detection mechanism exists to extract it without sending its real values externally. This check SHALL run at both the single-document trigger endpoint and the batch trigger endpoint, before any job is enqueued.

#### Scenario: Trigger is refused when a local_only type has no base_label_mapping

- **GIVEN** a tenant with an active `local_only`-sensitivity entity type `case_notes` and no `base_label_mapping` set on it
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL name `case_notes` and state that it has no local detection mechanism configured
- **AND** no pre-labeling job SHALL be enqueued

#### Scenario: Batch trigger is refused for the same reason

- **GIVEN** a tenant with an active `local_only`-sensitivity entity type with no `base_label_mapping`
- **WHEN** a Tenant Admin submits documents for a batch pre-labeling job
- **THEN** the response SHALL have status 422 and no batch SHALL be created

#### Scenario: A local_only type with a base_label_mapping does not block the trigger

- **GIVEN** a tenant with `local_only`-sensitivity entity type `child_name` mapped via `base_label_mapping: {"PER": ["child_name"]}`
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL have status 202

### Requirement: Fail-Closed on Local Detection Failure

If local detection cannot complete for a document — the local model service is unreachable, returns an error, or times out; or a configured `validation_rule` fails to compile — the system SHALL NOT proceed to call the external LLM provider for that document. The job or per-document batch outcome SHALL be marked failed with a reason that distinguishes local-detection failure from an external-provider failure.

#### Scenario: Local model unavailability blocks the external call entirely

- **GIVEN** a tenant with an active `local_only`-sensitivity entity type, and the local extraction model service is unreachable
- **WHEN** LLM pre-labeling is triggered for a document
- **THEN** the job SHALL be marked failed
- **AND** no request SHALL have been made to the external LLM provider
- **AND** the failure reason SHALL indicate local detection failed, distinguishable from an `LLMUnavailable` (external provider) failure

#### Scenario: A batch document's local-detection failure does not abort the batch

- **GIVEN** a batch of 10 documents where the local model service fails intermittently, causing local detection to fail for exactly one document
- **WHEN** the batch completes
- **THEN** that one document SHALL be recorded as failed with a local-detection failure reason
- **AND** the other 9 documents SHALL succeed normally
- **AND** no request for the failed document SHALL have reached the external LLM provider

### Requirement: Placeholder Stability Within a Document

Within a single document, every occurrence of the same exact detected text SHALL be replaced with the same placeholder token. Distinct detected values of the same entity type within one document SHALL receive distinguishable placeholder tokens. Placeholder identity SHALL NOT be persisted or reused across documents.

#### Scenario: Repeated mentions of the same value share one placeholder

- **GIVEN** a document mentioning "Jimmy Smith" three times, `child_name` classified `local_only`
- **WHEN** the masked copy is built
- **THEN** all three occurrences SHALL be replaced with the identical placeholder token

#### Scenario: Distinct values of the same type get distinguishable placeholders

- **GIVEN** a document mentioning both "Jimmy Smith" and "Maria Lopez", both matching `child_name` (`local_only`)
- **WHEN** the masked copy is built
- **THEN** "Jimmy Smith" and "Maria Lopez" SHALL be replaced with two different placeholder tokens
