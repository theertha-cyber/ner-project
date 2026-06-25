## MODIFIED Requirements

### Requirement: Layout and Navigation

The annotation workspace SHALL render at `/annotation` inside the authenticated app shell. The workspace SHALL support two layout modes: **3-pane** (default) with a fixed-width task queue (`228px`) on the left, a scrollable document viewer in the center, and a fixed-width entity panel (`326px`) on the right; and **focus mode** where the task queue is hidden, the entity palette becomes a `position: fixed` horizontal strip anchored to the bottom center of the viewport, and the document viewer expands to the full browser width with a maximum content width of `760px`. The selected layout mode SHALL be persisted to `localStorage` under the key `"ner-annotation-layout"`.

The view-mode control in the toolbar SHALL be a **two-button radio group** — one button labeled "3-pane" and one labeled "Focus" — rendered inside a shared pill container. The active button SHALL receive a filled background and visual emphasis; the inactive button SHALL appear unstyled within the pill. There SHALL NOT be a single toggle button whose label changes between modes.

The workspace SHALL NOT call the Fullscreen API (`requestFullscreen`, `exitFullscreen`) when entering or exiting focus mode. Focus mode is CSS-only: the task queue is hidden, the document viewer expands, and the entity palette repositions to the floating bottom strip. No `fullscreenchange` event listener is required.

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
- **AND** the entity palette SHALL render as a `position: fixed` bottom-center strip
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

### Requirement: Task Display Name

Each annotation task SHALL display its associated document filename as the primary label in both the task queue row and the annotation toolbar. Raw document UUIDs or ordinals such as "Task N" SHALL NOT appear as the primary identifier.

The annotation-task API response SHALL include a `filename` field. The task queue and toolbar SHALL read the `filename` field from the task object directly.

#### Scenario: Task queue shows document filename

- **GIVEN** the task queue is populated with tasks whose documents are named "invoice-2026-00417.pdf" and "contract-northwind.pdf"
- **WHEN** the task queue sidebar renders
- **THEN** the first row SHALL display "invoice-2026-00417.pdf" as the primary label
- **AND** the second row SHALL display "contract-northwind.pdf"
- **AND** ordinal labels such as "Task 1" or "Task 2" SHALL NOT appear as the primary identifier

#### Scenario: Toolbar shows document filename for the selected task

- **GIVEN** the user has selected a task whose document is "invoice-2026-00417.pdf"
- **WHEN** the workspace toolbar renders
- **THEN** the filename "invoice-2026-00417.pdf" SHALL appear in the toolbar in JetBrains Mono
- **AND** the task status badge SHALL appear adjacent to the filename

---

### Requirement: Annotation Task Queue

The workspace SHALL display a list of annotation tasks from `GET /api/v1/annotation-tasks` in the left queue panel (visible in 3-pane mode). For `annotator` users the list SHALL show only tasks assigned to the current user. For `tenant_admin` users the list SHALL show all tasks for the tenant.

Each task row SHALL display:
- Primary label: the document filename (e.g. `"invoice-2026-00417.pdf"`) in JetBrains Mono
- Subtitle: `"<document_status> · <span_count> spans"` (e.g. `"processed · 12 spans"`) in small secondary text

The active (selected) task row SHALL be highlighted with a left border in the primary color and a soft primary-tinted background. Selecting a task SHALL load that document into the document viewer and reset span state.

#### Scenario: Task row shows filename and document metadata

- **GIVEN** the task queue is populated and the active document is named "invoice-2026-00417.pdf" with status "processed" and 12 confirmed spans
- **WHEN** the task queue panel renders
- **THEN** the task row primary label SHALL read "invoice-2026-00417.pdf"
- **AND** the subtitle SHALL read "processed · 12 spans"

#### Scenario: Active task row is highlighted

- **GIVEN** the user has selected the first task in the queue
- **WHEN** the task queue renders
- **THEN** the selected row SHALL show a left border in `var(--color-primary)` and a soft primary-tinted background
- **AND** the other rows SHALL have no border or tinted background

#### Scenario: Annotator sees only assigned tasks

- **GIVEN** an authenticated annotator user with two assigned tasks and three tasks assigned to other users
- **WHEN** the annotation workspace loads
- **THEN** the queue SHALL show exactly two task rows

#### Scenario: Empty queue shows contextual message

- **GIVEN** there are no annotation tasks for the current user
- **WHEN** the annotation workspace loads
- **THEN** the queue panel SHALL display "No tasks assigned" with a prompt to contact a tenant admin

---

### Requirement: Annotation Toolbar

The workspace toolbar SHALL render at the top of the annotation workspace with the following elements from left to right: (1) the active document filename displayed in JetBrains Mono with a task status badge adjacent to it; (2) a three-button status group (buttons labeled "pending", "in_progress", "completed") styled as a pill radio group; (3) a flex spacer; (4) a span counter showing "N confirmed · N suggested" in JetBrains Mono; (5) a "✦ Pre-label" button; (6) the 3-pane/Focus view-mode radio group. There SHALL NOT be a separate "Mark Complete" button in the toolbar.

Clicking a status button in the status group SHALL send `PATCH /api/v1/annotation-tasks/{id}` with the new status. The request SHALL be sent optimistically — the active status button SHALL update immediately. If the API responds with a 4xx or 5xx error, the status button selection SHALL revert to the previous value and a toast SHALL display the error message.

The active status button SHALL render with a solid primary fill (`background: var(--primary); color: #fff`). Inactive buttons SHALL appear unstyled within the pill container.

#### Scenario: Toolbar renders all elements for an active task

- **GIVEN** a task is selected with document filename "invoice-2026-00417.pdf", status "in-progress", 3 confirmed spans, and 2 suggested spans
- **WHEN** the annotation toolbar renders
- **THEN** the toolbar SHALL show the filename "invoice-2026-00417.pdf" in JetBrains Mono with a status badge
- **AND** the status group SHALL show "in_progress" as the active button with solid primary fill
- **AND** the span counter SHALL read "3 confirmed · 2 suggested"
- **AND** the "✦ Pre-label" button and the 3-pane/Focus toggle SHALL be visible

#### Scenario: Clicking a status button updates the task optimistically

- **GIVEN** an active task with status "in-progress"
- **WHEN** the user clicks the "completed" button in the status group
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the "completed" button SHALL render with solid primary fill immediately (optimistic)

#### Scenario: Status transition rejected by backend reverts selection

- **GIVEN** an active task with status "in-progress"
- **WHEN** the user clicks "completed" and the API returns 4xx or 5xx
- **THEN** the status group SHALL revert to "in_progress" as the active button
- **AND** a toast SHALL display the error message from the API response

---

### Requirement: Document Viewer and Token Rendering

The workspace SHALL render the active document's text as a sequence of word tokens. The token area SHALL be wrapped in a paper-like card surface (`border: 1px solid var(--line)`, `border-radius: 16px`, `padding: 36px 40px`, `box-shadow: var(--shadow)`) with a maximum width of `680px` centered within the document column. Token line height SHALL be `2.05` to provide visual breathing room between lines.

Tokens belonging to confirmed spans SHALL be highlighted with the entity type's assigned color. Tokens belonging to suggested spans SHALL be highlighted with a dashed-border overlay in a muted variant of the entity type's color. Confirmed spans take visual precedence over suggested spans. A drag-preview overlay SHALL apply when the user is mid-drag with an armed entity type.

#### Scenario: Document renders inside a card container

- **GIVEN** a task is selected and the document text is loaded
- **WHEN** the document viewer renders
- **THEN** the token content SHALL appear inside a card element with `border-radius: 16px` and box shadow
- **AND** the card SHALL be centered with `max-width: 680px`

#### Scenario: Confirmed span tokens are highlighted

- **GIVEN** a document with a confirmed span "Acme Corp" (ORG)
- **WHEN** the document viewer renders
- **THEN** the tokens "Acme" and "Corp" SHALL render with the ORG entity type color as background

#### Scenario: Suggested span tokens show dashed overlay

- **GIVEN** a document with a suggested span for "Acme Corp" (ORG)
- **WHEN** the document viewer renders
- **THEN** the tokens "Acme" and "Corp" SHALL render with a dashed border in a muted ORG color
- **AND** confirmed spans SHALL take visual precedence over suggestions if they overlap

---

### Requirement: Entity Type Palette and Armed Mode

The entity palette SHALL display all active entity types from `GET /api/v1/entity-types` as clickable buttons. In 3-pane mode, the palette renders as a vertical list in the right panel. In focus mode, the palette renders as a horizontal strip in the bottom-center floating pill (see Focus Mode Entity Palette requirement).

Each entity type button SHALL display:
- A **colored dot** of `11×11px` with `border-radius: 3px` (rounded square, not a circle) using the entity type's assigned color
- The entity type name in bold JetBrains Mono as the primary label
- A `base: <base_type>` sub-label in small greyed JetBrains Mono (from `target_table` field)
- The confirmed span count for the active document, right-aligned

Clicking an entity type button SHALL arm it. The armed button SHALL receive an active border and ring highlight. Pressing `Escape` or clicking the armed button again SHALL disarm.

When an entity type is armed, an **armed banner** SHALL appear below the toolbar with: a pulsing dot (`animation: pulse 1.3s infinite`), the instructional text `"Labeling mode · click words to tag as <entity_name>"`, and an "esc · done" text button on the right to disarm. The banner SHALL use `background: var(--primary-soft)` and `border-bottom: 1px solid var(--primary-line)`.

#### Scenario: Palette shows entity types with correct visual elements

- **GIVEN** an active document with 3 confirmed "vendor_name" spans; entity type "vendor_name" has `target_table` = "ORG"
- **WHEN** the entity palette renders
- **THEN** each entity type button SHALL show a `11×11px` rounded-square dot (border-radius 3px)
- **AND** the "vendor_name" button SHALL display "vendor_name" as the primary label in JetBrains Mono
- **AND** SHALL display "base: ORG" as a secondary sub-label
- **AND** SHALL display count "3" right-aligned

#### Scenario: Armed banner shows instructional text

- **GIVEN** the entity palette is idle (no type armed)
- **WHEN** the user clicks the "vendor_name" button
- **THEN** the armed banner SHALL appear with text "Labeling mode · click words to tag as vendor_name"
- **AND** a pulsing dot animation SHALL be visible in the banner
- **AND** an "esc · done" control SHALL appear on the right side of the banner

#### Scenario: Escape key disarms via banner

- **GIVEN** the "vendor_name" entity type is currently armed
- **WHEN** the user presses `Escape` OR clicks the "esc · done" banner button
- **THEN** the armed type SHALL be cleared
- **AND** the armed banner SHALL disappear

#### Scenario: Clicking the armed chip again disarms it

- **GIVEN** the "vendor_name" entity type is currently armed
- **WHEN** the user clicks the "vendor_name" button again
- **THEN** the armed type SHALL be cleared (toggle-off behavior)

---

### Requirement: Span Inspector

When a user clicks a confirmed-span token while no entity type is armed, the workspace SHALL open a span inspector. The inspector SHALL display the span text as a colored chip and a 2×2 metadata grid showing `char_start`, `char_end`, `confidence`, and `base` values in JetBrains Mono. The inspector SHALL provide inline reassign chips (one per entity type) for retyping the span and a "Delete span" button.

In **3-pane mode**, the inspector SHALL render as a card inside the right entity panel, stacked below the entity palette (NOT in the center document column). The panel style SHALL be `border: 1px solid var(--line); border-radius: 14px`.

In **focus mode**, the inspector SHALL render as a condensed header `"<span_text> · [<charStart>, <charEnd>] · conf <confidence>"` above the reassign chips and delete button, inside a `position: fixed; top: 140px; right: 30px; width: 290px` glass card with `backdrop-filter: blur(20px)`.

Both actions (retype and delete) SHALL update the document viewer optimistically and dismiss the inspector on success. The inspector SHALL include an entrance animation (`animation: popIn 0.25s ease both`).

#### Scenario: Clicking a confirmed span opens inspector in right panel (3-pane)

- **GIVEN** a confirmed span "Acme Corp" (ORG) and the workspace is in 3-pane mode
- **WHEN** the user clicks the token "Acme" while no entity type is armed
- **THEN** the span inspector SHALL open inside the right entity panel (not in the center document column)
- **AND** SHALL show a colored chip with text "Acme Corp"
- **AND** SHALL show a 2×2 metadata grid

#### Scenario: Focus mode inspector renders condensed at fixed position

- **GIVEN** the workspace is in focus mode and the user clicks a confirmed-span token
- **WHEN** the span inspector mounts
- **THEN** the inspector SHALL render at `position: fixed; top: 140px; right: 30px; width: 290px`
- **AND** the header SHALL read `"<span_text> · [<charStart>, <charEnd>] · conf <confidence>"` on a single line
- **AND** the container SHALL use `backdrop-filter: blur(20px)` with `background: var(--glass)`

#### Scenario: Retype chip updates the span

- **GIVEN** the span inspector is open for span "Acme Corp" (ORG) and the user clicks the "vendor_name" chip
- **WHEN** the chip is clicked
- **THEN** a `PATCH /documents/{id}/spans/{span_id}` request SHALL be sent with `{entity_type: "vendor_name"}`
- **AND** on success, the token highlight SHALL change to the vendor_name color
- **AND** the inspector SHALL close

#### Scenario: Delete removes the span

- **GIVEN** the span inspector is open for span "Acme Corp"
- **WHEN** the user clicks "Delete span"
- **THEN** a `DELETE /documents/{id}/spans/{span_id}` request SHALL be sent
- **AND** on success (204), the token highlights SHALL be removed
- **AND** the inspector SHALL close

---

### Requirement: Pre-labeling and Suggestion Flow

The workspace SHALL provide a "✦ Pre-label" button in the toolbar that triggers `POST /api/v1/documents/{id}/prelabel`. On success, suggested spans SHALL render with dashed-border styling in the document viewer and as cards in the suggestion panel.

In **3-pane mode**, the suggestion panel SHALL render in the right entity panel, stacked below the entity palette and span inspector (NOT below the document viewer in the center column). Each suggestion card SHALL show: a colored dot, the matched text, the entity type name, and a confidence score (e.g. "conf 0.85"). Each card SHALL have a "Promote" button and a dismiss ("✕") button.

Promoting calls `POST /documents/{id}/spans/promote/{suggest_id}` and converts the suggestion to a confirmed span. Clicking "✕" removes the suggestion from the UI without an API call. The "✦ Pre-label" button SHALL be disabled while a pre-label request is in-flight.

#### Scenario: Suggestion panel renders in right panel (3-pane)

- **GIVEN** an active document in 3-pane mode and pre-labeling returns 3 suggested spans
- **WHEN** the suggestion panel renders
- **THEN** the suggestion cards SHALL appear in the right entity panel, below the entity palette
- **AND** the center document column SHALL NOT contain suggestion cards

#### Scenario: Pre-label populates suggestion cards

- **GIVEN** an active document with no existing suggested spans
- **WHEN** the user clicks the "✦ Pre-label" button
- **THEN** a `POST /documents/{id}/prelabel` request SHALL be sent
- **AND** on success, each returned suggested span SHALL appear as a card in the suggestion panel
- **AND** each card SHALL show the span text, entity type, and confidence value

#### Scenario: Promote converts a suggestion to a confirmed span

- **GIVEN** a suggestion card for "Acme Corp" (vendor_name, suggest_id "s-1") is visible
- **WHEN** the user clicks the "Promote" button on that card
- **THEN** a `POST /documents/{id}/spans/promote/s-1` request SHALL be sent
- **AND** on success (201), the confirmed span SHALL replace the suggested span in the viewer
- **AND** the suggestion card SHALL be removed from the panel

#### Scenario: Dismiss removes suggestion locally

- **GIVEN** a suggestion card for "Acme Corp" is in the suggestion panel
- **WHEN** the user clicks the "✕" dismiss button
- **THEN** the suggestion card SHALL be removed from the panel
- **AND** the dashed-border token highlight SHALL be removed from the document viewer
- **AND** no API request SHALL be sent

---

### Requirement: Task Status Lifecycle

When the first confirmed span is created on a task's document — whether by direct token click, drag selection, or suggestion promotion — the task SHALL automatically transition from `unannotated` to `in-progress` via `PATCH /annotation-tasks/{id}`. The in-progress transition SHALL be sent at most once per task per browser session (idempotency guard).

Task status transitions (pending → in_progress → completed) are managed through the toolbar status group (see Annotation Toolbar requirement). There SHALL NOT be a separate "Mark Complete" button.

#### Scenario: First span creation triggers in-progress transition

- **GIVEN** an active task with status `unannotated` and no confirmed spans
- **WHEN** the user creates the first confirmed span (via token click, drag, or promote)
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the status badge in the toolbar SHALL update to "in_progress"

#### Scenario: In-progress transition fires only once per session

- **GIVEN** an active task with status `unannotated`
- **WHEN** the user creates multiple spans in the same browser session
- **THEN** the `PATCH` in-progress request SHALL be sent exactly once
- **AND** subsequent span creations SHALL NOT send additional in-progress PATCHes

---

## ADDED Requirements

### Requirement: Focus Mode Entity Palette

In focus mode the entity palette SHALL render as a `position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%)` horizontal pill container with `backdrop-filter: blur(22px) saturate(1.4)` and `background: var(--glass)`. The pill SHALL contain from left to right: a "LABEL AS" label in JetBrains Mono, one inline chip per entity type showing colored dot + name + span count, a vertical separator, and the "✦ Pre-label" button.

Clicking an entity type chip in the bottom palette SHALL arm that entity type (same armed-mode behavior as the 3-pane palette). The bottom palette SHALL only be visible when the workspace is in focus mode.

#### Scenario: Bottom palette renders in focus mode

- **GIVEN** the workspace is in focus mode
- **WHEN** the focus-mode layout renders
- **THEN** a horizontal pill container SHALL appear at the bottom center of the viewport
- **AND** the pill SHALL begin with the label "LABEL AS"
- **AND** each entity type SHALL appear as an inline chip showing colored dot, entity name, and span count
- **AND** a "✦ Pre-label" button SHALL appear at the right end of the pill

#### Scenario: Bottom palette is hidden in 3-pane mode

- **GIVEN** the workspace is in 3-pane mode
- **WHEN** the layout renders
- **THEN** the bottom-center fixed pill SHALL NOT be present in the DOM

#### Scenario: Arming from bottom palette triggers armed banner

- **GIVEN** the workspace is in focus mode
- **WHEN** the user clicks an entity type chip in the bottom palette
- **THEN** the entity type SHALL become armed
- **AND** the armed banner SHALL appear below the toolbar with instructional text

---

## REMOVED Requirements

### Requirement: Task Display Name (original "Task N" version)

**Reason:** The finalized mockup uses document filenames as the primary display label for tasks. "Task N" ordinals provide no context about document content and require client-side sequence tracking. Document filenames are available on the annotation-task API response and are more meaningful to annotators. This requirement is superseded by the updated Task Display Name requirement above.

**Migration:** Any code rendering "Task N" labels SHALL be updated to display the `filename` field from the task object. Tests asserting "Task 1" / "Task 2" patterns SHALL be updated to assert filename values.

### Requirement: Fullscreen API behaviors

**Reason:** Focus mode is CSS-only per the updated Layout and Navigation requirement. The Fullscreen API integration (`requestFullscreen`, `exitFullscreen`, `fullscreenchange` event listener) is removed to simplify focus mode and avoid permission-related failure modes.

**Migration:** Remove any `requestFullscreen` / `exitFullscreen` calls and `fullscreenchange` listeners from the annotation workspace. Focus mode toggle SHALL only update CSS layout state.
