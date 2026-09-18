# Seed Bootstrap

## Purpose

The path from a seed set of documents to a first trained model. Covers entity schema proposal
with per-candidate human approval, batch pre-labeling of a document set as one trackable job,
sampled acceptance of a machine-annotated batch, and the pre-submission per-entity-type
readiness check.

Three boundaries define this capability. The LLM proposes entity types but never creates them —
an approved candidate is created through the existing `entity-config` API, inheriting its
validation, versioning, and tenant scoping. Batch pre-labeling reuses `llm-prelabeling`'s
extraction and grounding path per document rather than a second implementation, so the
extractive-only guarantee cannot differ between the single-document and batch routes. And bulk
promotion is gated on a measured agreement rate over a randomly drawn, recorded sample: a batch
that falls short promotes zero spans, with no partial-acceptance path.

The readiness check is advisory. It reads the platform's existing per-entity-type dataset
threshold and never blocks training submission, sets hyperparameters, or pre-empts the System
Admin approval step.

---

## Requirements

### Requirement: Entity Schema Proposal

The system SHALL generate a proposed entity schema for a tenant from a supplied seed set of processed documents together with any QA pairs configured on the tenant's existing entity types. Each proposed candidate SHALL carry a name, a description, and example values quoted verbatim from the seed documents. The system SHALL NOT create, modify, or activate any entity type as a result of generating a proposal.

#### Scenario: Generate a schema proposal from a seed set

- **GIVEN** a tenant with 5 processed documents supplied as a seed set
- **WHEN** a Tenant Admin requests a schema proposal for that seed set
- **THEN** the response SHALL have status 202
- **AND** the response body SHALL contain a `proposal_id`

#### Scenario: Proposal candidates carry verbatim examples

- **GIVEN** a completed schema proposal generated from a seed set containing the text "Vellore Institute of Technology"
- **WHEN** the proposal is retrieved
- **THEN** each candidate SHALL include a name, a description, and at least one example value
- **AND** every example value SHALL appear verbatim in at least one seed document

#### Scenario: Generating a proposal creates no entity types

- **GIVEN** a tenant with exactly 2 active entity types
- **WHEN** a schema proposal completes and returns 4 candidates
- **THEN** the tenant SHALL still have exactly 2 active entity types
- **AND** no entity type version SHALL have been incremented

#### Scenario: Proposal on a seed set with no processed documents

- **GIVEN** a seed set in which no document has extracted text
- **WHEN** a Tenant Admin requests a schema proposal
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate no processed documents are available

### Requirement: Schema Proposal Approval

The system SHALL allow a Tenant Admin to approve, edit, or reject each candidate in a proposal individually. An approved candidate SHALL be created as an entity type through the existing entity type creation API, inheriting its validation, versioning, and tenant scoping. A rejected candidate SHALL NOT create an entity type. The system SHALL record the disposition of every candidate.

#### Scenario: Approving a candidate creates an entity type

- **GIVEN** a proposal containing a candidate named `institute`
- **WHEN** a Tenant Admin approves that candidate
- **THEN** an entity type named `institute` SHALL exist for the tenant at version 1
- **AND** the candidate SHALL be recorded as approved

#### Scenario: Rejecting a candidate creates nothing

- **GIVEN** a proposal containing a candidate named `job_title`
- **WHEN** a Tenant Admin rejects that candidate
- **THEN** no entity type named `job_title` SHALL exist for the tenant
- **AND** the candidate SHALL be recorded as rejected

#### Scenario: Editing a candidate before approval

- **GIVEN** a proposal containing a candidate named `institute` with description "A school"
- **WHEN** a Tenant Admin edits the description to "A degree-granting institution" and approves it
- **THEN** the created entity type SHALL have description "A degree-granting institution"

#### Scenario: Approving a candidate whose name already exists

- **GIVEN** a tenant that already has an active entity type named `institute`
- **AND** a proposal containing a candidate also named `institute`
- **WHEN** a Tenant Admin approves that candidate
- **THEN** the response SHALL have status 422
- **AND** no duplicate entity type SHALL be created

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

### Requirement: Sampled Acceptance Gate

The system SHALL require a sampled review before the suggestions produced by an `initial`
batch may be bulk-promoted to confirmed spans. The system SHALL draw the review sample
randomly from the batch and SHALL record which documents were drawn. The system SHALL compute
an agreement rate from the reviewer's dispositions and SHALL permit bulk acceptance only when
that rate meets or exceeds the configured threshold. The system SHALL NOT permit partial
acceptance of a batch that falls below the threshold.

The acceptance review of an `initial` batch SHALL be performed by a user with the `annotator`
role; a `tenant_admin` SHALL NOT review or accept an `initial` batch. When an Annotator Admin
accepts an `initial` batch, the system SHALL record `prelabel_batches.annotator_review_status
= 'approved'`. Accepting an `initial` batch SHALL NOT mark it training-eligible
(`prelabel_batches.training_eligible_at` SHALL remain null) and SHALL NOT notify anyone; its
purpose is to produce review guidance for the subsequent `large` batch and to signal that the
large-batch step may now begin.

A `large` batch has no acceptance review of any kind — see "Automatic Large-Batch Promotion"
below. Every acceptance-gate endpoint (start review, read review, submit review, accept) SHALL
reject a call made against a `large` batch with status 422, regardless of the caller's role.

#### Scenario: Sample is drawn randomly and recorded

- **GIVEN** a completed `initial` batch pre-labeling job over 5 documents
- **WHEN** an Annotator Admin starts the acceptance review
- **THEN** the system SHALL present a randomly drawn sample of documents
- **AND** the identities of the sampled documents SHALL be stored with the acceptance record

#### Scenario: Batch meeting the threshold can be bulk-accepted

- **GIVEN** an `initial` batch whose sampled review produces an agreement rate at or above the configured threshold
- **WHEN** an Annotator Admin accepts the batch
- **THEN** all of the batch's suggested spans SHALL be promoted to confirmed spans
- **AND** the acceptance record SHALL store the sample size, the agreement rate, the reviewer, and the timestamp

#### Scenario: Batch below the threshold cannot be bulk-accepted

- **GIVEN** an `initial` batch whose sampled review produces an agreement rate below the configured threshold
- **WHEN** an Annotator Admin attempts to accept the batch
- **THEN** the request SHALL be rejected
- **AND** no suggested span from that batch SHALL be promoted to a confirmed span
- **AND** the measured agreement rate SHALL be recorded

#### Scenario: Bulk acceptance is not permitted without a completed sample review

- **GIVEN** a completed `initial` batch pre-labeling job whose sample review has not been completed
- **WHEN** an Annotator Admin attempts to bulk-accept the batch
- **THEN** the request SHALL be rejected
- **AND** the error SHALL indicate the sample review is incomplete

#### Scenario: Bulk-promoted spans record their acceptance route

- **GIVEN** an `initial` batch that has been bulk-accepted
- **WHEN** the resulting confirmed spans are inspected
- **THEN** each SHALL record that it was promoted via batch acceptance
- **AND** each SHALL be distinguishable from a span promoted through individual review

#### Scenario: A tenant admin cannot review or accept an initial batch

- **GIVEN** a completed `initial` batch
- **WHEN** a `tenant_admin` attempts to start its acceptance review, or to accept it
- **THEN** each request SHALL be rejected with status 403

#### Scenario: Annotator acceptance of an initial batch is recorded but is not the training-eligibility gate

- **GIVEN** a completed `initial` batch with a sample review at or above threshold
- **WHEN** an `annotator` accepts it
- **THEN** the batch's spans SHALL be promoted
- **AND** `prelabel_batches.annotator_review_status` SHALL be `approved`
- **AND** `prelabel_batches.training_eligible_at` SHALL remain null
- **AND** no `automated_batch_approved` notification SHALL be written

#### Scenario: A large batch refuses every acceptance-gate endpoint

- **GIVEN** a completed `large` batch
- **WHEN** a caller of any role calls the start-review, read-review, submit-review, or accept endpoint for it
- **THEN** every one of those requests SHALL be rejected with status 422
- **AND** the error SHALL state that a large batch is not manually reviewed

#### Scenario: A tenant admin cannot accept a large batch

- **GIVEN** a completed `large` batch
- **WHEN** a `tenant_admin` attempts to accept it
- **THEN** the request SHALL be rejected with status 422 — a `large` batch is never manually
  accepted by anyone, not only not by a `tenant_admin`

#### Scenario: Annotator acceptance of a large batch makes it training-eligible and notifies the tenant admin

- **GIVEN** a completed `large` batch
- **WHEN** an `annotator` attempts to accept it
- **THEN** the request SHALL be rejected with status 422 — there is no manual acceptance route
  for a `large` batch left to perform
- **AND** the batch instead becomes training-eligible and notifies the tenant admin
  automatically, per "Automatic Large-Batch Promotion" below, the moment pre-labeling finishes,
  with no acceptance call of any kind

#### Scenario: Accepting an initial batch neither notifies nor marks training-eligible

- **GIVEN** a completed `initial` batch with a sample review at or above threshold
- **WHEN** an `annotator` accepts it
- **THEN** its spans SHALL be promoted
- **AND** `prelabel_batches.training_eligible_at` SHALL remain null
- **AND** no `automated_batch_approved` notification SHALL be written

### Requirement: Pre-Submission Readiness Check

The system SHALL report, before a training job is submitted, the tenant's per-entity-type annotated entity counts against the platform's existing per-entity-type dataset readiness threshold, naming every entity type that falls short. The evaluated set SHALL be the union of the tenant's active entity type definitions and the distinct entity types present in confirmed spans. The check SHALL be advisory: it SHALL NOT block training submission, SHALL NOT set hyperparameters, and SHALL NOT replace or pre-empt the existing System Admin training approval step.

#### Scenario: Readiness check names shortfalling entity types

- **GIVEN** a tenant with entity types `institute` (250 confirmed entities) and `person_name` (40 confirmed entities), against a per-type threshold of 200
- **WHEN** the readiness check is requested
- **THEN** the response SHALL report `institute` as meeting the threshold
- **AND** the response SHALL report `person_name` as falling short, with its count of 40

#### Scenario: Configured but unannotated entity types are visible

- **GIVEN** a tenant with an active entity type `skill` that has zero confirmed spans
- **WHEN** the readiness check is requested
- **THEN** `skill` SHALL appear in the report with a count of 0

#### Scenario: Readiness check does not block submission

- **GIVEN** a tenant whose readiness check reports two entity types below the threshold
- **WHEN** a training job is submitted for that tenant
- **THEN** the submission SHALL be accepted
- **AND** the job SHALL enter the existing pending-approval state

#### Scenario: Readiness check does not use a tenant-wide total

- **GIVEN** a tenant with 1000 confirmed entities of type `institute` and 5 of type `person_name`
- **WHEN** the readiness check is requested
- **THEN** `person_name` SHALL be reported as falling short
- **AND** the report SHALL NOT indicate readiness on the basis of the combined total

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
trigger time. An `initial` batch SHALL cover at most 5 documents and is reviewed by an
Annotator Admin. A `large` batch has no upper document cap and is reviewed by no one — its
suggestions are promoted to confirmed spans automatically once pre-labeling finishes (see
"Automatic Large-Batch Promotion"). The trigger endpoint SHALL reject an `initial` batch of
more than 5 documents with status 422.

A `large` batch SHALL NOT be created for a tenant until an `initial` batch for that tenant has
been approved by an Annotator Admin (`annotator_review_status = 'approved'`). The trigger
endpoint SHALL reject a `large`-batch request with status 422 when no such `initial` batch
exists, naming the reason.

#### Scenario: Initial batch is capped at five documents

- **GIVEN** a Tenant Admin submitting 8 documents for an `initial` batch
- **WHEN** the trigger endpoint is called
- **THEN** the response SHALL have status 422 and the error SHALL state the 5-document cap

#### Scenario: Large batch has no document cap

- **GIVEN** a tenant with an Annotator-Admin-approved `initial` batch, and a Tenant Admin
  submitting 120 documents for a `large` batch
- **WHEN** the trigger endpoint is called
- **THEN** the response SHALL have status 202 and the batch SHALL be recorded with
  `batch_kind = large`

#### Scenario: Batch kind is reported on batch status

- **GIVEN** an `initial` batch and a `large` batch for the same tenant
- **WHEN** each batch's status is retrieved
- **THEN** each status response SHALL report its `batch_kind`

#### Scenario: A large batch is refused before any initial batch is approved

- **GIVEN** a tenant with no `initial` batch, or an `initial` batch that has not yet been
  approved by an Annotator Admin
- **WHEN** a Tenant Admin submits documents for a `large` batch
- **THEN** the response SHALL have status 422 and the error SHALL state that an approved
  initial validation batch is required first
- **AND** no pre-labeling task SHALL be enqueued

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

The system SHALL persist an Annotator Admin's corrections made while reviewing an `initial`
batch — corrected spans and an optional free-text note per document. When a subsequent
`large` batch is triggered for the same tenant, the system SHALL include that persisted
guidance in the pre-labeling prompt, in addition to the tenant's QA pairs.

#### Scenario: Initial-batch corrections are persisted

- **GIVEN** a completed `initial` batch
- **WHEN** an Annotator Admin corrects a suggested span's entity type and adds a note
- **THEN** the correction and the note SHALL be stored against that batch

#### Scenario: A tenant admin cannot record initial-batch guidance

- **GIVEN** a completed `initial` batch
- **WHEN** a `tenant_admin` attempts to record guidance for it
- **THEN** the request SHALL be rejected with status 403

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

### Requirement: Automatic Large-Batch Promotion

The system SHALL promote every suggested span produced by a `large` batch to a confirmed span
automatically, with no human review of any kind, as soon as the batch's pre-labeling job
reaches a terminal state (`completed` or `partially_completed`) with at least one succeeded
document. This SHALL happen at most once per batch even if the completing task is retried. On
promotion, the system SHALL set `prelabel_batches.training_eligible_at`, set
`prelabel_batches.annotator_review_status = 'approved'`, and write a persistent notification
addressed to `recipient_role = 'tenant_admin'` with kind `automated_batch_approved`. A `large`
batch that fails entirely (every document failed) SHALL NOT be promoted and SHALL NOT be
marked training-eligible.

Each promoted span SHALL record that it was promoted via batch acceptance, distinguishable
from an individually-promoted span, in the same manner as a batch a human reviewer accepted.

#### Scenario: A finished large batch is promoted with no reviewer of any role

- **GIVEN** a `large` batch over 5 documents where every document succeeds
- **WHEN** the pre-labeling job finishes
- **THEN** every suggested span for those documents SHALL become a confirmed span
- **AND** no acceptance-gate endpoint SHALL have been called by any user
- **AND** `prelabel_batches.training_eligible_at` SHALL be set
- **AND** `prelabel_batches.annotator_review_status` SHALL be `approved`
- **AND** a `public.notifications` row SHALL exist for that tenant with
  `recipient_role = tenant_admin` and kind `automated_batch_approved`

#### Scenario: A partially-completed large batch still promotes its successes

- **GIVEN** a `large` batch over 10 documents where 8 succeed and 2 fail
- **WHEN** the pre-labeling job finishes
- **THEN** the 8 succeeding documents' suggested spans SHALL become confirmed spans
- **AND** the batch SHALL be marked training-eligible

#### Scenario: A fully failed large batch is not promoted

- **GIVEN** a `large` batch over 3 documents where every document fails
- **WHEN** the pre-labeling job finishes
- **THEN** no span SHALL be promoted
- **AND** `prelabel_batches.training_eligible_at` SHALL remain null

#### Scenario: Promoted spans record their acceptance route like a reviewed batch's

- **GIVEN** an auto-promoted `large` batch
- **WHEN** its resulting confirmed spans are inspected
- **THEN** each SHALL be linked to a batch-acceptance record via the same provenance mechanism
  a human-reviewed batch's spans use
- **AND** each SHALL be distinguishable from a span promoted through individual review

### Requirement: Batch Pre-labeling Screen Shows Both Stages Persistently

The Tenant Admin's Batch Pre-labeling screen SHALL display the `initial` batch's status and
the `large` batch's status in separate, simultaneously-visible sections once each batch
exists; neither section SHALL be replaced or hidden by the other. The `large`-batch section
SHALL be visible once the tenant's `initial` batch exists, showing a locked/explanatory state
before that `initial` batch is Annotator-approved. Once the `initial` batch is
Annotator-approved, the `large`-batch section SHALL show its document picker as a repeatable
action: the picker SHALL remain available to start another `large` batch regardless of
whether a previous `large` batch exists or has completed, and SHALL be disabled only while the
tenant's most recently created `large` batch is queued or processing. The most recently
created `large` batch's status SHALL be shown as its own labeled section distinct from the
picker. The screen SHALL show a distinct, persistent confirmation once the `initial` batch is
Annotator-approved, and this confirmation SHALL remain visible after a `large` batch is
subsequently created. The screen SHALL trigger a client-side notification at the moment the
`initial` batch is observed to become Annotator-approved, and again at the moment a `large`
batch is observed to reach a terminal, successful state. The "Train model" action that appears
once a large batch completes SHALL navigate to `/training-jobs?source=automated` — the
Automated flow's own hand-off, so a training run started from here trains only on
automated-batch-promoted spans, never a blend with manual annotations or imported data.

#### Scenario: Both stages remain visible once the initial batch is approved and a large batch exists

- **GIVEN** a tenant whose `initial` batch is Annotator-approved and whose `large` batch has
  completed
- **WHEN** the Tenant Admin views the Batch Pre-labeling screen
- **THEN** the initial batch's approval confirmation SHALL be visible
- **AND** the large batch's completion state and a "Train model" action SHALL also be visible
  at the same time

#### Scenario: The large-batch section is visible but locked before the initial batch is approved

- **GIVEN** a tenant whose `initial` batch exists but is not yet Annotator-approved
- **WHEN** the Tenant Admin views the Batch Pre-labeling screen
- **THEN** a large-batch section SHALL be visible
- **AND** it SHALL show an explanatory locked state rather than its document picker

#### Scenario: The large-batch section unlocks its picker once the initial batch is approved

- **GIVEN** a tenant whose `initial` batch has just become Annotator-approved
- **WHEN** the Tenant Admin views the Batch Pre-labeling screen
- **THEN** the large-batch section SHALL show its document picker, with no upper document cap
- **AND** the initial batch's own approval confirmation SHALL still be visible above it

#### Scenario: A notification fires when each stage completes

- **GIVEN** the Tenant Admin has the Batch Pre-labeling screen open
- **WHEN** the initial batch transitions to Annotator-approved, and later when a large batch
  transitions to a completed or partially-completed state
- **THEN** a client-side notification SHALL be shown at each of those two moments

#### Scenario: The large-batch picker stays available after a previous large batch has already completed

- **GIVEN** a tenant whose most recently created `large` batch has already completed
- **WHEN** the Tenant Admin views the Batch Pre-labeling screen
- **THEN** the document picker for starting another `large` batch SHALL still be shown
- **AND** it SHALL NOT be replaced or hidden by the completed batch's status section

#### Scenario: Starting another large batch is disabled while one is already running

- **GIVEN** a tenant whose most recently created `large` batch is queued or processing
- **WHEN** the Tenant Admin views the Batch Pre-labeling screen
- **THEN** the document picker SHALL be visible
- **AND** its submit action SHALL be disabled
- **AND** an explanatory message SHALL state that a batch is already running

#### Scenario: Train model navigates to the Automated flow's own training entry point

- **GIVEN** a large batch has completed
- **WHEN** the Tenant Admin activates "Train model"
- **THEN** navigation SHALL go to `/training-jobs?source=automated`
