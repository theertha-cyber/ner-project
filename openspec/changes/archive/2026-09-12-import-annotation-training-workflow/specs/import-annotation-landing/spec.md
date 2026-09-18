## ADDED Requirements

### Requirement: Workflow Steps

For `tenant_admin`, the page SHALL render two "Your workflow" cards in a fixed order: "1. Import
file" (linking to `/imported-documents?import=1`, which SHALL open the file picker on arrival)
and "2. Review imported files" (linking to `/imported-documents`). For `annotator`, the page
SHALL render exactly one "Where the work is" card, "Imported files", linking to
`/imported-documents` — an annotator does not import files, only reviews them, so the "Import
file" step SHALL NOT be shown to that role.

#### Scenario: tenant_admin sees the two-step workflow in order

- **GIVEN** `/annotate/import` renders for a `tenant_admin`
- **WHEN** the "Your workflow" section is inspected
- **THEN** exactly two cards SHALL be present, in order: "1. Import file", "2. Review imported
  files"
- **AND** activating "1. Import file" SHALL navigate to `/imported-documents?import=1`
- **AND** activating "2. Review imported files" SHALL navigate to `/imported-documents`

#### Scenario: annotator sees only a single review card

- **GIVEN** `/annotate/import` renders for an `annotator`
- **WHEN** the work-card section is inspected
- **THEN** exactly one card SHALL be present, titled "Imported files"
- **AND** no "Import file" card SHALL be shown

### Requirement: Train Model Hand-off

For `tenant_admin` only, once at least one imported file is training-eligible, the page SHALL
show a "Train model" call-to-action stating how many files are training-eligible, which
navigates to `/training-jobs?source=import` when activated — the Import workflow's own
hand-off, distinct from Manual's and Automated's, so a training run started from here trains
only on imported data. The action SHALL NOT be rendered when zero files are training-eligible,
and SHALL NOT be rendered for `annotator`.

#### Scenario: CTA appears once training-eligible files exist

- **GIVEN** a `tenant_admin` with 2 training-eligible imported files
- **WHEN** `/annotate/import` renders
- **THEN** a "Train model" action SHALL be visible naming the training-eligible count
- **AND** activating it SHALL navigate to `/training-jobs?source=import`

#### Scenario: CTA is absent with nothing training-eligible

- **GIVEN** a `tenant_admin` with 0 training-eligible imported files
- **WHEN** `/annotate/import` renders
- **THEN** no "Train model" action SHALL be rendered

#### Scenario: CTA is never shown to an annotator

- **GIVEN** an authenticated `annotator`, even where training-eligible imported files exist
- **WHEN** `/annotate/import` renders
- **THEN** no "Train model" action SHALL be rendered
