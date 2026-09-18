## ADDED Requirements

### Requirement: Submit slide-over source scope

The submit-job slide-over SHALL require exactly one training source — `manual`, `automated`, or `import` — before a job can be submitted, since Manual, Automated, and Import are independent workflows and a job never blends their data. When the slide-over is opened via a workflow's own "Train model" hand-off, its source SHALL be locked: shown as read-only text naming the workflow, with no choice to change it. When opened via the page's generic "+ Submit job" entry point, the slide-over SHALL instead present a required radio choice among the three workflows, and the submit action SHALL remain disabled until one is chosen. The slide-over's span preflight check SHALL query the annotation export scoped to whichever source is locked or chosen, and SHALL show a neutral placeholder instead of a span count while no source is yet chosen. Submitting SHALL send the effective source as `source_scope` in the request body.

The Training Jobs page SHALL recognize a `source` query parameter (`manual`, `automated`, or `import`) on arrival and SHALL auto-open the submit slide-over with that source locked. An unrecognized or absent `source` value SHALL leave the slide-over closed and, if later opened via "+ Submit job", requires the ordinary explicit choice.

#### Scenario: Locked source shows read-only text, not a picker

- **GIVEN** the Training Jobs page is reached via a link ending in `?source=automated`
- **WHEN** the submit slide-over opens
- **THEN** it SHALL show "Training source: Automated batches" as read-only text
- **AND** it SHALL NOT render a radio choice

#### Scenario: Generic entry point requires an explicit source choice

- **GIVEN** the Tenant Admin opens the submit slide-over via "+ Submit job" with no `source` in the URL
- **WHEN** the slide-over renders
- **THEN** it SHALL show a required radio choice among Manual annotation, Automated batches, and Imported annotations
- **AND** the submit button SHALL be disabled until one is selected

#### Scenario: Choosing a source unlocks the preflight check and submission

- **GIVEN** the slide-over is open with no source yet chosen
- **WHEN** the Tenant Admin selects "Automated batches"
- **THEN** the span preflight check SHALL fetch `/api/v1/annotation-export?source=automated`
- **AND** the submit button SHALL become enabled

#### Scenario: Submitting sends the effective source_scope

- **GIVEN** a source is locked or chosen
- **WHEN** the Tenant Admin submits the form
- **THEN** the request body SHALL include `source_scope` set to that source

#### Scenario: Arriving with a source query parameter auto-opens the slide-over

- **GIVEN** the Tenant Admin navigates to `/training-jobs?source=manual`
- **WHEN** the page loads
- **THEN** the submit slide-over SHALL open automatically with the source locked to "Manual annotation"
