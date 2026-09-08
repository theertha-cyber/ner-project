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

The system SHALL accept a set of documents and enqueue a single batch pre-labeling job covering all of them. The job SHALL apply the same extraction, grounding, verification, and entity type constraints as single-document LLM pre-labeling. A failure on one document SHALL NOT abort the batch. The system SHALL record a per-document outcome for the batch and SHALL expose the batch's aggregate status.

#### Scenario: Enqueue a batch pre-labeling job

- **GIVEN** a tenant with 120 processed documents and at least one active entity type
- **WHEN** a Tenant Admin submits those documents for batch pre-labeling
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

The system SHALL require a sampled review before the suggestions produced by a batch may be bulk-promoted to confirmed spans. The system SHALL draw the review sample randomly from the batch and SHALL record which documents were drawn. The system SHALL compute an agreement rate from the reviewer's dispositions and SHALL permit bulk acceptance only when that rate meets or exceeds the configured threshold. The system SHALL NOT permit partial acceptance of a batch that falls below the threshold.

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
