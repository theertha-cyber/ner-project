## ADDED Requirements

### Requirement: LLM Pre-labeling Trigger

The system SHALL expose an endpoint to trigger LLM-based pre-labeling for a document, distinct from the existing keyword pre-labeling endpoint. The system SHALL only permit this trigger for a document belonging to a tenant with at least one active entity type; the request SHALL NOT require the tenant to have QA pairs configured on every entity type — types without QA pairs SHALL still be eligible for full-document extraction (see Extraction Scope), using only their `examples` and `description` as LLM context.

#### Scenario: Trigger LLM pre-labeling for a processed document

- **GIVEN** a processed document with extracted text and a tenant with at least one active entity type
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL have status 202
- **AND** the response body SHALL contain a `job_id`

#### Scenario: Trigger LLM pre-labeling for a document with no extracted text

- **GIVEN** a document with `status` other than `"processed"` or with no extracted text
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the document has no extracted text

#### Scenario: Trigger LLM pre-labeling for a tenant with no active entity types

- **GIVEN** a tenant with zero active entity types
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate no entity types are configured

### Requirement: Extraction Scope

The system SHALL instruct the LLM to extract all spans of all the tenant's active entity types present in the document text on every call, regardless of which entity types have QA pairs configured. The system SHALL NOT restrict extraction to only the entity types referenced by configured QA pairs. QA pairs, where present on an entity type, SHALL be included in the LLM prompt as few-shot context for that entity type only, and SHALL NOT be treated as questions to answer against the specific document being processed.

#### Scenario: Entity types without QA pairs are still extracted

- **GIVEN** a tenant with entity type `institute` (has QA pairs configured) and entity type `person_name` (has only `examples`, no QA pairs)
- **WHEN** LLM pre-labeling runs on a document containing both an institute name and a person name
- **THEN** the completed job's suggested spans SHALL include spans for both `institute` and `person_name`

#### Scenario: QA pairs do not limit extraction to their literal topic

- **GIVEN** a tenant with entity type `years_experience` whose only configured QA pair is "How many years of experience does X have? -> X has 10 years of experience"
- **AND** a document containing two distinct mentions of years of experience for two different people
- **WHEN** LLM pre-labeling runs on that document
- **THEN** the completed job's suggested spans SHALL include a span for each mention, not only one matching the QA pair's literal question

### Requirement: Extractive-Only Output

The system SHALL require the LLM to return each entity as a verbatim quote copied from the document text, and SHALL treat any output that is not intended as a literal substring of the document as invalid for the purposes of the Grounding and Verification requirement. The system SHALL NOT accept or store a span whose value was computed, inferred, normalized, or paraphrased rather than copied from the text.

#### Scenario: LLM output that is not a literal substring is not stored as a span

- **GIVEN** a document whose only experience-related text is "2019-2024" and no literal occurrence of "5 years" anywhere in the text
- **AND** a QA pair on entity type `years_experience` implying an answer of "5 years"
- **WHEN** LLM pre-labeling runs on that document
- **THEN** the completed job's suggested spans SHALL NOT contain a span with text "5 years" for entity type `years_experience`, because that string does not exist in the document and therefore fails grounding

### Requirement: Grounding and Verification

The system SHALL, for each entity the LLM returns, locate the character offsets of that entity's quoted text within the document text using an exact, case-insensitive match, before storing it as a suggested span. The system SHALL discard any returned entity whose quote cannot be located via exact match — it SHALL NOT store an approximate, nearest-match, or best-effort offset. When a quote matches more than one location in the document text, the system SHALL select the first (lowest character offset) occurrence that does not overlap a location already claimed by another grounded suggestion for that document.

#### Scenario: Quote grounds to exactly one location

- **GIVEN** a document with text "John Doe joined as Senior Engineer" and an LLM-returned entity `{"entity_type": "person_name", "quote": "John Doe"}`
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

### Requirement: Entity Type Constraint

The system SHALL discard any LLM-returned entity whose `entity_type` does not match an active entity type already configured for the tenant. The system SHALL NOT create a new entity type as a side effect of LLM pre-labeling.

#### Scenario: LLM returns an entity type not configured for the tenant

- **GIVEN** a tenant with active entity types `institute` and `person_name` only
- **AND** the LLM returns an entity with `entity_type: "job_title"`
- **WHEN** the grounding step runs
- **THEN** no suggested span SHALL be stored for that entity
- **AND** no new entity type named `job_title` SHALL be created

### Requirement: Suggested Span Storage and Source Tracking

The system SHALL write every grounded, entity-type-valid suggestion to `{tenant_schema}.suggested_spans` with `source: "llm"`, replacing all existing suggested spans for that document (matching the replace-not-merge behavior of keyword pre-labeling). Each stored span SHALL include `id`, `document_id`, `entity_type`, `char_start`, `char_end`, `text`, `confidence`, and `source`.

#### Scenario: LLM pre-labeling replaces existing suggestions for the document

- **GIVEN** a document with 2 existing suggested spans with `source: "keyword"`
- **WHEN** LLM pre-labeling completes successfully for that document
- **THEN** the prior 2 suggested spans SHALL be removed
- **AND** the newly stored suggested spans SHALL have `source: "llm"`

### Requirement: Asynchronous Execution

The system SHALL execute LLM pre-labeling as a background job and SHALL NOT block the triggering HTTP request on the LLM call. The system SHALL expose a way to check job status and, upon completion, retrieve the resulting suggested spans via the existing suggested-spans listing endpoint.

#### Scenario: Trigger request returns before the LLM call completes

- **GIVEN** a processed document eligible for LLM pre-labeling
- **WHEN** an annotator POSTs to `/api/v1/documents/{doc_id}/prelabel/llm`
- **THEN** the response SHALL be returned in under 1 second
- **AND** the LLM call and grounding SHALL continue running after the response is returned

#### Scenario: Job status reflects completion

- **GIVEN** a triggered LLM pre-labeling job that has finished processing
- **WHEN** an annotator GETs the job's status
- **THEN** the response SHALL indicate `status: "completed"`
- **AND** the resulting suggested spans SHALL be retrievable via `/api/v1/documents/{doc_id}/spans?type=suggested`

### Requirement: Result Caching

The system SHALL cache LLM pre-labeling results keyed on the document's content hash and the tenant's current entity-type configuration version (entity types, their `examples`, and their QA pairs, taken together). The system SHALL serve a cached result without invoking the LLM when a valid cache entry exists for the current key. The system SHALL treat any change to the tenant's entity-type configuration as invalidating previously cached results for that tenant.

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

### Requirement: Tenant Isolation

The system SHALL resolve the document, its text, the tenant's entity-type configuration, and the suggested-spans write target entirely within the requesting tenant's schema, using the same tenant-resolution mechanism as every other `annotation_service` endpoint. The system SHALL NOT include any other tenant's documents or entity-type configuration in a single LLM call.

#### Scenario: LLM pre-labeling is scoped to a single tenant

- **GIVEN** two tenants, "acme-corp" and "globex", each with a document containing entities
- **WHEN** LLM pre-labeling is triggered for the "acme-corp" document
- **THEN** the LLM call SHALL include only "acme-corp"'s document text and entity-type configuration
- **AND** the resulting suggested spans SHALL be written only to the "acme-corp" tenant schema
