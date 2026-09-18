## MODIFIED Requirements

### Requirement: Task Assignment Form

The annotation workspace SHALL render a role-gated "＋ Assign Task" button at the top of the Task Queue panel. The button SHALL be visible only when the authenticated user's role is `tenant_admin`. Clicking the button SHALL expand an inline assignment form below the Task Queue header, within the same panel. The form SHALL contain:
- A **Documents** checkbox list, populated by `GET /api/v1/documents`, filtered client-side to documents with `status: "processed"` only, supporting selection of more than one document at once. "Select all" and "Clear" controls SHALL be available above the list.
- An **Annotator** dropdown populated by `GET /api/v1/users`, filtered client-side to users with `role: "annotator"` only.
- An **Assign** submit button (disabled until at least one document and an annotator are selected).
- A **Cancel** link/button to collapse the form without submitting.

Both the document list and the annotator dropdown SHALL be fetched only when the form is opened (lazy fetch). While either is loading, a loading indicator SHALL be shown in its place. If both return empty results, the form SHALL display a descriptive empty state message.

Submitting the form SHALL create one task per selected document for the chosen annotator, sent as one `POST /api/v1/annotation-tasks` request per document — each document remains independently subject to the existing "one active task per document" conflict rule. When every request in the batch succeeds, the form SHALL close and every created task SHALL be prepended to the Task Queue in one update. When any request in the batch fails, the form SHALL remain open and show a per-document result (which succeeded, and why any others did not) instead of silently dropping the failures or closing over them; a "Done" action SHALL close the form at that point, prepending whichever tasks did succeed.

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
- **AND** the Documents list and Annotator dropdown SHALL begin loading

#### Scenario: Document dropdown lists only processed documents

- **GIVEN** the assignment form is open and the tenant has 3 documents: one with status `processed`, one `pending`, one `failed`
- **WHEN** the Documents list renders
- **THEN** only the `processed` document SHALL appear as a selectable checkbox
- **AND** the `pending` and `failed` documents SHALL NOT appear

#### Scenario: Annotator dropdown lists only annotator-role users

- **GIVEN** the assignment form is open and the tenant has users with roles `tenant_admin` (1), `annotator` (2), `business_user` (1)
- **WHEN** the Annotator dropdown renders
- **THEN** only the 2 annotator-role users SHALL appear as selectable options

#### Scenario: Assign button disabled until both fields are selected

- **GIVEN** the assignment form is open
- **WHEN** no document is checked, or no annotator is selected
- **THEN** the "Assign" submit button SHALL be disabled and non-interactive
- **AND** it SHALL become enabled once at least one document is checked and an annotator is selected, regardless of how many documents are checked

#### Scenario: Successful task creation adds task to queue

- **GIVEN** the tenant admin has selected one or more documents and an annotator in the assignment form
- **WHEN** the admin clicks "Assign"
- **THEN** one `POST /api/v1/annotation-tasks` request SHALL be sent per selected document, each with `{ document_id, annotator_user_id }`
- **AND** if every request returns 201, every new task SHALL be prepended to the Task Queue list
- **AND** the assignment form SHALL collapse
- **AND** a success toast SHALL be shown naming how many tasks were assigned

#### Scenario: Duplicate assignment (409) shows inline error

- **GIVEN** the tenant admin selects one or more documents, at least one of which already has an active (non-completed) task
- **WHEN** the admin clicks "Assign" and the backend returns 409 for that document
- **THEN** the form SHALL remain open
- **AND** a per-document result line SHALL appear for that document indicating it already has an active task
- **AND** the Task Queue SHALL NOT be updated with a task for that document

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

#### Scenario: Multiple documents can be selected and assigned together

- **GIVEN** the assignment form is open and the tenant has 5 processed documents
- **WHEN** the tenant admin checks 3 of them, selects an annotator, and clicks "Assign"
- **AND** all 3 requests succeed
- **THEN** 3 tasks SHALL be created, one per selected document, all for that annotator
- **AND** all 3 SHALL be prepended to the Task Queue in one update
- **AND** the form SHALL collapse

#### Scenario: Select all checks every visible processed document

- **GIVEN** the assignment form is open and the tenant has processed documents in the list
- **WHEN** the tenant admin clicks "Select all"
- **THEN** every processed document's checkbox SHALL become checked
- **AND** the selected count SHALL update to match

#### Scenario: A partially-failed batch shows per-document results and requires Done to close

- **GIVEN** the tenant admin selects 2 documents and an annotator, and one document's request
  returns 201 while the other returns 409
- **WHEN** the batch finishes submitting
- **THEN** the form SHALL remain open, showing a result line for each of the 2 documents
- **AND** the successfully created task SHALL NOT yet be prepended to the Task Queue
- **AND** clicking "Done" SHALL close the form and prepend the one task that succeeded
