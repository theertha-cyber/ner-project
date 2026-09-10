## ADDED Requirements

### Requirement: Annotation Task Endpoint Role Gates

The annotation-task endpoints SHALL enforce roles in the backend, not only by hiding UI:

- `POST /api/v1/annotation-tasks` SHALL require the `tenant_admin` role.
- `GET /api/v1/annotation-tasks` SHALL require `tenant_admin` or `annotator`; a
  `business_user` SHALL receive 403.
- `PATCH /api/v1/annotation-tasks/{id}` SHALL require `tenant_admin` or `annotator`.

#### Scenario: An annotator cannot create a task

- **GIVEN** an authenticated user with role `annotator`
- **WHEN** they call `POST /api/v1/annotation-tasks`
- **THEN** the response SHALL be 403

#### Scenario: A business user cannot create or list tasks

- **GIVEN** an authenticated user with role `business_user`
- **WHEN** they call `POST /api/v1/annotation-tasks` or `GET /api/v1/annotation-tasks`
- **THEN** each response SHALL be 403

#### Scenario: A tenant admin can create a task

- **GIVEN** an authenticated `tenant_admin` and a processed training-purpose document
- **WHEN** they call `POST /api/v1/annotation-tasks` with a valid body
- **THEN** the response SHALL be 201

### Requirement: Task Completion Is Final Approval

When a task transitions to `completed` (from a non-`completed` state), the system SHALL
stamp `annotation_tasks.training_eligible_at`, and SHALL write a persistent notification for
the tenant addressed to `recipient_role = "tenant_admin"` with kind
`annotation_task_completed`, naming the document. There SHALL be no further Tenant Admin
annotation-review step; the response SHALL indicate `training_eligible: true`.

#### Scenario: Completing a task marks it training-eligible and notifies the tenant admin

- **GIVEN** a task in `in-progress` with at least one confirmed span
- **WHEN** an `annotator` PATCHes its status to `completed`
- **THEN** the response SHALL include `training_eligible: true`
- **AND** `annotation_tasks.training_eligible_at` SHALL be set
- **AND** a `public.notifications` row SHALL exist for that tenant with
  `recipient_role = "tenant_admin"` and kind `annotation_task_completed`

#### Scenario: Re-completing an already-completed task does not re-notify

- **GIVEN** a task already in `completed`
- **WHEN** its status is PATCHed to `completed` again
- **THEN** no second notification SHALL be written
- **AND** `training_eligible_at` SHALL be unchanged

#### Scenario: A completion has no Tenant Admin review step

- **GIVEN** a task an annotator has marked `completed`
- **WHEN** the Tenant Admin views the resulting notification and the task
- **THEN** the only available onward action SHALL be to request training — there SHALL be
  no "review annotations" action for the Tenant Admin
