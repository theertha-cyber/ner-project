## MODIFIED Requirements

### Requirement: Annotation Task Queue

The workspace SHALL display a list of annotation tasks from `GET /api/v1/annotation-tasks` in the left queue panel (visible in 3-pane mode). For `annotator` users the list SHALL show only tasks assigned to the current user. For `tenant_admin` users the list SHALL show all tasks for the tenant.

Each task row SHALL display:
- Primary label: the document filename (e.g. `"invoice-2026-00417.pdf"`) in JetBrains Mono
- Subtitle: `"<document_status> · <span_count> spans"` (e.g. `"processed · 12 spans"`) in small secondary text

The active (selected) task row SHALL be highlighted with a left border in the primary color and a soft primary-tinted background. Selecting a task SHALL load that document into the document viewer and reset span state.

For `tenant_admin` users, the Task Queue panel header area SHALL include a "＋ Assign Task" button above the task list. Clicking this button SHALL open the inline task assignment form (see task-assignment-ui spec). The button SHALL NOT be rendered for `annotator` role users.

#### Scenario: Task row shows filename and document metadata

- **GIVEN** the task queue is populated and the active document is named "invoice-2026-00417.pdf" with status "processed" and 12 confirmed spans
- **WHEN** the task queue panel renders
- **THEN** the task row primary label SHALL read "invoice-2026-00417.pdf"
- **AND** the subtitle SHALL read "processed · 12 spans"

#### Scenario: Active task row is highlighted

- **GIVEN** the user has selected the first task in the queue
- **WHEN** the task queue renders
- **THEN** the selected row SHALL show a left border in `var(--color-primary)` and a soft primary-tinted background
- **AND** the other rows SHALL have no border or tinted background

#### Scenario: Annotator sees only assigned tasks

- **GIVEN** an authenticated annotator user with two assigned tasks and three tasks assigned to other users
- **WHEN** the annotation workspace loads
- **THEN** the queue SHALL show exactly two task rows

#### Scenario: Selecting a task loads the document

- **GIVEN** the task queue is populated with at least two tasks
- **WHEN** the user clicks the second task row
- **THEN** the document viewer SHALL load the text for that task's document via `GET /documents/{id}/text`
- **AND** confirmed spans SHALL be fetched via `GET /documents/{id}/spans`
- **AND** suggested spans SHALL be fetched via `GET /documents/{id}/spans?type=suggested`

#### Scenario: Empty queue shows contextual message

- **GIVEN** there are no annotation tasks for the current user
- **WHEN** the annotation workspace loads
- **THEN** the queue panel SHALL display "No tasks assigned" with a prompt to contact a tenant admin

#### Scenario: Tenant admin sees Assign Task button

- **GIVEN** an authenticated `tenant_admin` user is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** a "＋ Assign Task" button SHALL appear above the task list in the Task Queue panel

#### Scenario: Annotator does not see Assign Task button

- **GIVEN** an authenticated `annotator` user is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** the "＋ Assign Task" button SHALL NOT appear in the Task Queue panel
