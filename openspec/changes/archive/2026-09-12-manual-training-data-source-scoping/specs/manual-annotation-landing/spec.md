## RENAMED Requirements

- FROM: `### Requirement: Single Work Card`
- TO: `### Requirement: Workflow Steps`

## MODIFIED Requirements

### Requirement: Workflow Steps

For `tenant_admin`, the page SHALL render three "Your workflow" cards in a fixed order, naming the
steps a new tenant admin takes before they can annotate anything: "1. Upload documents" (linking
to `/documents?upload=1`, which SHALL auto-open the upload dialog on arrival), "2. Define entity
types" (linking to `/entity-types`), and "3. Annotation workspace" (linking to `/annotation`). For
`annotator`, the page SHALL render exactly one "Where the work is" card, "Annotation workspace",
linking to `/annotation` — an annotator does not upload documents or define entity types, so
those two steps SHALL NOT be shown to that role. The page SHALL NOT render a "Review queue" card
or any other work card for either role.

#### Scenario: only the workspace card is shown

- **GIVEN** `/annotate/manual` renders for an `annotator` — the one role that neither uploads
  documents nor defines entity types
- **WHEN** the "Where the work is" section is inspected
- **THEN** exactly one card SHALL be present, titled "Annotation workspace"
- **AND** no "Upload documents" or "Define entity types" card SHALL be shown

#### Scenario: tenant_admin sees the three-step workflow in order

- **GIVEN** `/annotate/manual` renders for a `tenant_admin`
- **WHEN** the "Your workflow" section is inspected
- **THEN** exactly three cards SHALL be present, in order: "1. Upload documents", "2. Define
  entity types", "3. Annotation workspace"
- **AND** activating "1. Upload documents" SHALL navigate to `/documents?upload=1`
- **AND** activating "2. Define entity types" SHALL navigate to `/entity-types`
- **AND** activating "3. Annotation workspace" SHALL navigate to `/annotation`

### Requirement: Train Model Hand-off

For `tenant_admin` only, once at least one annotation task is completed, the page SHALL show
a "Train model" call-to-action stating how many documents are annotated and ready, which
navigates to `/training-jobs?source=manual` when activated — the Manual workflow's own hand-off,
distinct from the Automated flow's hand-off, so a training run started from here trains only on
manually-confirmed spans. The action SHALL NOT be rendered when zero tasks are completed, and
SHALL NOT be rendered for `annotator`.

#### Scenario: CTA appears once training material exists

- **GIVEN** a `tenant_admin` with 99 completed annotation tasks tenant-wide
- **WHEN** `/annotate/manual` renders
- **THEN** a "Train model" action SHALL be visible reading "99 documents annotated and ready
  for training"
- **AND** activating it SHALL navigate to `/training-jobs?source=manual`

#### Scenario: CTA is absent with nothing annotated

- **GIVEN** a `tenant_admin` with 0 completed annotation tasks tenant-wide
- **WHEN** `/annotate/manual` renders
- **THEN** no "Train model" action SHALL be rendered

#### Scenario: CTA is never shown to an annotator

- **GIVEN** an authenticated `annotator` with completed tasks of their own
- **WHEN** `/annotate/manual` renders
- **THEN** no "Train model" action SHALL be rendered, regardless of completed count
