## ADDED Requirements

### Requirement: Q&A-Pair Proposal Input

The system SHALL allow a Tenant Admin to supply one question/answer document (PDF, DOC,
DOCX, or TXT) as an input to a schema proposal. The document SHALL be parsed through the
same text-extraction path used for training documents, and its extracted text SHALL be
passed to the proposal prompt together with the seed documents and the tenant's existing
QA pairs. The Q&A document SHALL be retained so a proposal's inputs are reproducible.
Supplying a Q&A document SHALL NOT create, modify, or activate any entity type.

#### Scenario: Schema proposal accepts a Q&A-pair document

- **GIVEN** a tenant with 3 processed seed documents
- **WHEN** a Tenant Admin requests a schema proposal for that seed set and uploads a TXT
  Q&A-pair document
- **THEN** the response SHALL have status 202 and the body SHALL contain a `proposal_id`
- **AND** the Q&A document SHALL be retrievable as an input of that proposal

#### Scenario: Q&A-pair text reaches the proposal prompt

- **GIVEN** a Q&A-pair document containing the question "What is the contract identifier?"
- **WHEN** the proposal is generated
- **THEN** the prompt sent to the LLM SHALL contain the Q&A document's extracted text

#### Scenario: An unsupported Q&A-pair file type is rejected

- **GIVEN** a Tenant Admin requesting a schema proposal
- **WHEN** they upload a `.csv` file as the Q&A pair
- **THEN** the response SHALL have status 422 and the error SHALL name the supported types

#### Scenario: Uploading a Q&A pair creates no entity types

- **GIVEN** a tenant with exactly 2 active entity types
- **WHEN** a schema proposal is requested with a Q&A-pair document
- **THEN** the tenant SHALL still have exactly 2 active entity types

### Requirement: Batch Kind

Every batch pre-labeling job SHALL carry a `batch_kind` of `initial` or `large`, chosen at
trigger time. An `initial` batch SHALL cover at most 5 documents and is reviewed by the
Tenant Admin. A `large` batch has no upper document cap and is reviewed by an Annotator
Admin. The trigger endpoint SHALL reject an `initial` batch of more than 5 documents with
status 422.

#### Scenario: Initial batch is capped at five documents

- **GIVEN** a Tenant Admin submitting 8 documents for an `initial` batch
- **WHEN** the trigger endpoint is called
- **THEN** the response SHALL have status 422 and the error SHALL state the 5-document cap

#### Scenario: Large batch has no document cap

- **GIVEN** a Tenant Admin submitting 120 documents for a `large` batch
- **WHEN** the trigger endpoint is called
- **THEN** the response SHALL have status 202 and the batch SHALL be recorded with
  `batch_kind = large`

#### Scenario: Batch kind is reported on batch status

- **GIVEN** an `initial` batch and a `large` batch for the same tenant
- **WHEN** each batch's status is retrieved
- **THEN** each status response SHALL report its `batch_kind`

### Requirement: Named Batch State

The system SHALL expose a single `state` for each batch, derived from its per-document
outcomes: `queued` before processing starts, `processing` while documents are being
labelled, `completed` when every document succeeded, `partially_completed` when the batch
finished with at least one failed document and at least one succeeded, and `failed` when
every document failed. Computing or reading the state SHALL NOT block the caller.

#### Scenario: A fully successful batch reports completed

- **GIVEN** a `large` batch over 10 documents where every document succeeds
- **WHEN** the batch finishes and its status is retrieved
- **THEN** the `state` SHALL be `completed`

#### Scenario: A batch with mixed outcomes reports partially_completed

- **GIVEN** a batch over 10 documents where 9 succeed and 1 fails
- **WHEN** the batch finishes and its status is retrieved
- **THEN** the `state` SHALL be `partially_completed`

#### Scenario: A batch where every document fails reports failed

- **GIVEN** a batch over 5 documents where the LLM call fails for all 5
- **WHEN** the batch finishes and its status is retrieved
- **THEN** the `state` SHALL be `failed`
- **AND** no suggested span SHALL exist for the batch

#### Scenario: Batch status is available while processing

- **GIVEN** a `large` batch that has started but not finished
- **WHEN** its status is retrieved
- **THEN** the response SHALL return promptly with `state = processing` and a progress count

### Requirement: Initial-Batch Review Guidance

The system SHALL persist a Tenant Admin's corrections made while reviewing an `initial`
batch — corrected spans and an optional free-text note per document. When a subsequent
`large` batch is triggered for the same tenant, the system SHALL include that persisted
guidance in the pre-labeling prompt, in addition to the tenant's QA pairs.

#### Scenario: Initial-batch corrections are persisted

- **GIVEN** a completed `initial` batch
- **WHEN** a Tenant Admin corrects a suggested span's entity type and adds a note
- **THEN** the correction and the note SHALL be stored against that batch

#### Scenario: Guidance from the initial batch reaches the large-batch prompt

- **GIVEN** a tenant with a reviewed `initial` batch whose stored guidance includes the note
  "treat internal project codenames as PROJECT"
- **WHEN** a `large` batch is triggered for that tenant
- **THEN** the pre-labeling prompt SHALL contain that guidance note

#### Scenario: No guidance without a reviewed initial batch

- **GIVEN** a tenant that has never run an `initial` batch
- **WHEN** a `large` batch is triggered
- **THEN** the prompt SHALL be built from the tenant's QA pairs alone and the batch SHALL
  still run

## MODIFIED Requirements

### Requirement: Sampled Acceptance Gate

The system SHALL require a sampled review before the suggestions produced by a batch may be
bulk-promoted to confirmed spans. The system SHALL draw the review sample randomly from the
batch and SHALL record which documents were drawn. The system SHALL compute an agreement
rate from the reviewer's dispositions and SHALL permit bulk acceptance only when that rate
meets or exceeds the configured threshold. The system SHALL NOT permit partial acceptance
of a batch that falls below the threshold.

The acceptance review of a `large` batch SHALL be performed by a user with the `annotator`
role; a `tenant_admin` SHALL NOT accept a `large` batch. When an Annotator Admin accepts a
`large` batch, in addition to bulk-promoting its spans, the system SHALL mark the batch
training-eligible (`prelabel_batches.training_eligible_at`), set
`prelabel_batches.annotator_review_status = 'approved'`, and write a persistent
notification addressed to `recipient_role = 'tenant_admin'` with kind
`automated_batch_approved`. The system SHALL NOT require any further Tenant Admin review of
an accepted `large` batch.

The acceptance review of an `initial` batch SHALL be performed by the `tenant_admin` role
and SHALL NOT mark the batch training-eligible or notify anyone; its purpose is to produce
review guidance for the subsequent `large` batch.

#### Scenario: Sample is drawn randomly and recorded

- **GIVEN** a completed batch pre-labeling job over 100 documents
- **WHEN** a reviewer starts the acceptance review
- **THEN** the system SHALL present a randomly drawn sample of documents
- **AND** the identities of the sampled documents SHALL be stored with the acceptance record

#### Scenario: Batch meeting the threshold can be bulk-accepted

- **GIVEN** a batch whose sampled review produces an agreement rate at or above the configured threshold
- **WHEN** the reviewer accepts the batch
- **THEN** all of the batch's suggested spans SHALL be promoted to confirmed spans
- **AND** the acceptance record SHALL store the sample size, the agreement rate, the reviewer, and the timestamp

#### Scenario: Batch below the threshold cannot be bulk-accepted

- **GIVEN** a batch whose sampled review produces an agreement rate below the configured threshold
- **WHEN** the reviewer attempts to accept the batch
- **THEN** the request SHALL be rejected
- **AND** no suggested span from that batch SHALL be promoted to a confirmed span
- **AND** the measured agreement rate SHALL be recorded

#### Scenario: Bulk acceptance is not permitted without a completed sample review

- **GIVEN** a completed batch pre-labeling job whose sample review has not been completed
- **WHEN** a reviewer attempts to bulk-accept the batch
- **THEN** the request SHALL be rejected
- **AND** the error SHALL indicate the sample review is incomplete

#### Scenario: Bulk-promoted spans record their acceptance route

- **GIVEN** a batch that has been bulk-accepted
- **WHEN** the resulting confirmed spans are inspected
- **THEN** each SHALL record that it was promoted via batch acceptance
- **AND** each SHALL be distinguishable from a span promoted through individual review

#### Scenario: A tenant admin cannot accept a large batch

- **GIVEN** a completed `large` batch with a passing sample review
- **WHEN** a `tenant_admin` attempts to accept it
- **THEN** the request SHALL be rejected with status 403

#### Scenario: Annotator acceptance of a large batch makes it training-eligible and notifies the tenant admin

- **GIVEN** a completed `large` batch with a sample review at or above threshold
- **WHEN** an `annotator` accepts it
- **THEN** the batch's suggested spans SHALL be promoted to confirmed spans
- **AND** `prelabel_batches.training_eligible_at` SHALL be set
- **AND** `prelabel_batches.annotator_review_status` SHALL be `approved`
- **AND** a `public.notifications` row SHALL exist for that tenant with
  `recipient_role = tenant_admin` and kind `automated_batch_approved`

#### Scenario: Accepting an initial batch neither notifies nor marks training-eligible

- **GIVEN** a completed `initial` batch reviewed by a `tenant_admin` at or above threshold
- **WHEN** the `tenant_admin` accepts it
- **THEN** its spans SHALL be promoted
- **AND** `prelabel_batches.training_eligible_at` SHALL remain null
- **AND** no `automated_batch_approved` notification SHALL be written

### Requirement: Batch Pre-labeling

The system SHALL accept a set of documents and a `batch_kind` and enqueue a single batch
pre-labeling job covering all of them. The job SHALL apply the same extraction, grounding,
verification, and entity type constraints as single-document LLM pre-labeling. A failure on
one document SHALL NOT abort the batch. The system SHALL record a per-document outcome for
the batch and SHALL expose the batch's aggregate status, its `batch_kind`, and its derived
`state`.

#### Scenario: Enqueue a batch pre-labeling job

- **GIVEN** a tenant with 120 processed documents and at least one active entity type
- **WHEN** a Tenant Admin submits those documents for a `large` batch pre-labeling job
- **THEN** the response SHALL have status 202
- **AND** the response body SHALL contain a single `batch_id`

#### Scenario: One document failing does not abort the batch

- **GIVEN** a batch pre-labeling job over 10 documents in which the LLM call for the third document fails
- **WHEN** the batch completes
- **THEN** the batch status SHALL report 9 documents succeeded and 1 failed
- **AND** suggested spans SHALL exist for the 9 successful documents

#### Scenario: Batch pre-labeling honours the entity type constraint

- **GIVEN** a batch pre-labeling job for a tenant whose only active entity types are `institute` and `person_name`
- **WHEN** the batch completes
- **THEN** every suggested span produced by the batch SHALL have an entity type of `institute` or `person_name`
- **AND** no new entity type SHALL have been created

#### Scenario: Batch pre-labeling grounds quotes the same way as single-document pre-labeling

- **GIVEN** a batch containing a document where the LLM returns a quote that does not appear in the document text
- **WHEN** the batch completes
- **THEN** no suggested span SHALL be stored for that quote
- **AND** the discarded quote SHALL be counted in that document's ungrounded-suggestion count
