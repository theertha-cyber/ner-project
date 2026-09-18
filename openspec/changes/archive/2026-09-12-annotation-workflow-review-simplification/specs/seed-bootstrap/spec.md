## MODIFIED Requirements

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

## ADDED Requirements

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
