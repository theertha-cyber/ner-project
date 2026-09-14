## MODIFIED Requirements

### Requirement: Annotation Mode Selector Visibility

The system SHALL render an annotation-mode selector with exactly two options, "Manual" and "Automated", within the document upload flow when `purpose` is `"training"`. The system SHALL NOT render the selector when `purpose` is `"query"`. The selector's initial selection SHALL be "Manual" unless the caller seeds a different initial selection (e.g. a deep link opened via the Automated flow's own upload entry point), and SHALL reset to "Manual" after a batch completes regardless of how it started — a mode that persisted across batches would silently send a later, unrelated batch through Automated by accident.

#### Scenario: Selector is shown for training uploads

- **GIVEN** the upload zone is rendered with `purpose: "training"`
- **WHEN** the page loads
- **THEN** an annotation-mode selector SHALL be visible with options "Manual" and "Automated"
- **AND** "Manual" SHALL be selected

#### Scenario: Selector is not shown for query uploads

- **GIVEN** the upload zone is rendered with `purpose: "query"`
- **WHEN** the page loads
- **THEN** no annotation-mode selector SHALL be rendered

#### Scenario: Selector resets to Manual after a batch completes

- **GIVEN** the user selected "Automated" and completed an upload batch
- **WHEN** the batch finishes and the upload zone returns to its idle state
- **THEN** the selector SHALL show "Manual" selected

#### Scenario: Selector seeds its initial selection from the caller

- **GIVEN** the upload zone is rendered with `purpose: "training"` and a seeded initial
  selection of "Automated"
- **WHEN** the page loads
- **THEN** the selector SHALL show "Automated" selected

#### Scenario: A seeded Automated selection still resets to Manual after a batch

- **GIVEN** the upload zone was seeded with an initial selection of "Automated" and the user
  completed an upload batch without changing it
- **WHEN** the batch finishes and the upload zone returns to its idle state
- **THEN** the selector SHALL show "Manual" selected
