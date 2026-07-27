## MODIFIED Requirements

### Requirement: Annotation Task Management

The system SHALL allow Tenant Admins to create annotation tasks that assign a document to a specific annotator. Each task SHALL track status through `unannotated` → `in-progress` → `completed`. A document SHALL have at most one active (non-completed) task at any time. Tasks SHALL be stored in the tenant's isolated schema. Annotation tasks SHALL only be creatable for documents whose `purpose` is `training`.

#### Scenario: Create an annotation task

- **GIVEN** a processed document with `purpose='training'` and an active annotator user
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with `{document_id: "doc-123", annotator_user_id: "user-456"}`
- **THEN** the response SHALL have status 201
- **AND** the task SHALL have `status: "unannotated"`

#### Scenario: Create task for already-assigned document returns 409

- **GIVEN** document "doc-123" already has an annotation task with status `in-progress`
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with `{document_id: "doc-123", annotator_user_id: "user-789"}`
- **THEN** the response SHALL have status 409
- **AND** the error SHALL indicate the document already has an active task

#### Scenario: List annotation tasks with status filter

- **GIVEN** 2 tasks with status `completed` and 1 with `unannotated`
- **WHEN** a Tenant Admin GETs `/api/v1/annotation-tasks?status=unannotated`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain only the unannotated task

#### Scenario: Update annotation task status

- **GIVEN** a task with ID "task-789" and status `unannotated`
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "in-progress"}`
- **THEN** the response SHALL have status 200
- **AND** the task status SHALL be `in-progress`

#### Scenario: Complete a task that has spans

- **GIVEN** a task with ID "task-789" in status `in-progress` and the document has at least one confirmed span
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "completed"}`
- **THEN** the response SHALL have status 200
- **AND** the task status SHALL be `completed`

#### Scenario: Complete a task with no spans returns 422

- **GIVEN** a task with ID "task-789" in status `in-progress` and the document has no confirmed spans
- **WHEN** an annotator PATCHes `/api/v1/annotation-tasks/task-789` with `{status: "completed"}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the document must have at least one span before completing

#### Scenario: Create task for a query-purpose document is rejected

- **GIVEN** a processed document with `purpose='query'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/annotation-tasks` with that document's `document_id` and a valid `annotator_user_id`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the document's purpose must be `training` to be assigned for annotation

#### Scenario: Document picker only lists training-purpose documents

- **GIVEN** a tenant with 2 processed documents with `purpose='training'` and 3 with `purpose='query'`
- **WHEN** the annotation task assignment form requests the document list
- **THEN** only the 2 `purpose='training'` documents SHALL be offered as assignable
