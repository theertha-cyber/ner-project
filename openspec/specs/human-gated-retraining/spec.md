# Human-Gated Retraining

## Purpose

The surface where accumulated review evidence meets the decision it informs, and the guarantee
that the decision stays with a person.

Change 5 made reviewed spans accumulate and reported how many had built up since the serving
model was trained. Nothing consumed that figure and nothing reset it. This capability closes both
halves. **A training run records what it consumed, at completion** — which is what makes the
figure a delta rather than a running total, and what makes it correct after the first retrain
instead of only before it. Recording at completion rather than at submission is the whole point:
a job rejected at approval, or one that fails, produced no model, and marking its spans as
consumed would zero the figure while leaving the tenant exactly where they started.

Two surfaces sit on top of that. The **retraining decision surface** reports the figure broken
down per entity type against the serving version, because a total says nothing about whether the
new evidence is concentrated in one type or spread across all of them, and that distinction
changes the answer. The **promotion decision surface** puts a completed version's metrics beside
the serving version's with the dataset size each was trained on, and says when those sizes differ
materially enough that the metrics are not directly comparable.

Neither surface produces a verdict, and neither starts anything. A retrain is *requested*, which
creates an ordinary training job in `pending_approval` that goes through the existing System
Admin approval flow unchanged and carries no hyperparameters. Promotion remains the existing
manual step.

The prohibition is stated as a requirement rather than a design note because it was a decision
already made once and reversed: no accumulation value, threshold crossing, schedule, or completed
run may create, enqueue, or schedule a training job, or promote a model version. Accumulation is
also not dataset readiness — ADR-010 owns that, per entity type, answering a different question —
and the two are deliberately presented apart.

---

## Requirements

### Requirement: Training Runs Record Consumed Spans

The system SHALL record the set of confirmed spans consumed by a training run, associated with the model version that run produced, at the point the run completes successfully. The system SHALL NOT record consumed spans for a training job that is rejected at approval, that fails, or that has not yet completed. Accumulation reporting SHALL be computed against the recorded set for the currently serving model version.

#### Scenario: A completed run records the spans it consumed

- **GIVEN** a training run over a dataset built from 300 confirmed spans
- **WHEN** the run completes successfully and produces model version 4
- **THEN** those 300 spans SHALL be recorded as consumed by model version 4

#### Scenario: Accumulation resets after a completed run

- **GIVEN** a tenant serving model version 3 with an accumulation figure of 134 spans
- **WHEN** a training run consuming those spans completes and version 4 becomes the serving version
- **THEN** the accumulation figure against version 4 SHALL be 0

#### Scenario: A rejected job records nothing

- **GIVEN** a tenant with an accumulation figure of 134 spans and a training job in `pending_approval`
- **WHEN** a System Admin rejects that job
- **THEN** no spans SHALL be recorded as consumed
- **AND** the accumulation figure SHALL remain 134

#### Scenario: A failed run records nothing

- **GIVEN** a tenant with an accumulation figure of 134 spans and an approved training job
- **WHEN** the run fails
- **THEN** no spans SHALL be recorded as consumed
- **AND** the accumulation figure SHALL remain 134

#### Scenario: Accumulation is unchanged while a run is in flight

- **GIVEN** a tenant with an accumulation figure of 134 spans and an approved training job that is running
- **WHEN** the accumulation figure is requested before the run completes
- **THEN** the figure SHALL still be 134

### Requirement: Retraining Decision Surface

The system SHALL present the accumulation figure for the tenant's currently serving model version, broken down per entity type, together with the serving model version identifier. For a tenant with no trained model, the system SHALL present that state distinctly rather than reporting an accumulation figure of zero. The system SHALL present accumulation distinctly from dataset readiness.

#### Scenario: Decision surface shows accumulation against the serving version

- **GIVEN** a tenant serving model version 3 with 134 confirmed spans accumulated since version 3 was trained
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL report 134 spans accumulated
- **AND** the response SHALL identify model version 3 as the serving version

#### Scenario: Accumulation is broken down per entity type

- **GIVEN** a tenant with 134 accumulated spans comprising 120 of type `organization` and 14 of type `person_name`
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL report 120 for `organization` and 14 for `person_name`

#### Scenario: A tenant with no trained model is shown distinctly

- **GIVEN** a tenant with no trained model, served by the base model
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL indicate that no trained model exists
- **AND** the response SHALL NOT report an accumulation figure of zero against a model version

#### Scenario: Accumulation is not presented as readiness

- **GIVEN** a tenant whose retraining decision surface reports an accumulation figure
- **WHEN** the surface is inspected
- **THEN** the accumulation figure SHALL be labelled distinctly from dataset readiness
- **AND** the accumulation figure SHALL NOT be compared against the per-entity-type dataset readiness threshold

### Requirement: Manual Retrain Request

The system SHALL allow a retrain to be requested from the retraining decision surface. A retrain request SHALL create an ordinary training job that enters the `pending_approval` state and is approved or rejected through the existing training approval flow. A retrain request SHALL NOT carry or set training hyperparameters, SHALL NOT enqueue the job directly, and SHALL NOT bypass approval.

#### Scenario: A retrain request creates a job pending approval

- **GIVEN** a tenant serving model version 3 with accumulated spans
- **WHEN** a retrain is requested
- **THEN** a training job SHALL be created with status `pending_approval`
- **AND** no Celery task SHALL be enqueued at request time

#### Scenario: A requested retrain follows the existing approval flow

- **GIVEN** a training job created by a retrain request in `pending_approval`
- **WHEN** a System Admin approves it
- **THEN** the job SHALL transition to `queued`
- **AND** a Celery task SHALL be enqueued

#### Scenario: A requested retrain can be rejected like any other job

- **GIVEN** a training job created by a retrain request in `pending_approval`
- **WHEN** a System Admin rejects it with a reason
- **THEN** the job status SHALL be `rejected`
- **AND** the rejection reason SHALL be recorded

#### Scenario: A retrain request does not set hyperparameters

- **GIVEN** a retrain request submitted from the decision surface
- **WHEN** the resulting training job is inspected before approval
- **THEN** the job SHALL NOT carry hyperparameters supplied by the requester
- **AND** hyperparameters SHALL be set at approval time

### Requirement: No Automatic Retraining Or Promotion

The system SHALL NOT create, enqueue, or schedule a training job as a consequence of an accumulation figure reaching any value, of a threshold being crossed, of a schedule elapsing, or of another training run completing. The system SHALL NOT promote a model version automatically. Every training job and every promotion SHALL originate from an explicit human action.

#### Scenario: Accumulation reaching a large value creates no job

- **GIVEN** a tenant whose accumulation figure grows to 5000 spans
- **WHEN** the figure is updated
- **THEN** no training job SHALL be created, enqueued, or scheduled

#### Scenario: A completed run does not chain another run

- **GIVEN** a training run that completes successfully
- **WHEN** the completion is processed
- **THEN** no further training job SHALL be created, enqueued, or scheduled

#### Scenario: A completed run does not promote itself

- **GIVEN** a training run that completes successfully and produces model version 4
- **WHEN** the completion is processed
- **THEN** version 4 SHALL have status `completed`
- **AND** version 4 SHALL NOT be promoted
- **AND** the previously promoted version SHALL remain the serving version

#### Scenario: Promotion still requires an explicit human action

- **GIVEN** a model version with status `completed`
- **WHEN** no user has promoted it
- **THEN** it SHALL NOT become the serving version
- **AND** it SHALL remain in `completed` status indefinitely

### Requirement: Promotion Decision Evidence

The system SHALL present, for a model version with status `completed`, that version's evaluation metrics alongside the currently promoted version's metrics, together with the number of confirmed spans each was trained on. Where the two runs were trained on materially different dataset sizes, the system SHALL indicate that fact rather than presenting the metrics as directly comparable. The system SHALL NOT compute or present a verdict about which version is better.

#### Scenario: Candidate and current metrics are presented together

- **GIVEN** model version 3 promoted and model version 4 completed
- **WHEN** the promotion decision surface is requested for version 4
- **THEN** the response SHALL include version 4's evaluation metrics
- **AND** the response SHALL include version 3's evaluation metrics
- **AND** the response SHALL include the confirmed span count each was trained on

#### Scenario: Materially different dataset sizes are flagged

- **GIVEN** version 3 trained on 300 confirmed spans and version 4 trained on 1200
- **WHEN** the promotion decision surface is requested for version 4
- **THEN** the response SHALL indicate that the two runs were trained on materially different dataset sizes

#### Scenario: No better-or-worse verdict is produced

- **GIVEN** version 4 with higher evaluation metrics than promoted version 3
- **WHEN** the promotion decision surface is requested for version 4
- **THEN** the response SHALL NOT state that version 4 is better than version 3
- **AND** the response SHALL NOT recommend promotion

#### Scenario: No currently promoted version to compare against

- **GIVEN** a tenant with model version 1 completed and no previously promoted version
- **WHEN** the promotion decision surface is requested for version 1
- **THEN** the response SHALL include version 1's metrics
- **AND** the response SHALL indicate that there is no promoted version to compare against
