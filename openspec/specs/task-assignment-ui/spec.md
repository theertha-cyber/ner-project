# Task Assignment UI

## Purpose

Inline task assignment form within the annotation workspace, allowing `tenant_admin` users to assign annotation tasks to annotators directly from the Task Queue panel.

---

## Requirements

### Requirement: Task Assignment Form

The annotation workspace SHALL render a role-gated "＋ Assign Task" button at the top of the Task Queue panel. The button SHALL be visible only when the authenticated user's role is `tenant_admin`. Clicking the button SHALL expand an inline assignment form below the Task Queue header, within the same panel. The form SHALL contain:
- A **Document** dropdown populated by `GET /api/v1/documents`, filtered client-side to documents with `status: "processed"` only.
- An **Annotator** dropdown populated by `GET /api/v1/users`, filtered client-side to users with `role: "annotator"` only.
- A **Assign** submit button (disabled until both dropdowns have a selection).
- A **Cancel** link/button to collapse the form without submitting.

Both dropdowns SHALL be fetched only when the form is opened (lazy fetch). While either dropdown is loading, a loading indicator SHALL be shown in place of that dropdown. If both dropdowns return empty results, the form SHALL display a descriptive empty state message.

#### Scenario: Assign Task button visible for tenant admin

- **GIVEN** an authenticated user with role `tenant_admin` is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** a "＋ Assign Task" button SHALL be visible at the top of the Task Queue panel

#### Scenario: Assign Task button hidden for annotator

- **GIVEN** an authenticated user with role `annotator` is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** the "＋ Assign Task" button SHALL NOT be present in the DOM

#### Scenario: Clicking Assign Task button expands the inline form

- **GIVEN** the authenticated user is a tenant admin and the assignment form is currently collapsed
- **WHEN** the user clicks the "＋ Assign Task" button
- **THEN** an inline form SHALL expand below the Task Queue header within the left panel
- **AND** the Document dropdown and Annotator dropdown SHALL begin loading

#### Scenario: Document dropdown lists only processed documents

- **GIVEN** the assignment form is open and the tenant has 3 documents: one with status `processed`, one `pending`, one `failed`
- **WHEN** the Document dropdown renders
- **THEN** only the `processed` document SHALL appear as a selectable option
- **AND** the `pending` and `failed` documents SHALL NOT appear

#### Scenario: Annotator dropdown lists only annotator-role users

- **GIVEN** the assignment form is open and the tenant has users with roles `tenant_admin` (1), `annotator` (2), `business_user` (1)
- **WHEN** the Annotator dropdown renders
- **THEN** only the 2 annotator-role users SHALL appear as selectable options

#### Scenario: Assign button disabled until both fields are selected

- **GIVEN** the assignment form is open
- **WHEN** only one of Document or Annotator has been selected
- **THEN** the "Assign" submit button SHALL be disabled and non-interactive

#### Scenario: Successful task creation adds task to queue

- **GIVEN** the tenant admin has selected a document and an annotator in the assignment form
- **WHEN** the admin clicks "Assign"
- **THEN** a `POST /api/v1/annotation-tasks` request SHALL be sent with `{ document_id, annotator_user_id }`
- **AND** on a 201 response, the new task SHALL be prepended to the Task Queue list
- **AND** the assignment form SHALL collapse
- **AND** a success toast SHALL be shown

#### Scenario: Duplicate assignment (409) shows inline error

- **GIVEN** the tenant admin selects a document that already has an active (non-completed) task
- **WHEN** the admin clicks "Assign" and the backend returns a 409
- **THEN** the form SHALL remain open
- **AND** an inline error message SHALL appear within the form indicating the document already has an active task
- **AND** the Task Queue list SHALL NOT be updated

#### Scenario: Cancel collapses form without submitting

- **GIVEN** the assignment form is open with a document and annotator selected
- **WHEN** the user clicks "Cancel"
- **THEN** the form SHALL collapse
- **AND** no `POST /api/v1/annotation-tasks` request SHALL be sent

#### Scenario: Empty annotator list shows descriptive message

- **GIVEN** the assignment form is open and `GET /api/v1/users` returns no users with role `annotator`
- **WHEN** the Annotator dropdown renders
- **THEN** a message SHALL appear stating "No annotators available — invite users first"
- **AND** the Assign button SHALL remain disabled
