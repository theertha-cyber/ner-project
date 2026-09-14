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

#### Scenario: Running extraction displays results grouped by type

- **GIVEN** the Playground tab is active and text is entered in the textarea
- **WHEN** the user clicks "Run extraction"
- **THEN** the button SHALL show a spinner and be disabled
- **AND** a `POST /api/v1/extract` request SHALL be sent with `{"text": <textarea content>}`
- **AND** on success (200), entities SHALL be displayed grouped alphabetically by type
- **AND** each entity SHALL show: a colored dot, the cleaned entity type (without B-/I- prefix), the entity value, and the confidence score
- **AND** the entity summary label SHALL update to "N entities · M types"
- **AND** the button SHALL re-enable

#### Scenario: Multi-token entities are merged into a single row

- **GIVEN** the inference response returns `[{"token":"Steve","label":"B-PER","confidence":0.98}, {"token":"Jobs","label":"I-PER","confidence":0.97}]`
- **WHEN** the entities are displayed
- **THEN** a single row SHALL render under the "PERSON" group with value "Steve Jobs" and confidence 0.975

#### Scenario: Groups are ordered alphabetically

- **GIVEN** extracted entities of types "PERSON", "ORGANIZATION", and "LOCATION"
- **WHEN** the results panel renders
- **THEN** the "LOCATION" group SHALL appear first, followed by "ORGANIZATION", then "PERSON"

#### Scenario: Entities within a group are ordered by text position

- **GIVEN** a group contains entities at start_offset 10, 5, and 20
- **WHEN** the group renders
- **THEN** the entities SHALL appear in order: offset 5 → offset 10 → offset 20

---

### Requirement: Batch Runs Tab — Batch Extraction Management

The Batch Runs tab SHALL render a two-column layout with a 340px-wide left column listing batch run cards and a right detail panel. Above the columns, the tab SHALL show a label "POST /api/v1/extract-batch · async via Celery" on the left and a "⊕ New batch run" primary button on the right. Each batch run card in the left list SHALL display: the run ID in JetBrains Mono, a status pill (completed / running / queued / failed), a progress bar showing processed/total percentage, and a footer row with "N% docs · model vM" and the start timestamp. The selected run card SHALL have a primary-colored border. The right detail panel SHALL display: the run ID, status pill, and model version label in a header row; a large percentage number showing processed%; a progress bar; and a 4-cell stats grid (TOTAL, PROCESSED, SKIPPED, FAILED) with color-coded values (`var(--good)` for PROCESSED, `var(--warn)` for SKIPPED, `var(--bad)` for FAILED). Clicking "New batch run" SHALL POST to `/api/v1/extract-batch` (without document IDs to process all eligible documents) and add the new run to the top of the list. On mount, the tab SHALL fetch run history from `GET /api/v1/extract-batch` so that previously triggered runs remain visible across page reloads.

The left-hand run list column SHALL be constrained to a bounded height and SHALL scroll independently (`overflow-y: auto`) when the number of run cards exceeds the available height. Scrolling the run list SHALL NOT cause the page (header, tab pills, or the right-hand detail panel) to scroll; only the run list column's internal content SHALL move.

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

#### Scenario: Long run list scrolls independently of the page

- **GIVEN** the Batch Runs tab is active and the run list contains more runs than fit in the available column height
- **WHEN** the user scrolls within the run list column
- **THEN** the run list's internal content SHALL scroll
- **AND** the page header, tab pills, and the right-hand detail panel SHALL remain in place (not scroll with the run list)

#### Scenario: Document selection dialog remains centered and independently scrollable

- **GIVEN** the user clicks "New batch run" and the document-selection dialog opens
- **WHEN** the dialog renders with more eligible documents than fit in its panel height
- **THEN** the dialog SHALL remain centered on the screen
- **AND** only the document checklist within the dialog SHALL scroll, not the underlying page

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

#### Scenario: BIO prefix is stripped from entity type in display

- **GIVEN** an entity with `entity_id`: "B-ORG" and value "Acme Corp"
- **WHEN** the entity type group renders
- **THEN** the group heading SHALL read "ORG" (without the "B-" prefix)

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

### Requirement: Batch Document-Selection Modal — Bulk Selection

The batch document-selection modal SHALL render a "Select all" checkbox between the "Select documents to extract" heading and the scrollable document list, and a selected-count line below the list. Both controls SHALL operate only on the documents currently shown in the modal.

A document is *selectable* when its `already_extracted` flag is `false`. "Select all" SHALL be checked when the modal contains at least one selectable document and every selectable document is selected, and unchecked otherwise. Checking it SHALL select every selectable document; unchecking it SHALL deselect every selectable document. It SHALL be disabled when the modal contains zero selectable documents.

Documents with `already_extracted: true` SHALL NEVER enter the selection set by any path, including "Select all", and SHALL remain visibly unchecked and disabled. The selected-count line SHALL report only selectable documents that are actually selected.

This requirement adds controls to the existing modal and SHALL NOT change its dimensions, layout, scroll behavior, typography, buttons, per-row checkbox styling, or dark/light theme behavior.

#### Scenario: Unextracted documents are selectable

- **GIVEN** the modal is open with a document whose `already_extracted` is `false`
- **WHEN** the user clicks that document's checkbox
- **THEN** the checkbox SHALL become checked
- **AND** the selected-count line SHALL report one selected document

#### Scenario: Select all selects every eligible document and excludes already-extracted ones

- **GIVEN** the modal is open with three selectable documents and two already-extracted documents
- **WHEN** the user checks "Select all"
- **THEN** all three selectable documents' checkboxes SHALL be checked
- **AND** both already-extracted documents' checkboxes SHALL remain unchecked and disabled
- **AND** the selected-count line SHALL report three selected documents

#### Scenario: Clearing Select all deselects eligible documents without affecting disabled ones

- **GIVEN** the modal is open with "Select all" checked and every selectable document selected
- **WHEN** the user unchecks "Select all"
- **THEN** every selectable document's checkbox SHALL become unchecked
- **AND** the already-extracted documents' checkboxes SHALL remain unchecked and disabled
- **AND** the "Run extraction" action SHALL be disabled

#### Scenario: Select all reflects the current selection state

- **GIVEN** the modal is open with every selectable document individually checked
- **WHEN** the modal renders
- **THEN** the "Select all" checkbox SHALL be checked
- **AND** unchecking any single document SHALL make "Select all" unchecked

#### Scenario: Select all is disabled when there are no eligible documents

- **GIVEN** the modal is open and every listed document has `already_extracted: true`
- **WHEN** the modal renders
- **THEN** the "Select all" checkbox SHALL be disabled
- **AND** the "Run extraction" action SHALL be disabled

#### Scenario: Run extraction submits only eligible selected documents

- **GIVEN** the modal is open with a mix of selectable and already-extracted documents and "Select all" checked
- **WHEN** the user clicks "Run extraction"
- **THEN** the confirmed document ID list SHALL contain exactly the selectable documents' IDs
- **AND** SHALL NOT contain any already-extracted document's ID

