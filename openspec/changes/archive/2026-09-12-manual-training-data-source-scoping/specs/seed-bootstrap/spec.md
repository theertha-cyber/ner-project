## MODIFIED Requirements

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
