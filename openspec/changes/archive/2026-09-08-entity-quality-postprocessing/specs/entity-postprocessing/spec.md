## ADDED Requirements

### Requirement: Post-processing runs only on selected candidate entities

The system SHALL NOT submit every reconstructed entity to the LLM post-processor. An entity SHALL be selected as a candidate only when it satisfies at least one selection rule: its calibrated confidence is below `postprocess_confidence_threshold`; its configured `value_kind` is non-`text` and semantic normalization produced no typed value; it is a single-token entity of a type configured as typically multi-token; or it lies within `max_entity_word_gap` of a same-type, same-page neighbour. Entities satisfying no rule SHALL be persisted directly from the deterministic pipeline without any LLM call.

#### Scenario: High-confidence, well-formed entity is never sent to the LLM

- **GIVEN** a reconstructed entity with calibrated confidence above `postprocess_confidence_threshold`, a successfully typed value, and no same-type neighbour within the gap bound
- **WHEN** a batch run executes in `bert_llm_postprocess` mode
- **THEN** that entity SHALL NOT appear in any post-processor request
- **AND** it SHALL be persisted with `postprocess_status = 'not_applied'`

#### Scenario: Low-confidence entity is selected as a candidate

- **GIVEN** a reconstructed entity whose calibrated confidence is below `postprocess_confidence_threshold`
- **WHEN** a batch run executes in `bert_llm_postprocess` mode
- **THEN** that entity SHALL be included in the post-processor request for its document

#### Scenario: Unparseable typed value selects an entity

- **GIVEN** an entity of a type configured with `value_kind = 'duration'` whose value produced no `value_number` during semantic normalization
- **WHEN** a batch run executes in `bert_llm_postprocess` mode
- **THEN** that entity SHALL be included in the post-processor request

#### Scenario: Adjacent same-type entities are selected as merge candidates

- **GIVEN** two entities of the same `entity_type` on the same `page_number` whose word indices differ by no more than `max_entity_word_gap`
- **WHEN** a batch run executes in `bert_llm_postprocess` mode
- **THEN** both SHALL be included in the same post-processor request as merge candidates

#### Scenario: Candidates are batched per document, not per entity

- **GIVEN** a document producing five candidate entities
- **WHEN** post-processing runs for that document
- **THEN** exactly one post-processor request SHALL be issued for that document
- **AND** the request SHALL contain all five candidates

### Requirement: The post-processor returns a strictly validated structured decision

The post-processor SHALL return one decision object per submitted candidate, each carrying a server-assigned `candidate_id`, a `decision` of exactly `keep`, `modify`, `merge`, or `reject`, and the fields required by that decision. The system SHALL validate every returned object before any database write. `candidate_id` SHALL be assigned by the server per request and SHALL NOT be any database identifier. The post-processor SHALL NOT write to `document_entities` directly; accepted values SHALL flow through the existing deterministic canonicalization and semantic normalization before insertion.

#### Scenario: Well-formed decision is applied

- **GIVEN** a candidate submitted with `candidate_id = 3`
- **WHEN** the post-processor returns `{"candidate_id": 3, "decision": "modify", "value": "<a substring of the supplied window>"}`
- **AND** every validation check passes
- **THEN** the modified value SHALL be canonicalized and semantically normalized by the existing deterministic code
- **AND** the resulting row SHALL be persisted with `postprocess_status = 'modified'`

#### Scenario: Malformed response discards the whole batch without losing extraction

- **GIVEN** a document with candidates submitted for post-processing
- **WHEN** the post-processor returns output that does not parse as JSON matching the declared schema
- **THEN** no post-processed value SHALL be persisted for that document
- **AND** every entity for that document SHALL be persisted exactly as the deterministic pipeline produced it
- **AND** each such row SHALL record `postprocess_status = 'failed'`

#### Scenario: Unknown candidate_id is discarded

- **GIVEN** a request submitting candidates with ids 1 through 4
- **WHEN** the response contains an object with `candidate_id = 99`
- **THEN** that object SHALL be discarded
- **AND** the remaining valid objects SHALL still be applied

#### Scenario: Invalid item does not invalidate its siblings

- **GIVEN** a response containing four decision objects, one of which fails validation
- **WHEN** validation runs
- **THEN** the three valid decisions SHALL be applied
- **AND** the candidate corresponding to the invalid decision SHALL be persisted exactly as the deterministic pipeline produced it

#### Scenario: Post-processed value is normalized by the existing deterministic code

- **GIVEN** the post-processor returns a corrected value containing mixed casing and a trailing comma
- **WHEN** the decision is applied
- **THEN** the persisted `normalized_value` SHALL be the result of applying the same `canonicalize` used for non-post-processed rows
- **AND** any typed value fields SHALL be derived by the same semantic normalizer used for non-post-processed rows

### Requirement: The post-processor SHALL NOT invent entities

Every value emitted by a `modify` or `merge` decision SHALL be verifiable as a substring of the document text window supplied with the request, compared after the same canonical folding applied to stored values. A decision whose value fails this check SHALL be discarded and its candidate persisted unchanged. The post-processor SHALL NOT emit an entity that does not correspond to a submitted candidate; a post-processing run SHALL NOT increase the number of distinct entities beyond what merging can produce.

#### Scenario: Value not present in the source text is rejected

- **GIVEN** a candidate whose supplied text window does not contain the string "Acme Corporation"
- **WHEN** the post-processor returns `{"decision": "modify", "value": "Acme Corporation"}` for it
- **THEN** the decision SHALL be discarded
- **AND** the candidate SHALL be persisted with the value the deterministic pipeline produced
- **AND** the discard SHALL be recorded for diagnostics

#### Scenario: Post-processing never adds an unanchored entity

- **GIVEN** a document producing N entities from the deterministic pipeline
- **WHEN** post-processing completes for that document
- **THEN** the number of persisted entities SHALL be less than or equal to N
- **AND** every persisted entity SHALL trace to at least one submitted candidate

#### Scenario: Case and punctuation folding do not defeat the substring check

- **GIVEN** a text window containing `"St.Xavier’s College,"`
- **WHEN** the post-processor returns `{"decision": "modify", "value": "St. Xavier's College"}`
- **THEN** the substring check SHALL compare both sides under the same canonical folding
- **AND** the value SHALL be accepted

### Requirement: Permitted transformations are enumerated and enforced

The system SHALL permit only the following post-processor transformations, each subject to its stated condition, and SHALL reject any decision that exceeds them: merging same-type, same-page neighbours within `max_entity_word_gap` where the merged value is contiguous in the source text; repairing a span boundary within the enclosing sentence; correcting `entity_type` to a type present in the tenant's `entity_definitions`; and rejecting an invalid extraction artifact. The system SHALL NOT permit the post-processor to normalize punctuation, whitespace, or casing; to emit typed value fields directly; to canonicalize surface variants to aliases; or to introduce an entity type absent from the tenant's configuration.

#### Scenario: Merge within the gap bound on the same page is applied

- **GIVEN** two `YEARS_OF_EXP` candidates on page 0 with values `two` and `half years`, separated by two words in the source text `"Having two and a half years of experience"`
- **WHEN** the post-processor returns a `merge` decision producing `two and a half years`
- **THEN** the merged value SHALL be verified as contiguous in the source text
- **AND** a single entity SHALL be persisted with `postprocess_status = 'merged'`
- **AND** semantic normalization SHALL derive `value_number = 2.5` with `value_unit = 'years'`

#### Scenario: Merge across pages is rejected

- **GIVEN** two same-type candidates whose `page_number` values differ
- **WHEN** the post-processor returns a `merge` decision for them
- **THEN** the decision SHALL be rejected
- **AND** both candidates SHALL be persisted as the deterministic pipeline produced them

#### Scenario: Entity type correction to a configured type is applied

- **GIVEN** a candidate extracted as `entity_type = 'COMPANY'` with value `HANNAH`, and a tenant whose `entity_definitions` contains `NAME`
- **WHEN** the post-processor returns `{"decision": "modify", "entity_type": "NAME"}`
- **THEN** the entity SHALL be persisted with `entity_type = 'NAME'`
- **AND** the original type SHALL be retained as provenance

#### Scenario: Entity type correction to an unconfigured type is rejected

- **GIVEN** a tenant whose `entity_definitions` does not contain `PERSON`
- **WHEN** the post-processor returns `{"decision": "modify", "entity_type": "PERSON"}`
- **THEN** the decision SHALL be rejected
- **AND** the candidate SHALL be persisted with its original type

#### Scenario: Directly emitted typed values are ignored

- **GIVEN** the post-processor returns an object containing a `value_number` field
- **WHEN** the decision is validated
- **THEN** the `value_number` field SHALL be ignored
- **AND** typed values SHALL be derived only by the deterministic semantic normalizer

#### Scenario: Rejection removes an invalid artifact

- **GIVEN** a candidate extracted as `entity_type = 'PHONE_NUMBER'` with value `Z5060835`
- **WHEN** the post-processor returns `{"decision": "reject"}`
- **THEN** no `document_entities` row SHALL be persisted for that candidate
- **AND** the rejection SHALL be recorded for diagnostics

### Requirement: Post-processing failure never destroys a successful extraction

The system SHALL persist the validated deterministic extraction result whenever the post-processing stage fails for any reason, including timeout, provider error, rate limiting, malformed response, or exhausted token budget. A post-processing failure SHALL mark affected rows and the run as degraded; it SHALL NOT fail the extraction run and SHALL NOT discard extracted entities.

#### Scenario: Timeout persists the deterministic result

- **GIVEN** post-processing is enabled for a run
- **WHEN** the post-processor call exceeds `postprocess_timeout_seconds`
- **THEN** the deterministic entities for that document SHALL be persisted
- **AND** their `postprocess_status` SHALL be `failed`
- **AND** the document SHALL count toward the run's `processed_count`, not `failed_count`

#### Scenario: Provider error retries once then degrades

- **GIVEN** the post-processing provider returns a server error
- **WHEN** the stage runs
- **THEN** the system SHALL retry at most once with backoff
- **AND** on a second failure the deterministic result SHALL be persisted and marked `failed`

#### Scenario: Rate limiting is respected within the run budget

- **GIVEN** the provider responds with HTTP 429 and a `Retry-After` value
- **WHEN** the remaining run budget accommodates the indicated wait
- **THEN** the system SHALL wait and retry once
- **AND** when the budget does not accommodate it the system SHALL persist the deterministic result and mark it `failed`

#### Scenario: Token budget exhaustion degrades the remainder of the run

- **GIVEN** a run whose post-processing token budget is exhausted after some documents are processed
- **WHEN** further documents are processed
- **THEN** those documents SHALL be processed without post-processing
- **AND** the run SHALL complete with status `completed` and a degraded indicator recorded

#### Scenario: A failed run is never the consequence of post-processing alone

- **GIVEN** every post-processing call in a run fails
- **WHEN** all deterministic extractions succeed
- **THEN** the run SHALL complete with status `completed`
- **AND** every document SHALL have its entities persisted

### Requirement: Post-processing is tenant-scoped and server-controlled

Tenant identity, schema, and document scope SHALL be derived from server-controlled worker context and SHALL NOT be readable from or influenced by post-processor output. A post-processing request SHALL contain content from exactly one document belonging to exactly one tenant. The document text window supplied as evidence SHALL be bounded by `postprocess_context_chars`.

#### Scenario: A request never spans documents

- **GIVEN** a batch run processing multiple documents
- **WHEN** post-processing requests are constructed
- **THEN** each request SHALL contain text from exactly one document

#### Scenario: Post-processor output cannot redirect persistence

- **GIVEN** a post-processor response containing fields naming a `document_id`, `tenant_id`, or schema
- **WHEN** the response is validated
- **THEN** those fields SHALL be ignored
- **AND** persistence SHALL target the schema and document resolved by the worker

#### Scenario: Evidence window is bounded

- **GIVEN** a document longer than `postprocess_context_chars`
- **WHEN** a post-processing request is built for a candidate in that document
- **THEN** the supplied text window SHALL not exceed `postprocess_context_chars`
- **AND** the window SHALL contain the candidate's span
