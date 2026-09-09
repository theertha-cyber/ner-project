## MODIFIED Requirements

### Requirement: Retraining Decision Surface

The system SHALL present the accumulation figure for the tenant's currently serving model
version, broken down per entity type AND per source (`manual`, `automated`, `import`),
together with the serving model version identifier. For a tenant with no trained model, the
system SHALL present that state distinctly rather than reporting an accumulation figure of
zero. The system SHALL present accumulation distinctly from dataset readiness.

The system SHALL additionally present a training-eligibility overview: for each source, the
number of training-eligible units that have not yet been consumed by a completed training
run, and the most recent eligibility timestamp for that source. A training-eligible unit is
a completed annotation task, an annotator-approved automated `large` batch, or an import
file with every entity type mapped. The overview SHALL remain a report — requesting it
SHALL NOT create, enqueue, approve, or promote anything.

#### Scenario: Decision surface shows accumulation against the serving version

- **GIVEN** a tenant serving model version 3 with 134 confirmed spans accumulated since version 3 was trained
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL report 134 spans accumulated
- **AND** the response SHALL identify model version 3 as the serving version

#### Scenario: Accumulation is broken down per entity type

- **GIVEN** a tenant with 134 accumulated spans comprising 120 of type `organization` and 14 of type `person_name`
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL report 120 for `organization` and 14 for `person_name`

#### Scenario: Accumulation is broken down per source

- **GIVEN** a tenant whose 134 accumulated spans comprise 90 from manual annotation, 30 from an accepted automated batch, and 14 from an imported file
- **WHEN** the retraining decision surface is requested
- **THEN** the response SHALL report `manual: 90`, `automated: 30`, `import: 14`

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

#### Scenario: Overview counts training-eligible units per source

- **GIVEN** a tenant with 2 completed annotation tasks, 1 annotator-approved automated `large` batch, and 3 fully-mapped import files, none yet consumed by a training run
- **WHEN** the retraining decision surface is requested
- **THEN** the overview SHALL report `manual: 2`, `automated: 1`, `import: 3`
- **AND** each SHALL carry the most recent eligibility timestamp for that source

#### Scenario: Consumed units drop off the overview

- **GIVEN** a tenant whose 2 completed annotation tasks were consumed by a training run that has since completed
- **WHEN** the retraining decision surface is requested
- **THEN** the overview SHALL report `manual: 0`

#### Scenario: The overview is a report only

- **GIVEN** a tenant with training-eligible units in every source
- **WHEN** the retraining decision surface is requested repeatedly
- **THEN** no training job SHALL be created
- **AND** no Celery task SHALL be enqueued
- **AND** the serving model version SHALL be unchanged
