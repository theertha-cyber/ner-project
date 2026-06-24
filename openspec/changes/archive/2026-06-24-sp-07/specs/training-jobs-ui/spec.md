## ADDED Requirements

### Requirement: Training job list view

The portal SHALL display a paginated, filterable list of training jobs for the current tenant. The list SHALL show job cards with status badge (color-coded), submitted timestamp, entity type count, and an animated pulse indicator for running jobs. The list SHALL support status filter tabs: All, Pending Approval, Running, Completed, Failed. The status filter SHALL be reflected in the URL query string (`?status=`).

#### Scenario: List shows all jobs on load

- **GIVEN** a tenant_admin user with 10 training jobs across multiple statuses
- **WHEN** the user navigates to `/training-jobs`
- **THEN** the list SHALL display all 10 jobs with status badges, timestamps, and entity type counts
- **AND** the "All" filter tab SHALL be selected by default

#### Scenario: Filter tabs narrow the list

- **GIVEN** a tenant_admin user viewing the training jobs list
- **WHEN** the user clicks the "Running" filter tab
- **THEN** the URL SHALL update to `?status=running`
- **AND** only jobs with status "running" SHALL be displayed

#### Scenario: Running job shows animated pulse

- **GIVEN** a training job with status "running"
- **WHEN** the job card is rendered in the list
- **THEN** the status badge SHALL display an animated pulse indicator

### Requirement: Training job detail panel

The portal SHALL display a detail panel when a training job is selected from the list. The panel SHALL show: status timeline (derived from job status lifecycle), hyperparameter grid (learning_rate, num_epochs, batch_size, max_seq_length), evaluation metrics with horizontal bar charts (F1, precision, recall per entity type), dataset-to-job-to-model lineage strip, and an MLflow run deep link (opens in new tab).

#### Scenario: Select a job shows detail panel

- **GIVEN** a tenant_admin viewing the training jobs list
- **WHEN** the user clicks a job card
- **THEN** the detail panel SHALL open on the right side
- **AND** the panel SHALL show status timeline, hyperparameters, metrics (if completed), lineage strip, and MLflow link (if completed)

#### Scenario: Detail panel shows live progress for running job

- **GIVEN** a training job with status "running"
- **WHEN** the detail panel is open
- **THEN** the panel SHALL display `current_epoch` and `current_loss`
- **AND** the panel SHALL poll `GET /api/v1/training-jobs/{id}` every 5 seconds to update progress
- **AND** the polling SHALL stop when status transitions out of "running"

#### Scenario: Detail panel shows evaluation metrics for completed job

- **GIVEN** a training job with status "completed"
- **WHEN** the detail panel is open
- **THEN** the panel SHALL display final evaluation metrics: F1, precision, recall, and loss
- **AND** the metrics SHALL be rendered as horizontal bar charts with values

#### Scenario: Detail panel shows error for failed job

- **GIVEN** a training job with status "failed"
- **WHEN** the detail panel is open
- **THEN** the panel SHALL display the `error_message` in a styled error alert

#### Scenario: Cross-tenant job access returns 404

- **GIVEN** a training job owned by tenant A
- **WHEN** a user from tenant B navigates to a deep link for that job
- **THEN** the list SHALL show no matching job
- **AND** the detail panel SHALL show "Job not found"

### Requirement: Submit training job

The portal SHALL provide a slide-over form to submit a new training job. The form SHALL include fields: learning_rate (number input), num_epochs (range slider 1–50), batch_size (select: 4, 8, 16, 32), max_seq_length (select: 64, 128, 256). The form SHALL check the tenant's annotated entity count before submission and display a preflight status banner. On successful submission, the new job SHALL appear in the list as "pending_approval" without a full page reload.

#### Scenario: Submit form shows preflight check

- **GIVEN** a tenant_admin user with at least 500 annotated entities
- **WHEN** the user opens the "Submit Job" slide-over
- **THEN** the form SHALL display a banner: "812 confirmed spans · meets the 500-span minimum"

#### Scenario: Submit form warns on insufficient spans

- **GIVEN** a tenant_admin user with fewer than 500 annotated entities
- **WHEN** the user opens the "Submit Job" slide-over
- **THEN** the form SHALL display a warning banner: "X confirmed spans · requires 500 minimum"
- **AND** the submit button SHALL be disabled

#### Scenario: Submit a valid training job from the UI

- **GIVEN** a tenant with sufficient entities and valid hyperparameters entered
- **WHEN** the user clicks "Submit Training Job"
- **THEN** the system SHALL call `POST /api/v1/training-jobs` with the hyperparameters
- **AND** on 201 response, the new job SHALL appear in the list as "pending_approval"
- **AND** the slide-over SHALL close
- **AND** the new job card SHALL be highlighted briefly

#### Scenario: Submit with invalid hyperparameters shows error

- **GIVEN** a tenant with sufficient entities
- **WHEN** the user enters `num_epochs = -1` and clicks "Submit Training Job"
- **THEN** the form SHALL display a field-level validation error before making the API call

### Requirement: Cancel training job from UI

The portal SHALL allow a tenant_admin to cancel a training job in "pending_approval", "queued", or "running" status. The cancel action SHALL show a confirmation dialog before sending the request. System admins SHALL NOT see the cancel button.

#### Scenario: Cancel a pending job

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a tenant_admin clicks the "Cancel" button and confirms the dialog
- **THEN** the system SHALL call `POST /api/v1/training-jobs/{id}/cancel`
- **AND** the job status SHALL update to "cancelled" in the list

#### Scenario: Cancel dialog dismissed

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a tenant_admin clicks "Cancel" and then dismisses the confirmation dialog
- **THEN** no API call SHALL be made
- **AND** the job status SHALL remain unchanged

### Requirement: Approve/reject training job (system_admin)

The portal SHALL allow a system_admin to approve or reject training jobs in "pending_approval" status. Approve/reject buttons SHALL be visible only for system_admin users and only for jobs in "pending_approval" status. Rejection SHALL include an optional reason text input. On approval, the job transitions to "queued". On reject, the job transitions to "rejected".

#### Scenario: Approve a pending job as system_admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a system_admin clicks "Approve & queue"
- **THEN** the system SHALL call `POST /api/v1/training-jobs/{id}/approve?tenant_id={tid}`
- **AND** the job status SHALL update to "queued" in the list

#### Scenario: Reject a pending job as system_admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a system_admin clicks "Reject" and optionally enters a reason
- **THEN** the system SHALL call `POST /api/v1/training-jobs/{id}/reject?tenant_id={tid}` with the reason body
- **AND** the job status SHALL update to "rejected" in the list

#### Scenario: Approve/reject buttons hidden for non-pending jobs

- **GIVEN** a training job in "running" status
- **WHEN** a system_admin views the detail panel
- **THEN** the approve and reject buttons SHALL NOT be displayed

#### Scenario: Approve/reject buttons hidden for tenant_admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a tenant_admin views the detail panel
- **THEN** the approve and reject buttons SHALL NOT be displayed
