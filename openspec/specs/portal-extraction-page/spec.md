## Purpose

This capability covers the Extraction page frontend in the portal (`/extractions`). It provides a three-tab workspace — Playground, Batch Runs, and Entity Review — for interacting with the NER extraction API, managing batch extraction jobs, and reviewing extracted entities.

---

## Requirements

### Requirement: Extraction Page Layout and Tab Navigation

The system SHALL render a three-tab workspace at `/extractions` for users with the `business_user` role. The page SHALL display a page header with the title "Extraction" in Hanken Grotesk 800-weight 34px and a kicker label `/api/v1/extract · port 8005` in JetBrains Mono above it. Below the header, the page SHALL render a tab pill containing three buttons — "Playground", "Batch Runs", and "Entity Review" — styled as a segment control (`background: var(--surface-2); border: 1px solid var(--line); border-radius: 12px; padding: 4px`). The active tab button SHALL receive a filled primary background; inactive buttons SHALL appear unstyled within the pill. Only the content for the active tab SHALL be rendered.

#### Scenario: Page renders with Playground tab active by default

- **GIVEN** an authenticated `business_user` navigates to `/extractions`
- **WHEN** the page mounts
- **THEN** the page SHALL render the "Extraction" heading and the three-tab pill
- **AND** the "Playground" tab button SHALL be active (filled background)
- **AND** the Playground tab content SHALL be visible

#### Scenario: Clicking a tab switches the active content

- **GIVEN** the Extractions page is open with the Playground tab active
- **WHEN** the user clicks "Batch Runs"
- **THEN** the "Batch Runs" button SHALL become the active tab
- **AND** the Batch Runs content SHALL replace the Playground content
- **AND** the Playground content SHALL NOT be present in the DOM

---

### Requirement: Playground Tab — Real-time Extraction

The Playground tab SHALL render a two-column grid layout (`grid-template-columns: 1fr 1fr; gap: 18px`). The left column SHALL be a card containing: a "Input text" heading and a "model v{N} · serving" label (where N is the `model_version` from the last response, defaulting to the promoted version), a resizable textarea pre-populated with sample text, and a full-width "Run extraction" button. The right column SHALL be a card with an "Entities" heading and an entity count label showing "N found · sorted by confidence". When the user clicks "Run extraction", the system SHALL POST to `/api/v1/extract` with `{"text": <textarea value>}` and display the returned entities. While the request is in-flight, a spinner SHALL appear inside the "Run extraction" button and an animated spinner SHALL appear in the results panel. The "Run extraction" button SHALL be disabled during the in-flight request. A hint below the button SHALL read "Whitespace-tokenized · POST /internal/v1/infer · mapped to char offsets. Not persisted."

#### Scenario: Running extraction displays results

- **GIVEN** the Playground tab is active and text is entered in the textarea
- **WHEN** the user clicks "Run extraction"
- **THEN** the button SHALL show a spinner and be disabled
- **AND** a `POST /api/v1/extract` request SHALL be sent with `{"text": <textarea content>}`
- **AND** on success (200), each entity in the response SHALL render as a row showing: an entity type chip (colored dot + type label), the entity value, and the confidence score
- **AND** the entity count label SHALL update to "N found · sorted by confidence"
- **AND** the button SHALL re-enable

#### Scenario: Playground shows spinner in results panel during in-flight request

- **GIVEN** a `POST /api/v1/extract` request is in-flight
- **WHEN** the results panel renders
- **THEN** an animated circular spinner SHALL appear centered in the results panel
- **AND** previous results (if any) SHALL NOT be shown during the in-flight state

#### Scenario: Playground shows model version from response

- **GIVEN** the extraction response includes `model_version: "3"`
- **WHEN** the result is displayed
- **THEN** the label in the input card header SHALL read "model v3 · serving"

#### Scenario: Empty textarea prevents submission

- **GIVEN** the textarea is empty
- **WHEN** the user clicks "Run extraction"
- **THEN** no API request SHALL be sent

---

### Requirement: Batch Runs Tab — Batch Extraction Management

The Batch Runs tab SHALL render a two-column layout with a 340px-wide left column listing batch run cards and a right detail panel. Above the columns, the tab SHALL show a label "POST /api/v1/extract-batch · async via Celery" on the left and a "⊕ New batch run" primary button on the right. Each batch run card in the left list SHALL display: the run ID in JetBrains Mono, a status pill (completed / running / queued / failed), a progress bar showing processed/total percentage, and a footer row with "N% docs · model vM" and the start timestamp. The selected run card SHALL have a primary-colored border. The right detail panel SHALL display: the run ID, status pill, and model version label in a header row; a large percentage number showing processed%; a progress bar; and a 4-cell stats grid (TOTAL, PROCESSED, SKIPPED, FAILED) with color-coded values (`var(--good)` for PROCESSED, `var(--warn)` for SKIPPED, `var(--bad)` for FAILED). Clicking "New batch run" SHALL POST to `/api/v1/extract-batch` (without document IDs to process all eligible documents) and add the new run to the top of the list.

#### Scenario: Batch Runs tab lists existing runs

- **GIVEN** the user switches to the Batch Runs tab
- **WHEN** the tab mounts
- **THEN** a `GET /api/v1/extract-batch` request SHALL be sent (or the list SHALL be derived from available run data)
- **AND** each batch run SHALL appear as a card showing ID, status, progress bar, and footer metadata
- **AND** the most recent run SHALL be selected by default and its detail shown in the right panel

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

---

### Requirement: Entity Review Tab — Entity Listing and Review

The Entity Review tab SHALL render a filter pill row followed by a table of extracted entities. The filter pills SHALL be: "all", "unreviewed", "confirmed", "corrected", "rejected" — styled as compact labeled buttons. The active filter pill SHALL render with a filled background. Changing the filter SHALL re-fetch `GET /api/v1/entities` with the appropriate `reviewStatus` query parameter (omit for "all"). The entity count SHALL be displayed as "N entities · GET /entities" in JetBrains Mono to the right of the filter pills. The entity table SHALL have five columns: TYPE (entity type chip with colored dot), VALUE (entity text + source document filename as subtitle), CONFIDENCE (colored by threshold — `var(--good)` ≥ 0.90, `var(--warn)` 0.70–0.89, `var(--bad)` < 0.70), REVIEW (review status pill), and an actions column with a confirm button (✓) and a reject button (✗). Clicking confirm SHALL PATCH the entity to `review_status: "confirmed"`. Clicking reject SHALL PATCH the entity to `review_status: "rejected"`. Both actions SHALL update the row optimistically.

#### Scenario: Entity Review tab loads entities with default filter

- **GIVEN** the user switches to the Entity Review tab
- **WHEN** the tab mounts
- **THEN** a `GET /api/v1/entities` request SHALL be sent with no `reviewStatus` filter
- **AND** all entities SHALL be displayed in the table
- **AND** the "all" filter pill SHALL be active

#### Scenario: Changing filter re-fetches entities

- **GIVEN** the Entity Review tab is active showing all entities
- **WHEN** the user clicks the "unreviewed" filter pill
- **THEN** the "unreviewed" pill SHALL become the active filter
- **AND** a `GET /api/v1/entities?reviewStatus=unreviewed` request SHALL be sent
- **AND** the entity table SHALL update to show only unreviewed entities

#### Scenario: Entity rows display type chip, value, confidence, and review status

- **GIVEN** an entity with type "B-ORG", value "Acme Corp", confidence 0.998, review_status "unreviewed", from document "invoice-2026-00417.pdf"
- **WHEN** the entity table renders
- **THEN** the TYPE column SHALL show a colored chip with label "B-ORG"
- **AND** the VALUE column SHALL show "Acme Corp" in bold with "invoice-2026-00417.pdf" as a subtitle below
- **AND** the CONFIDENCE column SHALL show "0.998" in `var(--good)` color
- **AND** the REVIEW column SHALL show an "unreviewed" status pill

#### Scenario: Confirming an entity updates its review status optimistically

- **GIVEN** an entity row with review_status "unreviewed"
- **WHEN** the user clicks the confirm button (✓) on that row
- **THEN** a `PATCH /api/v1/entities/{id}` request SHALL be sent with `{"review_status": "confirmed"}`
- **AND** the REVIEW column SHALL immediately update to "confirmed" (optimistic)
- **AND** the confirm and reject buttons SHALL be hidden or disabled for that row after confirmation

#### Scenario: Rejecting an entity updates its review status optimistically

- **GIVEN** an entity row with review_status "unreviewed"
- **WHEN** the user clicks the reject button (✗) on that row
- **THEN** a `PATCH /api/v1/entities/{id}` request SHALL be sent with `{"review_status": "rejected"}`
- **AND** the REVIEW column SHALL immediately update to "rejected" (optimistic)

#### Scenario: Confidence color coding reflects thresholds

- **GIVEN** three entities with confidences 0.94, 0.75, and 0.62
- **WHEN** the entity table renders
- **THEN** confidence 0.94 SHALL render in `var(--good)` (≥ 0.90)
- **AND** confidence 0.75 SHALL render in `var(--warn)` (0.70–0.89)
- **AND** confidence 0.62 SHALL render in `var(--bad)` (< 0.70)

#### Scenario: Empty entity list shows empty state

- **GIVEN** no entities exist for the current filter
- **WHEN** the entity table renders
- **THEN** the table SHALL show an empty state message instead of rows