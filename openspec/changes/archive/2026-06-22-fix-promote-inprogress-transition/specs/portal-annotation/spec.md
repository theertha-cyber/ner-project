## MODIFIED Requirements

### Requirement: Task Status Lifecycle

The workspace SHALL manage annotation task status transitions. When the first confirmed span is created on a task's document — whether by direct token click, drag selection, or suggestion promotion — the task SHALL automatically transition from `unannotated` to `in-progress` via `PATCH /annotation-tasks/{id}`. The in-progress transition SHALL be sent at most once per task per browser session (idempotency guard). A "Mark Complete" button SHALL be visible in the workspace toolbar whenever a task is selected. When the document has no confirmed spans, the "Mark Complete" button SHALL be visually disabled but remain clearly visible as a button with a distinct border, background, and text — it SHALL NOT be invisible or blend into the toolbar background. A tooltip on the disabled button SHALL read "Add at least one confirmed span before completing". When at least one confirmed span exists, the button SHALL become enabled and styled with the primary action color. Clicking it SHALL attempt to transition the task to `completed` via `PATCH /annotation-tasks/{id}`. On successful completion, the next available task SHALL be auto-selected.

#### Scenario: First span creation via token click triggers in-progress transition

- **GIVEN** an active task with status `unannotated` and no confirmed spans
- **WHEN** the user clicks a token while an entity type is armed, creating the first confirmed span
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the task row in the queue SHALL update its status badge to "in-progress"

#### Scenario: Promoting a suggestion triggers in-progress transition

- **GIVEN** an active task with status `unannotated` and no confirmed spans
- **WHEN** the user promotes a suggested span (clicking "Promote" in the suggestion panel)
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}` after the successful promote API call
- **AND** the task row in the queue SHALL update its status badge to "in-progress"

#### Scenario: In-progress transition fires only once per session

- **GIVEN** an active task with status `unannotated`
- **WHEN** the user promotes or creates multiple spans in the same browser session
- **THEN** the `PATCH /annotation-tasks/{id}` in-progress request SHALL be sent exactly once
- **AND** subsequent span creations or promotions SHALL NOT send additional in-progress PATCHes

#### Scenario: Mark Complete button is visible but disabled with no spans

- **GIVEN** an active task is selected and the document has zero confirmed spans
- **WHEN** the workspace toolbar renders
- **THEN** the "Mark Complete" button SHALL be visible in the toolbar
- **AND** the button SHALL be clearly distinguishable as a disabled button (distinct border and text, not transparent)
- **AND** a tooltip on hover SHALL read "Add at least one confirmed span before completing"

#### Scenario: Mark Complete becomes enabled when spans exist

- **GIVEN** an active task is selected and the document has at least one confirmed span
- **WHEN** the workspace toolbar renders
- **THEN** the "Mark Complete" button SHALL be enabled and styled with the primary action color
- **AND** clicking it SHALL send `PATCH /annotation-tasks/{id}` with `{status: "completed"}`

#### Scenario: Mark Complete transitions task to completed

- **GIVEN** an active task with status `in-progress` and at least one confirmed span
- **WHEN** the user clicks "Mark Complete"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** on success, the task status badge in the queue SHALL update to "completed"
- **AND** the next available (non-completed) task in the queue SHALL be auto-selected if one exists
