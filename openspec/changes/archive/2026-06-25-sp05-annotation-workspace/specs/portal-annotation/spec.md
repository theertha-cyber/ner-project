## MODIFIED Requirements

### Requirement: Layout and Navigation

The annotation workspace SHALL render at `/annotation` inside the authenticated app shell. The workspace SHALL support two layout modes: **3-pane** (default) with a fixed-width task queue (`228px`) on the left, a scrollable document viewer in the center, and a fixed-width entity panel (`326px`) on the right; and **focus mode** where the task queue is hidden, the entity palette becomes a `position: fixed` horizontal strip anchored to the bottom center of the viewport, and the document viewer expands to the full browser width with a maximum content width of `760px`. The selected layout mode SHALL be persisted to `localStorage` under the key `"ner-annotation-layout"`.

The view-mode control in the toolbar SHALL be a **two-button radio group** — one button labeled "3-pane" and one labeled "Focus" — rendered inside a shared pill container (`background: var(--surface-3); border: 1px solid var(--line); border-radius: 9px; padding: 3px`). The active button SHALL receive a filled background and visual emphasis; the inactive button SHALL appear unstyled within the pill. There SHALL NOT be a single toggle button whose label changes between modes.

The workspace SHALL NOT call the Fullscreen API (`requestFullscreen`, `exitFullscreen`) when entering or exiting focus mode. Focus mode is CSS-only: the task queue is hidden, the document viewer expands, and the entity palette repositions to the floating bottom strip. No fullscreen-change event listener is required.

#### Scenario: Default layout renders three columns

- **GIVEN** an authenticated annotator navigates to `/annotation`
- **WHEN** the page mounts for the first time (no `localStorage` preference)
- **THEN** the workspace SHALL render with a task queue column (`228px`), a scrollable document viewer column, and an entity panel column (`326px`) visible simultaneously
- **AND** the view-mode control SHALL show a "3-pane" button in its active state and a "Focus" button in its inactive state

#### Scenario: Clicking "Focus" button enters CSS focus mode

- **GIVEN** the annotation workspace is in 3-pane mode
- **WHEN** the user clicks the "Focus" button in the view-mode radio group
- **THEN** the task queue column SHALL be hidden
- **AND** the document viewer SHALL expand to fill the full available width (max-width `760px`, centered)
- **AND** the entity palette SHALL render as a `position: fixed` bottom-center strip (see Focus Mode Entity Palette)
- **AND** the "Focus" button SHALL render in its active/filled state and "3-pane" in its inactive state
- **AND** the layout preference SHALL be written to `localStorage` under `"ner-annotation-layout"`
- **AND** `document.documentElement.requestFullscreen()` SHALL NOT be called

#### Scenario: Clicking "3-pane" button exits focus mode

- **GIVEN** the annotation workspace is in focus mode
- **WHEN** the user clicks the "3-pane" button in the view-mode radio group
- **THEN** the workspace SHALL return to three-column layout
- **AND** the "3-pane" button SHALL render in its active state
- **AND** the floating bottom entity palette SHALL be replaced by the right-side entity panel

#### Scenario: Layout preference is restored on reload

- **GIVEN** the user previously selected focus mode (stored in `localStorage`)
- **WHEN** the user navigates to `/annotation`
- **THEN** the workspace SHALL render in focus mode without requiring re-selection

---

### Requirement: Annotation Toolbar

The workspace toolbar SHALL render at the top of the annotation workspace with the following elements from left to right: (1) the active document filename displayed in `JetBrains Mono` with a task status badge adjacent to it; (2) a three-button status group (buttons labeled "pending", "in_progress", "completed") styled as a pill radio group; (3) a flex spacer; (4) a span counter showing "N confirmed · N suggested" in `JetBrains Mono`; (5) a "✦ Pre-label" button; (6) the 3-pane/Focus view-mode radio group. There SHALL NOT be a separate "Mark Complete" button in the toolbar.

Clicking a status button in the status group SHALL send `PATCH /api/v1/annotation-tasks/{id}` with the new status. The request SHALL be sent optimistically — the active status button SHALL update immediately. If the API responds with a 4xx or 5xx error (e.g. 422 when completing with no spans), the status button selection SHALL revert to the previous value and a toast SHALL display the error message. The status group SHALL remain interactive at all times; client-side disabling of the "completed" button based on span count is NOT required.

The span counter SHALL update in real time as spans are created, promoted, or deleted. It SHALL read confirmed span count from client state and suggested span count from client state.

#### Scenario: Toolbar renders all elements for an active task

- **GIVEN** a task is selected with document filename "invoice-2026-00417.pdf", status "in_progress", 3 confirmed spans, and 2 suggested spans
- **WHEN** the annotation toolbar renders
- **THEN** the toolbar SHALL show the filename "invoice-2026-00417.pdf" with a status badge
- **AND** the status group SHALL show "in_progress" as the active button
- **AND** the span counter SHALL read "3 confirmed · 2 suggested"
- **AND** the "✦ Pre-label" button and the 3-pane/Focus toggle SHALL be visible

#### Scenario: Clicking a status button transitions the task

- **GIVEN** an active task with status "in_progress"
- **WHEN** the user clicks the "completed" button in the status group
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the "completed" button SHALL render as active immediately (optimistic)
- **AND** on success (200), the task status badge SHALL reflect "completed"

#### Scenario: Status transition rejected by backend reverts selection

- **GIVEN** an active task with status "in_progress" and zero confirmed spans
- **WHEN** the user clicks the "completed" button
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the API SHALL return 422
- **AND** the status group SHALL revert to "in_progress" as the active button
- **AND** a toast SHALL display the error message from the API response

---

### Requirement: Annotation Task Queue

The workspace SHALL display a list of annotation tasks from `GET /api/v1/annotation-tasks` in the left queue panel (visible in 3-pane mode). For `annotator` users the list SHALL show only tasks assigned to the current user. For `tenant_admin` users the list SHALL show all tasks for the tenant. Each task row SHALL display the document filename and a metadata string (e.g. task status or document size). Selecting a task SHALL load that document into the document viewer and reset span state.

#### Scenario: Annotator sees only assigned tasks

- **GIVEN** an authenticated annotator user with two assigned tasks and three tasks assigned to other users
- **WHEN** the annotation workspace loads
- **THEN** the queue SHALL show exactly two task rows

#### Scenario: Task row shows document filename

- **GIVEN** the task queue is populated with tasks
- **WHEN** the task queue panel renders
- **THEN** each task row SHALL display the document filename (e.g. "invoice-2026-00417.pdf")
- **AND** raw document UUID fragments SHALL NOT appear as the primary label in the task row

#### Scenario: Selecting a task loads the document

- **GIVEN** the task queue is populated with at least two tasks
- **WHEN** the user clicks the second task row
- **THEN** the document viewer SHALL load the text for that task's document via `GET /documents/{id}/text`
- **AND** confirmed spans SHALL be fetched via `GET /documents/{id}/spans`
- **AND** suggested spans SHALL be fetched via `GET /documents/{id}/spans?type=suggested`

#### Scenario: Empty queue shows contextual message

- **GIVEN** there are no annotation tasks for the current user
- **WHEN** the annotation workspace loads
- **THEN** the queue panel SHALL display "No tasks assigned" with a prompt to contact a tenant admin

---

### Requirement: Entity Type Palette and Armed Mode

The entity palette SHALL display all active entity types from `GET /api/v1/entity-types` as clickable buttons. In 3-pane mode, the palette renders as a vertical list in the right panel. In focus mode, the palette renders as a horizontal strip in the bottom-center floating pill (see Focus Mode Entity Palette). Each entity type button SHALL display: a colored dot using the entity type's assigned color, the entity type name in bold (`JetBrains Mono`), a `base: <base_type>` sub-label in small greyed text, and the confirmed span count for the active document right-aligned. Clicking an entity type button SHALL arm it. The armed entity type button SHALL receive an active border/ring highlight. Pressing `Escape` or clicking the armed button again SHALL disarm the palette.

When an entity type is armed, an **armed banner** SHALL appear below the toolbar with: a pulsing dot (`animation: pulse 1.3s infinite`), the name and description of the armed entity type, and an "esc · done" text button on the right to disarm. The banner SHALL use `background: var(--primary-soft)` and `border-bottom: 1px solid var(--primary-line)`.

#### Scenario: Palette shows entity types with base label and span count

- **GIVEN** an active document with 3 confirmed "vendor_name" spans; entity type "vendor_name" has base type "ORG"
- **WHEN** the entity palette renders
- **THEN** the "vendor_name" button SHALL display "vendor_name" as the primary label
- **AND** SHALL display "base: ORG" as a secondary sub-label below the name
- **AND** SHALL display count "3" right-aligned

#### Scenario: Clicking a chip arms the entity type and shows animated banner

- **GIVEN** the entity palette is idle (no type armed)
- **WHEN** the user clicks the "vendor_name" button
- **THEN** the "vendor_name" button SHALL render with an active ring highlight
- **AND** the armed banner SHALL appear with a pulsing dot animation
- **AND** the banner SHALL contain text indicating "vendor_name" is armed
- **AND** an "esc · done" control SHALL appear on the right side of the banner

#### Scenario: Escape key disarms via banner

- **GIVEN** the "vendor_name" entity type is currently armed and the banner is visible
- **WHEN** the user presses the `Escape` key OR clicks the "esc · done" banner button
- **THEN** the armed type SHALL be cleared
- **AND** the armed banner SHALL disappear

#### Scenario: Clicking the armed chip again disarms it

- **GIVEN** the "vendor_name" entity type is currently armed
- **WHEN** the user clicks the "vendor_name" button again
- **THEN** the armed type SHALL be cleared (toggle-off behavior)

---

### Requirement: Span Inspector

When a user clicks a confirmed-span token while no entity type is armed, the workspace SHALL open a span inspector panel. In 3-pane mode the inspector renders as a card inside the right panel (`border: 1px solid var(--line); border-radius: 14px`). In focus mode the inspector renders as a `position: fixed; top: 140px; right: 30px; width: 290px` glass card with `backdrop-filter: blur(20px)`.

The inspector SHALL display: the span text as a colored chip (`background: <entity-soft-color>`), and a 2×2 metadata grid showing `char_start`, `char_end`, `confidence`, and `base` values in `JetBrains Mono`. The inspector SHALL provide **inline reassign chips** — one chip per entity type — for retyping the span; clicking a chip SHALL call `PATCH /documents/{id}/spans/{span_id}` with the new entity type. The inspector SHALL provide a "Delete span" button that calls `DELETE /documents/{id}/spans/{span_id}`. Both actions SHALL update the document viewer optimistically and dismiss the inspector on success.

The inspector SHALL include an `animation: popIn 0.25s ease both` entrance animation.

#### Scenario: Clicking a confirmed span opens the inspector with metadata grid

- **GIVEN** a confirmed span "Acme Corp" (ORG, `char_start: 0`, `char_end: 9`, confidence 1.0, base "ORG")
- **WHEN** the user clicks the token "Acme" while no entity type is armed
- **THEN** the span inspector SHALL open
- **AND** SHALL show a colored chip with text "Acme Corp"
- **AND** SHALL show a 2×2 grid with values: `char_start: 0`, `char_end: 9`, `confidence: 1.0`, `base: ORG`

#### Scenario: Retype chips are shown for all entity types

- **GIVEN** the span inspector is open for span "Acme Corp" (ORG) and the tenant has entity types vendor_name, customer_name, invoice_number
- **WHEN** the "REASSIGN TYPE" section renders
- **THEN** one inline chip SHALL appear for each entity type (excluding the current type)
- **AND** each chip SHALL show a colored dot and the entity type name

#### Scenario: Clicking a retype chip updates the span

- **GIVEN** the span inspector is open for span "Acme Corp" (ORG) and the user clicks the "vendor_name" chip
- **WHEN** the chip is clicked
- **THEN** a `PATCH /documents/{id}/spans/{span_id}` request SHALL be sent with `{entity_type: "vendor_name"}`
- **AND** on success, the token highlight SHALL change to the vendor_name color
- **AND** the inspector SHALL close

#### Scenario: Delete removes the span

- **GIVEN** the span inspector is open for span "Acme Corp"
- **WHEN** the user clicks the "Delete span" button
- **THEN** a `DELETE /documents/{id}/spans/{span_id}` request SHALL be sent
- **AND** on success (204), the token highlights SHALL be removed
- **AND** the inspector SHALL close

#### Scenario: Focus mode inspector renders as fixed glass card

- **GIVEN** the workspace is in focus mode and the user clicks a confirmed-span token
- **WHEN** the span inspector mounts
- **THEN** the inspector SHALL render at `position: fixed; top: 140px; right: 30px; width: 290px`
- **AND** the container SHALL use `backdrop-filter: blur(20px)` with `background: var(--glass)`

---

### Requirement: Pre-labeling and Suggestion Flow

The workspace SHALL provide a "✦ Pre-label" button in the toolbar that triggers `POST /api/v1/documents/{id}/prelabel`. On success, suggested spans SHALL be fetched and rendered in the suggestion panel (3-pane mode) and as dashed-border token overlays in the document viewer. Each suggestion SHALL render as a dashed-border card in the suggestion panel showing: a colored dot, the matched text, the entity type name, and a confidence score. Each card SHALL have a "Promote" button and a dismiss ("✕") button. Promoting calls `POST /documents/{id}/spans/promote/{suggest_id}` and converts the suggestion to a confirmed span. Clicking "✕" removes the suggestion from the UI without an API call. The Pre-label button SHALL be disabled while a pre-label request is in-flight.

#### Scenario: Pre-label populates suggestion cards

- **GIVEN** an active document with no existing suggested spans
- **WHEN** the user clicks the "✦ Pre-label" button
- **THEN** a `POST /documents/{id}/prelabel` request SHALL be sent
- **AND** on success, each returned suggested span SHALL appear as a dashed-border card in the suggestion panel
- **AND** each card SHALL show the span text, entity type, and confidence value (e.g. "conf 0.85")

#### Scenario: Promote converts a suggestion to a confirmed span

- **GIVEN** a suggestion card for "Acme Corp" (vendor_name, suggest_id "s-1") is visible
- **WHEN** the user clicks the "Promote" button on that card
- **THEN** a `POST /documents/{id}/spans/promote/s-1` request SHALL be sent
- **AND** on success (201), the confirmed span SHALL replace the suggested span in the viewer
- **AND** the dashed styling SHALL change to solid vendor_name color
- **AND** the suggestion card SHALL be removed from the panel

#### Scenario: Dismiss removes suggestion locally

- **GIVEN** a suggestion card for "Acme Corp" is in the suggestion panel
- **WHEN** the user clicks the "✕" dismiss button
- **THEN** the suggestion card SHALL be removed from the panel
- **AND** the dashed-border token highlight SHALL be removed from the document viewer
- **AND** no API request SHALL be sent

#### Scenario: Pre-label button is disabled during in-flight request

- **GIVEN** a `POST /documents/{id}/prelabel` request is in-flight
- **WHEN** the "✦ Pre-label" button is rendered
- **THEN** the button SHALL be visually disabled and non-interactive until the request settles

---

## ADDED Requirements

### Requirement: Focus Mode Entity Palette

In focus mode the entity palette SHALL render as a `position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%)` horizontal pill container with `backdrop-filter: blur(22px) saturate(1.4)` and `background: var(--glass)`. The pill SHALL contain from left to right: a "LABEL AS" label in `JetBrains Mono`, one inline chip per entity type showing colored dot + name + count, a vertical separator, and the "✦ Pre-label" button. Clicking an entity type chip in the bottom palette SHALL arm that entity type (same armed-mode behavior as the 3-pane palette).

The bottom palette SHALL only be visible when the workspace is in focus mode. In 3-pane mode the palette SHALL NOT render at the bottom.

#### Scenario: Bottom palette renders in focus mode

- **GIVEN** the workspace is in focus mode
- **WHEN** the focus-mode layout renders
- **THEN** a horizontal pill container SHALL appear at the bottom center of the viewport
- **AND** each entity type SHALL appear as an inline chip showing a colored dot, entity name, and span count
- **AND** a "✦ Pre-label" button SHALL appear at the right end of the pill

#### Scenario: Bottom palette is hidden in 3-pane mode

- **GIVEN** the workspace is in 3-pane mode
- **WHEN** the layout renders
- **THEN** the bottom-center fixed pill SHALL NOT be present in the DOM

#### Scenario: Arming from the bottom palette works identically to the right-panel palette

- **GIVEN** the workspace is in focus mode
- **WHEN** the user clicks an entity type chip in the bottom palette
- **THEN** the entity type SHALL become armed
- **AND** the armed banner SHALL appear below the toolbar
- **AND** token clicks SHALL create spans for that entity type

---

## REMOVED Requirements

### Requirement: Task Display Name

**Reason:** The finalized mockup uses document filenames instead of "Task N" ordinals as the primary display label for tasks. Ordinal labels gave no context about document content and required client-side sequence tracking. Document filenames are already present in the annotation-task API response and are more meaningful to annotators.

**Migration:** Any UI components rendering "Task N" labels SHALL be updated to display the document `filename` field from the task object. Tests asserting "Task 1" / "Task 2" patterns SHALL be updated to assert filename values.
