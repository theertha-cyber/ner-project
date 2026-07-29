## MODIFIED Requirements

### Requirement: Annotation Toolbar

The workspace toolbar SHALL render at the top of the annotation workspace with the following elements from left to right: (1) the active document filename displayed in `JetBrains Mono` with a task status badge adjacent to it; (2) a flex spacer; (3) a span counter showing "N confirmed · N suggested" in `JetBrains Mono`; (4) a "✦ Pre-label" button; (5) the 3-pane/Focus view-mode radio group. The toolbar SHALL NOT render a status button group or any other control that lets the user select a task status.

The task status badge SHALL be read-only. It SHALL display `pending` for `unannotated`, `in_progress` for `in-progress`, and `completed` for `completed`, using the existing badge colors.

The span counter SHALL update in real time as spans are created, promoted, or deleted. It SHALL read confirmed span count from client state and suggested span count from client state.

#### Scenario: Toolbar renders all elements for an active task

- **GIVEN** a task is selected with document filename "invoice-2026-00417.pdf", status "in-progress", 3 confirmed spans, and 2 suggested spans
- **WHEN** the annotation toolbar renders
- **THEN** the toolbar SHALL show the filename "invoice-2026-00417.pdf" in JetBrains Mono with a status badge reading "in_progress"
- **AND** the span counter SHALL read "3 confirmed · 2 suggested"
- **AND** the "✦ Pre-label" button and the 3-pane/Focus toggle SHALL be visible

#### Scenario: Toolbar exposes no status selection control

- **GIVEN** a task is selected with any status
- **WHEN** the annotation toolbar renders
- **THEN** no status button group SHALL be present in the toolbar
- **AND** no element in the toolbar SHALL issue a `PATCH /api/v1/annotation-tasks/{id}` request

#### Scenario: Badge reflects completed status without offering a transition

- **GIVEN** a task whose status is `completed`
- **WHEN** the annotation toolbar renders
- **THEN** the status badge SHALL read "completed"
- **AND** there SHALL be no control in the toolbar that transitions the task to "in_progress"

### Requirement: Task Status Lifecycle

Selecting a task in the annotation workspace SHALL open it in the `in-progress` state. When a task with status `unannotated` is selected, the workspace SHALL send `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}`, at most once per task per browser session (idempotency guard). Tasks already in `in-progress` or `completed` SHALL NOT trigger a status request on selection.

The `completed` state SHALL be terminal in the UI. The workspace SHALL NOT provide any control that transitions a task out of `completed`. A completed task SHALL remain viewable, and — while span editing is permitted — editable, with further edits re-submitted through the "Mark as Completed" action (see Annotation Action Bar requirement).

Span creation, drag selection, and suggestion promotion SHALL NOT send status transition requests, since the transition now happens on task open.

#### Scenario: Opening an unannotated task promotes it to in-progress

- **GIVEN** a task with status `unannotated`
- **WHEN** the user selects that task in the task queue
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the status badge in the toolbar SHALL read "in_progress"

#### Scenario: In-progress transition fires only once per session

- **GIVEN** a task with status `unannotated`
- **WHEN** the user selects the task, switches to another task, and selects it again in the same browser session
- **THEN** the `PATCH` in-progress request SHALL be sent exactly once

#### Scenario: Opening a completed task sends no status request

- **GIVEN** a task with status `completed`
- **WHEN** the user selects that task in the task queue
- **THEN** no `PATCH /annotation-tasks/{id}` request SHALL be sent
- **AND** the status badge SHALL read "completed"
- **AND** the document and its confirmed spans SHALL render normally

#### Scenario: Creating a span does not send a status request

- **GIVEN** an active task already in status `in-progress`
- **WHEN** the user creates a confirmed span via token click, drag, or suggestion promotion
- **THEN** the span request SHALL be sent
- **AND** no `PATCH /annotation-tasks/{id}` status request SHALL accompany it

## ADDED Requirements

### Requirement: Annotation Action Bar

The annotation workspace SHALL render an action bar pinned to the bottom of the workspace, spanning the full width below the document and side panels. The action bar SHALL contain a save/status indicator on the left and a primary "Mark as Completed" button on the right.

The save indicator SHALL communicate that span edits persist automatically (e.g. "All changes saved" once the last span request has settled, "Saving…" while a span request is in flight).

Clicking "Mark as Completed" SHALL wait for any in-flight span request to settle, then send `PATCH /api/v1/annotation-tasks/{id}` with `{status: "completed"}`. While the request is in flight the button SHALL be disabled and show a pending label. On success (200) the status badge SHALL read "completed", the task queue row SHALL reflect the new status, and a success toast SHALL be shown. On a 4xx or 5xx response the task status SHALL be left unchanged and a toast SHALL display the error message from the response body.

The button SHALL be rendered and enabled for a `completed` task as well, so that later edits can be re-submitted; re-completing an already `completed` task SHALL succeed without error.

When no task is selected the action bar SHALL render with the "Mark as Completed" button disabled.

#### Scenario: Action bar renders at the bottom of the workspace

- **GIVEN** a task is selected
- **WHEN** the annotation workspace renders
- **THEN** an action bar SHALL be present at the bottom of the workspace
- **AND** it SHALL contain a save indicator and a "Mark as Completed" button

#### Scenario: Mark as Completed completes the task

- **GIVEN** an active task with status `in-progress` and at least one confirmed span
- **WHEN** the user clicks "Mark as Completed"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the button SHALL be disabled while the request is in flight
- **AND** on success (200) the toolbar status badge SHALL read "completed"
- **AND** a success toast SHALL be shown

#### Scenario: Completing with no spans surfaces the error and keeps the task in-progress

- **GIVEN** an active task with status `in-progress` and zero confirmed spans
- **WHEN** the user clicks "Mark as Completed"
- **THEN** the API SHALL return 422
- **AND** the status badge SHALL still read "in_progress"
- **AND** a toast SHALL display the error message from the API response
- **AND** the "Mark as Completed" button SHALL become enabled again

#### Scenario: Re-completing an already completed task saves further edits

- **GIVEN** a task with status `completed` that the user has re-opened and edited
- **WHEN** the user clicks "Mark as Completed"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the response SHALL have status 200
- **AND** no "Cannot transition" error SHALL be shown

#### Scenario: Action bar disabled with no task selected

- **GIVEN** no task is selected in the task queue
- **WHEN** the annotation workspace renders
- **THEN** the "Mark as Completed" button SHALL be disabled
- **AND** clicking it SHALL send no request
