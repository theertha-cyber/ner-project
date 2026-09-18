# Confidence-Routed Review

## Purpose

The loop that turns production extraction into training data. Extraction already scores every
prediction; this capability routes those scores rather than discarding the uncertain half, puts
the low-confidence part in front of a reviewer, and turns what the reviewer decides into confirmed
spans.

Four boundaries define it. **Two thresholds, never one** — the business-facing confidence
threshold decides what a consumer sees, a separate review threshold decides what is worth a
person's time, and moving either must not move the other. **One inference pass** — routing
consumes the predictions the extraction run already produced, so there is no second path that can
disagree with the first about what the model said. **One way into training data** — human and LLM
review resolve through the same outcome record, and spans are created only from those outcomes, so
neither route has a privileged or unaudited path. And **offsets, not values** — a span is a claim
about where an entity is in a document, which is why the existing value-level correction flow is
not an input here and keeps working for its own purpose.

Accumulation reporting stops at reporting. It says how much reviewed material exists since the
serving model was trained, excludes base-model output from that figure, and triggers nothing. The
decision to retrain belongs to a person.

---

## Requirements

### Requirement: Confidence-Based Routing

The system SHALL route each prediction produced by an extraction run according to a configurable review threshold, which SHALL be configurable independently of the business-facing extraction confidence threshold. A prediction at or above the review threshold SHALL be auto-accepted without review. A prediction below the review threshold SHALL be placed in the review queue. The system SHALL record, for every routed prediction, the model version that produced it. The system SHALL NOT run a second inference pass to perform routing.

#### Scenario: High-confidence prediction is auto-accepted

- **GIVEN** a review threshold of 0.90 and an extraction run producing a prediction with confidence 0.95
- **WHEN** routing runs
- **THEN** that prediction SHALL be recorded as auto-accepted
- **AND** it SHALL NOT appear in the review queue

#### Scenario: Low-confidence prediction enters the review queue

- **GIVEN** a review threshold of 0.90 and an extraction run producing a prediction with confidence 0.62
- **WHEN** routing runs
- **THEN** that prediction SHALL appear in the review queue
- **AND** its recorded confidence SHALL be 0.62

#### Scenario: Review threshold is independent of the extraction threshold

- **GIVEN** an extraction confidence threshold of 0.50 and a review threshold of 0.90
- **WHEN** the review threshold is changed to 0.80
- **THEN** the extraction confidence threshold SHALL remain 0.50
- **AND** business-facing extraction results SHALL be unchanged

#### Scenario: Routed predictions record the serving model version

- **GIVEN** an extraction run served by tenant model version 3
- **WHEN** routing runs
- **THEN** every routed prediction from that run SHALL record model version 3

### Requirement: Review Queue Resolution

The system SHALL allow a queued prediction to be resolved by either a human reviewer or the LLM, according to the tenant's configured review policy. Both routes SHALL produce the same outcome structure: confirmed as-is, corrected to different character offsets or a different entity type, or rejected as not an entity. The system SHALL record which route produced each outcome. The LLM review route SHALL run as an asynchronous background job on the non-GPU queue used for LLM work, and SHALL NOT write spans directly without passing through the same outcome path as a human review.

#### Scenario: Human reviewer confirms a queued prediction

- **GIVEN** a queued prediction for entity type `organization` at offsets 45-53
- **WHEN** a human reviewer confirms it as-is
- **THEN** the outcome SHALL be recorded as confirmed
- **AND** the outcome SHALL record the human review route

#### Scenario: Human reviewer corrects the offsets of a queued prediction

- **GIVEN** a queued prediction for entity type `organization` at offsets 45-53
- **WHEN** a human reviewer corrects it to offsets 45-58
- **THEN** the outcome SHALL be recorded as corrected with offsets 45-58

#### Scenario: Reviewer rejects a queued prediction

- **GIVEN** a queued prediction the reviewer judges not to be an entity
- **WHEN** the reviewer rejects it
- **THEN** the outcome SHALL be recorded as rejected
- **AND** no confirmed span SHALL be created from it

#### Scenario: LLM review produces the same outcome structure

- **GIVEN** a tenant whose review policy routes queued predictions to the LLM
- **WHEN** the LLM review job resolves a queued prediction
- **THEN** the outcome SHALL be one of confirmed, corrected, or rejected
- **AND** the outcome SHALL record the LLM review route

#### Scenario: LLM review does not bypass the outcome path

- **GIVEN** a tenant whose review policy routes queued predictions to the LLM
- **WHEN** the LLM review job completes
- **THEN** every resulting confirmed span SHALL have been created from a recorded review outcome
- **AND** no span SHALL have been written directly by the LLM review job

### Requirement: Review Outcomes Become Confirmed Spans

The system SHALL create a confirmed span from each review outcome that is confirmed or corrected. The span SHALL be defined by character offsets over the document text. The system SHALL NOT derive a span from an extracted entity's corrected value. Each span created this way SHALL record that it originated from production review, distinguishably from spans created by manual annotation or by batch acceptance.

#### Scenario: A confirmed outcome creates a span at the predicted offsets

- **GIVEN** a review outcome confirming a prediction of type `organization` at offsets 45-53
- **WHEN** the outcome is processed
- **THEN** a confirmed span SHALL exist for that document with entity type `organization`, `char_start` 45 and `char_end` 53

#### Scenario: A corrected outcome creates a span at the corrected offsets

- **GIVEN** a review outcome correcting a prediction to offsets 45-58 with entity type `organization`
- **WHEN** the outcome is processed
- **THEN** a confirmed span SHALL exist with `char_start` 45 and `char_end` 58
- **AND** no span SHALL exist at the original offsets 45-53

#### Scenario: A rejected outcome creates no span

- **GIVEN** a review outcome rejecting a prediction
- **WHEN** the outcome is processed
- **THEN** no confirmed span SHALL be created for that prediction

#### Scenario: A value correction does not produce a span

- **GIVEN** an extracted entity whose `corrected_value` differs from the document text at its offsets
- **WHEN** review outcomes are processed
- **THEN** no confirmed span SHALL be created from that `corrected_value`

#### Scenario: Spans from production review are distinguishable by origin

- **GIVEN** a tenant with confirmed spans created by manual annotation, by batch acceptance, and by production review
- **WHEN** the spans are inspected
- **THEN** each SHALL record its origin
- **AND** spans originating from production review SHALL be distinguishable from the other two

### Requirement: Accumulation Reporting

The system SHALL report how many confirmed spans have accumulated from production review since the tenant's currently serving model version was trained. Predictions served by the base model rather than a tenant-trained model SHALL be recorded distinctly and SHALL NOT count toward that figure. The system SHALL NOT trigger, schedule, or initiate a training job as a result of this figure changing. The system SHALL NOT present this figure as a dataset readiness measure.

#### Scenario: Accumulation is reported against the current model version

- **GIVEN** a tenant serving model version 3, with 40 confirmed spans created by production review since version 3 was trained
- **WHEN** the accumulation figure is requested
- **THEN** the response SHALL report 40 spans accumulated against model version 3

#### Scenario: Base-model predictions do not count toward accumulation

- **GIVEN** a tenant with no trained model, served by the base model
- **AND** 25 confirmed spans created by production review of base-model predictions
- **WHEN** the accumulation figure is requested
- **THEN** those 25 spans SHALL NOT be counted as accumulation against a tenant-trained model version
- **AND** they SHALL be recorded distinctly

#### Scenario: Accumulation growth triggers nothing

- **GIVEN** a tenant whose accumulation figure grows from 40 to 500 spans
- **WHEN** the figure is updated
- **THEN** no training job SHALL be created, queued, or submitted
- **AND** no notification SHALL initiate a training run

### Requirement: Auto-Accept Audit Sampling

The system SHALL periodically draw a random sample of auto-accepted predictions and route them through the review flow, recording the resulting agreement rate. The sampled predictions SHALL be recorded. Audit sampling SHALL NOT change the accepted status of predictions outside the drawn sample.

#### Scenario: Audit sample is drawn randomly and recorded

- **GIVEN** a tenant with 500 auto-accepted predictions since the last audit
- **WHEN** an audit sample is drawn
- **THEN** the sampled predictions SHALL be selected randomly from that population
- **AND** the identities of the sampled predictions SHALL be recorded

#### Scenario: Audit agreement rate is recorded

- **GIVEN** an audit sample that has been fully reviewed
- **WHEN** the audit completes
- **THEN** the measured agreement rate SHALL be recorded with the sample size and the model version audited

#### Scenario: Audit sampling does not alter unsampled predictions

- **GIVEN** a tenant with 500 auto-accepted predictions and an audit sample of 20
- **WHEN** the audit completes with some sampled predictions found incorrect
- **THEN** the 480 unsampled predictions SHALL retain their accepted status
