## ADDED Requirements

### Requirement: Span Deselection

The workspace SHALL allow the user to deselect the currently selected span (close the span inspector) by clicking any document token that is not covered by a confirmed span, provided no entity type is currently armed.

#### Scenario: Clicking an unannotated token closes the span inspector

- **GIVEN** the span inspector is open for a confirmed span and no entity type is armed
- **WHEN** the user clicks a token that does not belong to any confirmed span
- **THEN** the span inspector SHALL close
- **AND** no span creation or modification request SHALL be sent

#### Scenario: Clicking unannotated token while armed does not deselect

- **GIVEN** an entity type is armed and the span inspector is open
- **WHEN** the user clicks an unannotated token
- **THEN** span creation SHALL proceed (armed behavior takes priority)
- **AND** the inspector SHALL remain open if the span creation fails

### Requirement: Task Display Name

The workspace SHALL display human-readable task labels instead of raw document ID fragments. Each annotation task SHALL be labeled "Task N" where N is its 1-based position in the currently visible task queue list (top of list = Task 1). The "Task N" label SHALL appear in both the task queue sidebar row and the workspace toolbar when a task is selected.

#### Scenario: Task queue shows Task N labels

- **GIVEN** the task queue is populated with three tasks (top to bottom)
- **WHEN** the task queue sidebar renders
- **THEN** the first row SHALL display "Task 1", the second "Task 2", the third "Task 3"
- **AND** raw document ID fragments (e.g. "doc-296fb9ac") SHALL NOT appear in the task row labels

#### Scenario: Toolbar shows Task N for the selected task

- **GIVEN** the user has selected the second task in the queue
- **WHEN** the workspace toolbar renders
- **THEN** the task label in the toolbar SHALL read "Task 2"

## MODIFIED Requirements

### Requirement: Layout and Navigation

The annotation workspace SHALL render at `/annotation` inside the authenticated app shell. The workspace SHALL support two layout modes: **3-pane** (default) with a fixed-width task queue on the left, a scrollable document viewer in the center, and a fixed-width entity palette on the right; and **focus mode** where the task queue is hidden, the entity palette becomes a floating `position: fixed` panel, and the workspace occupies the full browser viewport via the browser Fullscreen API. The selected layout mode SHALL be persisted to `localStorage` under the key `"ner-annotation-layout"`.

The focus mode control SHALL be a single toggle button labeled "Focus". When focus mode is inactive the button SHALL appear as an outline or secondary style; when active it SHALL appear filled/highlighted. Clicking the button SHALL toggle between 3-pane and focus mode. There SHALL NOT be separate "3-pane" and "Focus" buttons acting as a radio group.

When focus mode is entered, the workspace SHALL call `document.documentElement.requestFullscreen()`. If the Fullscreen API call is rejected (e.g. permission denied), the workspace SHALL fall back to CSS focus mode (queue hidden, palette floating) without crashing. When the browser exits fullscreen (e.g. via Escape or the browser's native fullscreen controls), the workspace SHALL detect the `fullscreenchange` event and revert `layoutMode` to `"3pane"`.

#### Scenario: Default layout renders three columns

- **GIVEN** an authenticated annotator navigates to `/annotation`
- **WHEN** the page mounts for the first time (no localStorage preference)
- **THEN** the workspace SHALL render with a task queue column, a document viewer column, and an entity palette column visible simultaneously
- **AND** the layout mode toggle SHALL show a single "Focus" button in its inactive state

#### Scenario: Focus toggle enters fullscreen and hides queue

- **GIVEN** the annotation workspace is in 3-pane mode
- **WHEN** the user clicks the "Focus" toggle button
- **THEN** the task queue column SHALL be hidden
- **AND** the entity palette SHALL render as a `position: fixed` panel at `top: 140px; right: 30px`
- **AND** the document viewer SHALL expand to fill the full available width
- **AND** `document.documentElement.requestFullscreen()` SHALL be called
- **AND** the layout preference SHALL be written to `localStorage`
- **AND** the "Focus" button SHALL render in its active/filled state

#### Scenario: Clicking Focus toggle again exits focus mode

- **GIVEN** the annotation workspace is in focus mode
- **WHEN** the user clicks the "Focus" toggle button again
- **THEN** the workspace SHALL return to 3-pane layout
- **AND** `document.exitFullscreen()` SHALL be called
- **AND** the "Focus" button SHALL render in its inactive state

#### Scenario: Browser-native fullscreen exit (Escape) syncs layout state

- **GIVEN** the workspace is in focus mode (fullscreen active)
- **WHEN** the user presses Escape to exit fullscreen via the browser's native behavior
- **THEN** the `fullscreenchange` event listener SHALL detect the exit
- **AND** `layoutMode` SHALL revert to `"3pane"` without requiring a button click
- **AND** the task queue and 3-pane layout SHALL restore automatically

#### Scenario: Fullscreen API rejection falls back gracefully

- **GIVEN** the browser blocks the Fullscreen API (e.g. iframe restriction)
- **WHEN** the user clicks the "Focus" toggle
- **THEN** the workspace SHALL still enter CSS focus mode (queue hidden, palette floating)
- **AND** no error SHALL be thrown or displayed to the user

#### Scenario: Layout preference is restored on reload

- **GIVEN** the user previously selected focus mode (stored in `localStorage`)
- **WHEN** the user navigates to `/annotation`
- **THEN** the workspace SHALL render in focus mode without requiring re-selection

### Requirement: Task Status Lifecycle

The workspace SHALL manage annotation task status transitions. When an annotator creates the first confirmed span on a task's document, the task SHALL automatically transition from `unannotated` to `in-progress` via `PATCH /annotation-tasks/{id}`. A "Mark Complete" button SHALL be visible in the workspace toolbar whenever a task is selected. When the document has no confirmed spans, the "Mark Complete" button SHALL be visually disabled but remain clearly visible as a button with a distinct border, background, and text — it SHALL NOT be invisible or blend into the toolbar background. A tooltip on the disabled button SHALL read "Add at least one confirmed span before completing". When at least one confirmed span exists, the button SHALL become enabled and styled with the primary action color. Clicking it SHALL attempt to transition the task to `completed` via `PATCH /annotation-tasks/{id}`. On successful completion, the next available task SHALL be auto-selected.

#### Scenario: First span creation triggers in-progress transition

- **GIVEN** an active task with status `unannotated` and no confirmed spans
- **WHEN** the user creates the first confirmed span
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the task row in the queue SHALL update its status badge to "in-progress"

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
