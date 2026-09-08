## ADDED Requirements

### Requirement: Deep Link to a Specific Task

The annotation workspace SHALL accept an optional `task` query parameter at `/annotation?task=<taskId>`. When present and the identified task belongs to the current user's visible queue, the workspace SHALL pre-select that task on load — loading its document text and entity panel exactly as an in-app click on that queue row would.

When the parameter is absent, names a task that is not in the user's queue, or names a task that no longer exists, the workspace SHALL fall back to its default selection behaviour and SHALL NOT render an error state. The parameter SHALL affect initial selection only: selecting a different task afterwards SHALL NOT be overridden by the parameter, and the existing `localStorage` layout-mode persistence SHALL be unaffected.

#### Scenario: task parameter pre-selects the task

- **GIVEN** the annotator has a task `abc123` in their queue
- **WHEN** the user navigates to `/annotation?task=abc123`
- **THEN** task `abc123` is the selected task
- **AND** its document text is loaded in the viewer

#### Scenario: unknown task id falls back to default selection

- **GIVEN** no task `zzz999` exists in the annotator's queue
- **WHEN** the user navigates to `/annotation?task=zzz999`
- **THEN** the workspace renders its default selection
- **AND** no error state is shown

#### Scenario: task belonging to another annotator is not selected

- **GIVEN** task `other456` exists but is not in the current user's visible queue
- **WHEN** the user navigates to `/annotation?task=other456`
- **THEN** the workspace renders its default selection
- **AND** no content from task `other456` is displayed

#### Scenario: parameter does not override later selection

- **GIVEN** the user arrived at `/annotation?task=abc123` and task `abc123` is selected
- **WHEN** the user clicks a different task in the queue
- **THEN** the newly clicked task becomes the selected task
- **AND** the selection is not reverted to `abc123`

#### Scenario: no parameter preserves existing behaviour

- **GIVEN** the user navigates to `/annotation` with no query parameter
- **WHEN** the workspace loads
- **THEN** the default selection behaviour is unchanged
- **AND** the persisted layout mode from `localStorage` is applied as before
