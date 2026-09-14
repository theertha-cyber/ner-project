# manual-annotation-landing Specification

## Purpose

`manual-annotation-landing` covers the `/annotate/manual` page: the at-a-glance stats, the
"Where the work is" entry points, the list of already-annotated documents, and the hand-off
into model training. It is the first screen a Tenant Admin or Annotator sees when they choose
manual annotation over the automated or import flows.

## Requirements

### Requirement: At-a-Glance Stats

For `tenant_admin`, the page SHALL show three stats: documents ready (processed documents
available to annotate), annotated (count of completed annotation tasks tenant-wide), and
entity types defined. For `annotator`, the page SHALL show two stats: assigned to me, and
completed by me (count of the annotator's own completed annotation tasks).

#### Scenario: tenant_admin sees tenant-wide counts

- **GIVEN** an authenticated `tenant_admin` with 100 processed documents, 99 completed
  annotation tasks tenant-wide, and 0 entity types defined
- **WHEN** `/annotate/manual` renders
- **THEN** the stats SHALL read "100 documents ready", "99 annotated", "0 entity types defined"

#### Scenario: annotator sees their own completed count

- **GIVEN** an authenticated `annotator` with 3 of their own annotation tasks completed and 2
  more completed by other annotators on the same tenant
- **WHEN** `/annotate/manual` renders
- **THEN** the "completed by me" stat SHALL read 3, not 5

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

### Requirement: Annotated Documents List

The page SHALL render an "Annotated documents" list of every annotation task whose status is
`completed`, each row showing the document's filename and span count. For `annotator`, the
list SHALL be scoped to tasks assigned to the current user. For `tenant_admin`, the list
SHALL include completed tasks across the tenant. Each row SHALL offer a "View" action that
navigates to `/annotation?task={taskId}`, the existing read-only view of a completed task.
When there are no completed tasks, the page SHALL show an empty-state message instead of an
empty list.

#### Scenario: completed tasks are listed with a working view link

- **GIVEN** a completed annotation task with id `abc-123`, filename `Contract-NDA.pdf`, and
  15 confirmed spans
- **WHEN** `/annotate/manual` renders
- **THEN** the Annotated Documents list SHALL show a row "Contract-NDA.pdf" · 15 spans
- **AND** its "View" action SHALL navigate to `/annotation?task=abc-123`

#### Scenario: annotator sees only their own annotated documents

- **GIVEN** an `annotator` with 2 completed tasks of their own and 1 completed task assigned
  to a different annotator on the same tenant
- **WHEN** `/annotate/manual` renders
- **THEN** the Annotated Documents list SHALL contain exactly 2 rows

#### Scenario: empty state when nothing is annotated yet

- **GIVEN** the caller has zero completed annotation tasks
- **WHEN** `/annotate/manual` renders
- **THEN** the Annotated Documents section SHALL show an empty-state message
- **AND** SHALL NOT show a table with a header row and no data rows

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
