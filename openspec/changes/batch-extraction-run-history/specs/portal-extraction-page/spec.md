## MODIFIED Requirements

### Requirement: Batch Runs Tab — Batch Extraction Management

The Batch Runs tab SHALL render a two-column layout with a 340px-wide left column listing batch run cards and a right detail panel. Above the columns, the tab SHALL show a label "POST /api/v1/extract-batch · async via Celery" on the left and a "⊕ New batch run" primary button on the right. Each batch run card in the left list SHALL display: the run ID in JetBrains Mono, a status pill (completed / running / queued / failed), a progress bar showing processed/total percentage, and a footer row with "N% docs · model vM" and the start timestamp. The selected run card SHALL have a primary-colored border. The right detail panel SHALL display: the run ID, status pill, and model version label in a header row; a large percentage number showing processed%; a progress bar; and a 4-cell stats grid (TOTAL, PROCESSED, SKIPPED, FAILED) with color-coded values (`var(--good)` for PROCESSED, `var(--warn)` for SKIPPED, `var(--bad)` for FAILED). Clicking "New batch run" SHALL POST to `/api/v1/extract-batch` (without document IDs to process all eligible documents) and add the new run to the top of the list. On mount, the tab SHALL fetch run history from `GET /api/v1/extract-batch` so that previously triggered runs remain visible across page reloads.

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

#### Scenario: Triggering a new batch run

- **GIVEN** the Batch Runs tab is active
- **WHEN** the user clicks "New batch run"
- **THEN** a `POST /api/v1/extract-batch` request SHALL be sent
- **AND** on success (202), the new run SHALL appear at the top of the run list with status "queued"
- **AND** the new run SHALL be selected automatically, showing its detail in the right panel

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