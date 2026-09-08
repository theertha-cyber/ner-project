## MODIFIED Requirements

### Requirement: Submit slide-over visual parity without behavior change

The `SubmitJobSlideover` component SHALL be a lightweight training-request action for Tenant Admins: it SHALL retain the live annotated-span-count preflight display (informational only) but SHALL NOT render `learning_rate`, epoch, batch-size, or max-sequence-length inputs. Submitting the form SHALL POST a hyperparameter-free body to `/api/v1/training-jobs`.

#### Scenario: Slide-over still performs span preflight check, with no hyperparameter fields

- **GIVEN** a Tenant Admin opens the submit slide-over
- **WHEN** the slide-over mounts
- **THEN** it still fetches and displays the confirmed annotated span count exactly as before
- **AND** no learning-rate input, epoch slider, batch-size selector, or max-sequence-length selector is rendered
- **AND** the Submit button is enabled based only on submission-in-flight state

### Requirement: Job list card content

The `JobCard` component SHALL display, for each job: a status-colored dot (sourced from the same status-color mapping `Badge` uses) to the left of the job ID, pulsing only when `status === "running"`; the job ID in `font-mono`; a status pill (via `Badge`); and the job's F1 score (read from `metrics.eval_f1`) formatted to two decimal places, or `"—"` when no F1 score is available. When `hyperparams` is non-null, the card SHALL show a hyperparameter summary line formatted as `lr {learning_rate} · {num_epochs}ep · bs {batch_size}`. When `hyperparams` is `null` (a `pending_approval` job awaiting System Admin approval), the card SHALL show `"awaiting hyperparameters"` (or equivalent placeholder text) in place of the summary line, rather than rendering `undefined`/`null` values. Per the mockup, the card SHALL NOT show a separate creation-date line.

#### Scenario: Running job card shows full summary

- **GIVEN** a training job `{id: "tj_9f2a", status: "running", hyperparams: {learning_rate: 2e-5, num_epochs: 3, batch_size: 8}, metrics: null}`
- **WHEN** its `JobCard` renders
- **THEN** the card shows the job ID "tj_9f2a" in monospace
- **AND** a pulsing status-colored dot is visible
- **AND** the hyperparameter line reads "lr 0.00002 · 3ep · bs 8"
- **AND** the F1 value reads "—"

#### Scenario: Completed job card shows F1 score

- **GIVEN** a training job `{id: "tj_7c04", status: "completed", metrics: {eval_f1: 0.90}}`
- **WHEN** its `JobCard` renders
- **THEN** the F1 value reads "0.90"
- **AND** the status dot is visible but not pulsing

#### Scenario: Non-running job still shows a status-colored dot

- **GIVEN** a training job with status "pending_approval"
- **WHEN** its `JobCard` renders
- **THEN** a dot colored per the "pending_approval" status is visible
- **AND** it does not pulse

#### Scenario: Pending-approval job with no hyperparameters yet shows a placeholder, not undefined

- **GIVEN** a training job `{id: "tj_new1", status: "pending_approval", hyperparams: null}`
- **WHEN** its `JobCard` renders
- **THEN** the card shows "awaiting hyperparameters" (or equivalent) instead of a hyperparameter summary line
- **AND** no literal "undefined" or "null" text is rendered

### Requirement: Hyperparameters render as a single 4-column row

The hyperparameters section SHALL lay its four values (learning rate, epochs, batch size, max sequence length) out in a single row of four equal-width columns, matching the mockup's `grid-template-columns:1fr 1fr 1fr 1fr`, not a 2×2 grid. When the job's `hyperparams` is `null` (still `pending_approval`), the section SHALL render a placeholder state (e.g. "Hyperparameters not yet set — awaiting System Admin approval") instead of four empty/undefined values.

#### Scenario: Hyperparameters grid has 4 columns

- **GIVEN** a training job with hyperparams set
- **WHEN** the detail panel renders the hyperparameters section
- **THEN** its grid container has 4 columns, not 2

#### Scenario: Detail panel shows a placeholder when hyperparameters are not yet set

- **GIVEN** a training job `{status: "pending_approval", hyperparams: null}`
- **WHEN** the detail panel renders the hyperparameters section
- **THEN** a placeholder message is shown instead of four empty/undefined values

## ADDED Requirements

### Requirement: System Admin approval form collects hyperparameters

The Training Queue's approve action, when performed by a System Admin on a `pending_approval` job, SHALL open a form (dialog or inline) collecting `learning_rate`, `num_epochs` (range 1-50), `batch_size` (from the existing option set `[4, 8, 16, 32]`), and `max_seq_length` (from the existing option set `[64, 128, 256]`). The approve submission SHALL be disabled until all four fields hold valid values per those constraints. On submit, the form SHALL POST the entered values as the body of `/api/v1/training-jobs/{job_id}/approve`. A validation error returned by the backend SHALL be displayed on the form, which SHALL remain open with the entered values intact.

#### Scenario: Approve action opens a hyperparameter form

- **GIVEN** a System Admin views a training job in "pending_approval" status
- **WHEN** the System Admin clicks the approve action
- **THEN** a form appears with inputs for learning rate, epochs, batch size, and max sequence length
- **AND** no job is approved yet until the form is submitted

#### Scenario: Approve submit is disabled until all fields are valid

- **GIVEN** the System Admin has opened the approval form
- **WHEN** one or more of the four hyperparameter fields is empty or out of its valid range
- **THEN** the form's submit control SHALL be disabled

#### Scenario: Approve form submits entered hyperparameters

- **GIVEN** the System Admin has filled in all four hyperparameter fields with valid values
- **WHEN** the System Admin submits the form
- **THEN** the client SHALL POST those exact values to `/api/v1/training-jobs/{job_id}/approve`
- **AND** on success the job list/detail SHALL reflect `status: "queued"` and the newly-set `hyperparams`

#### Scenario: Backend validation error is surfaced on the approval form

- **GIVEN** the System Admin submits the approval form
- **AND** `/api/v1/training-jobs/{job_id}/approve` responds with a 422 validation error
- **THEN** the form SHALL display the backend's error message
- **AND** the form SHALL remain open with the entered values intact
