## MODIFIED Requirements

### Requirement: Batch Runs Tab — Batch Extraction Management

The Batch Runs tab SHALL render a two-column layout with a 340px-wide left column listing batch run cards and a right detail panel. Above the columns, the tab SHALL show a label "POST /api/v1/extract-batch · async via Celery" on the left and a "⊕ New batch run" primary button on the right. Each batch run card in the left list SHALL display: the run ID in JetBrains Mono, a status pill (completed / running / queued / failed), a progress bar showing processed/total percentage, and a footer row with "N% docs · model vM" and the start timestamp. The selected run card SHALL have a primary-colored border. The right detail panel SHALL display: the run ID, status pill, and model version label in a header row; a large percentage number showing processed%; a progress bar; and a 4-cell stats grid (TOTAL, PROCESSED, SKIPPED, FAILED) with color-coded values (`var(--good)` for PROCESSED, `var(--warn)` for SKIPPED, `var(--bad)` for FAILED). Clicking "New batch run" SHALL open a document-selection modal rather than immediately triggering a run. On mount, the tab SHALL fetch run history from `GET /api/v1/extract-batch` so that previously triggered runs remain visible across page reloads.

The document-selection modal SHALL fetch `GET /api/v1/extract-batch/eligible-documents` on open and list each eligible document with a checkbox. Documents with `already_extracted: true` SHALL render disabled (unselectable) with a label indicating they were already processed, and SHALL NOT be included regardless of prior checkbox state. The modal SHALL have a "Run extraction" confirm action and a cancel/close action. The confirm action SHALL be disabled when zero documents are checked. Confirming SHALL POST to `/api/v1/extract-batch?documentIds=<comma-separated selected ids>`, close the modal, add the new run to the top of the run list, and select it automatically. Canceling SHALL close the modal without sending any request.

#### Scenario: Batch Runs tab lists existing runs

- **GIVEN** the user switches to the Batch Runs tab, or reloads the page while on it
- **WHEN** the tab mounts
- **THEN** a `GET /api/v1/extract-batch` request SHALL be sent
- **AND** each run returned in the response's `runs` array SHALL appear as a card showing ID, status, progress bar, and footer metadata
- **AND** the most recent run SHALL be selected by default and its detail shown in the right panel

#### Scenario: Run history persists across page reload

- **GIVEN** a batch run previously completed and the page is reloaded
- **WHEN** the Batch Runs tab mounts after reload
- **THEN** the completed run SHALL appear in the run list
- **AND** the run list SHALL NOT show the empty state ("No batch runs yet")

#### Scenario: Selecting a batch run shows detail

- **GIVEN** the Batch Runs tab is active with multiple run cards visible
- **WHEN** the user clicks a run card
- **THEN** the card SHALL receive a primary border highlight
- **AND** the right panel SHALL update to show that run's stats (total, processed, skipped, failed) and the large progress percentage

#### Scenario: Clicking "New batch run" opens the document-selection modal

- **GIVEN** the Batch Runs tab is active
- **WHEN** the user clicks "New batch run"
- **THEN** the document-selection modal SHALL open
- **AND** a `GET /api/v1/extract-batch/eligible-documents` request SHALL be sent
- **AND** no `POST /api/v1/extract-batch` request SHALL be sent yet

#### Scenario: Already-extracted documents are disabled in the modal

- **GIVEN** the document-selection modal is open with a document whose `already_extracted` is `true`
- **WHEN** the modal renders that document's row
- **THEN** its checkbox SHALL be disabled
- **AND** the row SHALL display a label indicating it was already processed

#### Scenario: Confirm is disabled with no selection

- **GIVEN** the document-selection modal is open and no checkboxes are checked
- **WHEN** the user views the modal
- **THEN** the "Run extraction" confirm action SHALL be disabled

#### Scenario: Triggering a new batch run with selected documents

- **GIVEN** the document-selection modal is open with two not-yet-extracted documents checked
- **WHEN** the user clicks "Run extraction"
- **THEN** a `POST /api/v1/extract-batch?documentIds=<the two checked document ids>` request SHALL be sent
- **AND** on success (202), the modal SHALL close
- **AND** the new run SHALL appear at the top of the run list with status "queued"
- **AND** the new run SHALL be selected automatically, showing its detail in the right panel

#### Scenario: Canceling the modal sends no request

- **GIVEN** the document-selection modal is open with some documents checked
- **WHEN** the user clicks cancel/close
- **THEN** the modal SHALL close
- **AND** no `POST /api/v1/extract-batch` request SHALL be sent

#### Scenario: In-progress runs poll for status updates

- **GIVEN** one or more batch runs have status "running" or "queued"
- **WHEN** the Batch Runs tab is mounted and active
- **THEN** the system SHALL poll `GET /api/v1/extract-batch/{run_id}` every 3 seconds for each in-flight run
- **AND** the run card progress bar and stats SHALL update when the polled status changes
- **AND** polling SHALL stop for a run when it reaches a terminal state ("completed" or "failed")

#### Scenario: Status pills use correct visual styles

- **GIVEN** batch runs with various statuses
- **WHEN** the run list renders
- **THEN** "completed" status SHALL use the success/good color token
- **AND** "running" and "queued" status SHALL use the warning color token
- **AND** "failed" status SHALL use the error/bad color token
