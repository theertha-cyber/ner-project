# import-annotation-landing Specification

## Purpose
TBD - created by archiving change import-annotation-training-workflow. Update Purpose after archive.

## Requirements

### Requirement: Workflow Steps

For `tenant_admin`, the page SHALL render two "Your workflow" cards in a fixed order: "1. Import
annotations" (linking to `/imported-documents?import=1`, which SHALL open the file picker on
arrival) and "2. Train model" (linking to `/training-jobs?source=import`, the Import workflow's
own hand-off, so a run started from here trains only on imported data). Step 2 SHALL be shown
regardless of whether any file is yet training-eligible — imported data skips labeling and goes
straight to training-eligible once resolved, so there is no separate review step gating access
to training. For `annotator`, the page SHALL render exactly one "Where the work is" card,
"Imported files", linking to `/imported-documents` — an annotator does not import files or
train models, only reviews them, so neither workflow step SHALL be shown to that role.

#### Scenario: tenant_admin sees the two-step workflow in order

- **GIVEN** `/annotate/import` renders for a `tenant_admin`
- **WHEN** the "Your workflow" section is inspected
- **THEN** exactly two cards SHALL be present, in order: "1. Import annotations", "2. Train
  model"
- **AND** activating "1. Import annotations" SHALL navigate to `/imported-documents?import=1`
- **AND** activating "2. Train model" SHALL navigate to `/training-jobs?source=import`

#### Scenario: annotator sees only a single review card

- **GIVEN** `/annotate/import` renders for an `annotator`
- **WHEN** the work-card section is inspected
- **THEN** exactly one card SHALL be present, titled "Imported files"
- **AND** no "Import annotations" or "Train model" card SHALL be shown

#### Scenario: Train model is available with nothing imported yet

- **GIVEN** a `tenant_admin` with zero imported files
- **WHEN** `/annotate/import` renders
- **THEN** the "2. Train model" card SHALL still be shown, not hidden pending an eligible file
