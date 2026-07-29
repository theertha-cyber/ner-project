# Portal Annotation Workspace

## Purpose

Frontend annotation workspace at `/annotation` for annotators and tenant admins to perform document labeling, manage annotation tasks, and trigger pre-labeling.

---

## Requirements

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

### Requirement: Annotation Toolbar

The workspace toolbar SHALL render at the top of the annotation workspace with the following elements from left to right: (1) the active document filename displayed in `JetBrains Mono` with a task status badge adjacent to it; (2) a flex spacer; (3) a span counter showing "N confirmed · N suggested" in `JetBrains Mono`; (4) a "✦ Pre-label" button; (5) the 3-pane/Focus view-mode radio group. The toolbar SHALL NOT render a status button group or any other control that lets the user select a task status.

The task status badge SHALL be read-only. It SHALL display `pending` for `unannotated`, `in_progress` for `in-progress`, and `completed` for `completed`, using the existing badge colors.

The span counter SHALL update in real time as spans are created, promoted, or deleted. It SHALL read confirmed span count from client state and suggested span count from client state.

#### Scenario: Toolbar renders all elements for an active task

- **GIVEN** a task is selected with document filename "invoice-2026-00417.pdf", status "in-progress", 3 confirmed spans, and 2 suggested spans
- **WHEN** the annotation toolbar renders
- **THEN** the toolbar SHALL show the filename "invoice-2026-00417.pdf" in JetBrains Mono with a status badge reading "in_progress"
- **AND** the span counter SHALL read "3 confirmed · 2 suggested"
- **AND** the "✦ Pre-label" button and the 3-pane/Focus toggle SHALL be visible

#### Scenario: Toolbar exposes no status selection control

- **GIVEN** a task is selected with any status
- **WHEN** the annotation toolbar renders
- **THEN** no status button group SHALL be present in the toolbar
- **AND** no element in the toolbar SHALL issue a `PATCH /api/v1/annotation-tasks/{id}` request

#### Scenario: Badge reflects completed status without offering a transition

- **GIVEN** a task whose status is `completed`
- **WHEN** the annotation toolbar renders
- **THEN** the status badge SHALL read "completed"
- **AND** there SHALL be no control in the toolbar that transitions the task to "in_progress"

### Requirement: Annotation Task Queue

The workspace SHALL display a list of annotation tasks from `GET /api/v1/annotation-tasks` in the left queue panel (visible in 3-pane mode). For `annotator` users the list SHALL show only tasks assigned to the current user. For `tenant_admin` users the list SHALL show all tasks for the tenant.

Each task row SHALL display:
- Primary label: the document filename (e.g. `"invoice-2026-00417.pdf"`) in JetBrains Mono
- Subtitle: `"<document_status> · <span_count> spans"` (e.g. `"processed · 12 spans"`) in small secondary text

The active (selected) task row SHALL be highlighted with a left border in the primary color and a soft primary-tinted background. Selecting a task SHALL load that document into the document viewer and reset span state.

For `tenant_admin` users, the Task Queue panel header area SHALL include a "＋ Assign Task" button above the task list. Clicking this button SHALL open the inline task assignment form (see task-assignment-ui spec). The button SHALL NOT be rendered for `annotator` role users.

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

#### Scenario: Tenant admin sees Assign Task button

- **GIVEN** an authenticated `tenant_admin` user is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** a "＋ Assign Task" button SHALL appear above the task list in the Task Queue panel

#### Scenario: Annotator does not see Assign Task button

- **GIVEN** an authenticated `annotator` user is on the annotation workspace
- **WHEN** the Task Queue panel renders
- **THEN** the "＋ Assign Task" button SHALL NOT appear in the Task Queue panel

### Requirement: Document Viewer and Token Rendering

The workspace SHALL render the active document's text as a sequence of word tokens in a flex-wrapped container. The token area SHALL be wrapped in a paper-like card surface (`border: 1px solid var(--line)`, `border-radius: 16px`, `padding: 36px 40px`, `box-shadow: var(--shadow)`) with a maximum width of `680px` centered within the document column. Token line height SHALL be `2.05` to provide visual breathing room between lines. Tokens belonging to confirmed spans SHALL be highlighted with the entity type's assigned color. Tokens belonging to suggested spans SHALL be highlighted with a dashed-border overlay in a muted variant of the entity type's color. The token rendering SHALL support documents up to 1,000 words without layout jank, using CSS `flex-wrap` token layout (not a virtualized list).

#### Scenario: Document renders inside a card container

- **GIVEN** a task is selected and the document text is loaded
- **WHEN** the document viewer renders
- **THEN** the token content SHALL appear inside a card element with `border-radius: 16px` and box shadow
- **AND** the card SHALL be centered with `max-width: 680px`

#### Scenario: Confirmed span tokens are highlighted

- **GIVEN** a document with text "Acme Corp hired John Doe" and confirmed spans for "Acme Corp" (ORG) and "John Doe" (PER)
- **WHEN** the document viewer renders
- **THEN** the tokens "Acme" and "Corp" SHALL render with the ORG entity type color background
- **AND** the tokens "John" and "Doe" SHALL render with the PER entity type color background

#### Scenario: Suggested span tokens show dashed overlay

- **GIVEN** a document with a suggested span for "Acme Corp" (ORG) from pre-labeling
- **WHEN** the document viewer renders
- **THEN** the tokens "Acme" and "Corp" SHALL render with a dashed border in a muted ORG color
- **AND** confirmed spans, if any overlap, SHALL take visual precedence over suggestions

#### Scenario: Unannotated tokens render without highlight

- **GIVEN** a document token "hired" that does not belong to any confirmed or suggested span
- **WHEN** the document viewer renders
- **THEN** the token SHALL render with the default `var(--color-text-primary)` color and no background highlight

### Requirement: Entity Type Palette and Armed Mode

The entity palette SHALL display all active entity types from `GET /api/v1/entity-types` as clickable buttons. In 3-pane mode, the palette renders as a vertical list in the right panel. In focus mode, the palette renders as a horizontal strip in the bottom-center floating pill (see Focus Mode Entity Palette). Each entity type button SHALL display: a colored dot using the entity type's assigned color, the entity type name in bold (`JetBrains Mono`), a `base: <base_type>` sub-label in small greyed text, and the confirmed span count for the active document right-aligned. Clicking an entity type button SHALL arm it. The armed entity type button SHALL receive an active border/ring highlight. Pressing `Escape` or clicking the armed button again SHALL disarm the palette.

When an entity type is armed, an **armed banner** SHALL appear below the toolbar with: a pulsing dot (`animation: pulse 1.3s infinite`), the instructional text `"Labeling mode · click words to tag as <entity_name>"`, and an "esc · done" text button on the right to disarm. The banner SHALL use `background: var(--primary-soft)` and `border-bottom: 1px solid var(--primary-line)`.

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
- **AND** the banner SHALL contain text "Labeling mode · click words to tag as vendor_name"
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

### Requirement: Token-Click Span Creation

When an entity type is armed, clicking any document token SHALL create a single-token confirmed span via `POST /api/v1/documents/{id}/spans`. The span's `char_start` and `char_end` SHALL be derived from the token's position in the document text using whitespace-split tokenization. Span creation SHALL be optimistic — the token SHALL highlight immediately without waiting for the API response. If the API returns an error, the optimistic highlight SHALL be reverted and a toast SHALL display the error.

#### Scenario: Clicking a token while armed creates a span

- **GIVEN** the entity type "ORG" is armed and the document text is "Acme Corp hired John"
- **WHEN** the user clicks the token "Acme"
- **THEN** the "Acme" token SHALL immediately highlight with the ORG color (optimistic)
- **AND** a `POST /documents/{id}/spans` request SHALL be sent with `{entity_type: "ORG", char_start: 0, char_end: 4, text: "Acme"}`
- **AND** on success (201), the span ID from the response SHALL replace the optimistic placeholder

#### Scenario: Clicking an already-spanned token while armed does nothing

- **GIVEN** the entity type "PER" is armed and the token "John" is already covered by a confirmed "ORG" span
- **WHEN** the user clicks "John"
- **THEN** no span creation request SHALL be sent
- **AND** the token color SHALL remain the existing ORG color

#### Scenario: API error reverts optimistic span

- **GIVEN** "ORG" is armed and the user clicks a token
- **WHEN** the `POST /documents/{id}/spans` request returns a 4xx or 5xx error
- **THEN** the optimistic token highlight SHALL be removed
- **AND** a toast SHALL display the error message

#### Scenario: Clicking a token while no type is armed opens the span inspector

- **GIVEN** no entity type is armed and the user clicks a token that belongs to a confirmed span
- **WHEN** the token is clicked
- **THEN** the span inspector SHALL open for that span (see Span Inspector requirement)

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

### Requirement: Task Status Lifecycle

Selecting a task in the annotation workspace SHALL open it in the `in-progress` state. When a task with status `unannotated` is selected, the workspace SHALL send `PATCH /annotation-tasks/{id}` with `{status: "in-progress"}`, at most once per task per browser session (idempotency guard). Tasks already in `in-progress` or `completed` SHALL NOT trigger a status request on selection.

The `completed` state SHALL be terminal in the UI. The workspace SHALL NOT provide any control that transitions a task out of `completed`. A completed task SHALL remain viewable, and — while span editing is permitted — editable, with further edits re-submitted through the "Mark as Completed" action (see Annotation Action Bar requirement).

Span creation, drag selection, and suggestion promotion SHALL NOT send status transition requests, since the transition now happens on task open.

#### Scenario: Opening an unannotated task promotes it to in-progress

- **GIVEN** a task with status `unannotated`
- **WHEN** the user selects that task in the task queue
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the status badge in the toolbar SHALL read "in_progress"

#### Scenario: In-progress transition fires only once per session

- **GIVEN** a task with status `unannotated`
- **WHEN** the user selects the task, switches to another task, and selects it again in the same browser session
- **THEN** the `PATCH` in-progress request SHALL be sent exactly once

#### Scenario: Opening a completed task sends no status request

- **GIVEN** a task with status `completed`
- **WHEN** the user selects that task in the task queue
- **THEN** no `PATCH /annotation-tasks/{id}` request SHALL be sent
- **AND** the status badge SHALL read "completed"
- **AND** the document and its confirmed spans SHALL render normally

#### Scenario: Creating a span does not send a status request

- **GIVEN** an active task already in status `in-progress`
- **WHEN** the user creates a confirmed span via token click, drag, or suggestion promotion
- **THEN** the span request SHALL be sent
- **AND** no `PATCH /annotation-tasks/{id}` status request SHALL accompany it

### Requirement: Annotation Action Bar

The annotation workspace SHALL render an action bar pinned to the bottom of the workspace, spanning the full width below the document and side panels. The action bar SHALL contain a save/status indicator on the left and a primary "Mark as Completed" button on the right.

The save indicator SHALL communicate that span edits persist automatically (e.g. "All changes saved" once the last span request has settled, "Saving…" while a span request is in flight).

Clicking "Mark as Completed" SHALL wait for any in-flight span request to settle, then send `PATCH /api/v1/annotation-tasks/{id}` with `{status: "completed"}`. While the request is in flight the button SHALL be disabled and show a pending label. On success (200) the status badge SHALL read "completed", the task queue row SHALL reflect the new status, and a success toast SHALL be shown. On a 4xx or 5xx response the task status SHALL be left unchanged and a toast SHALL display the error message from the response body.

The button SHALL be rendered and enabled for a `completed` task as well, so that later edits can be re-submitted; re-completing an already `completed` task SHALL succeed without error.

When no task is selected the action bar SHALL render with the "Mark as Completed" button disabled.

#### Scenario: Action bar renders at the bottom of the workspace

- **GIVEN** a task is selected
- **WHEN** the annotation workspace renders
- **THEN** an action bar SHALL be present at the bottom of the workspace
- **AND** it SHALL contain a save indicator and a "Mark as Completed" button

#### Scenario: Mark as Completed completes the task

- **GIVEN** an active task with status `in-progress` and at least one confirmed span
- **WHEN** the user clicks "Mark as Completed"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the button SHALL be disabled while the request is in flight
- **AND** on success (200) the toolbar status badge SHALL read "completed"
- **AND** a success toast SHALL be shown

#### Scenario: Completing with no spans surfaces the error and keeps the task in-progress

- **GIVEN** an active task with status `in-progress` and zero confirmed spans
- **WHEN** the user clicks "Mark as Completed"
- **THEN** the API SHALL return 422
- **AND** the status badge SHALL still read "in_progress"
- **AND** a toast SHALL display the error message from the API response
- **AND** the "Mark as Completed" button SHALL become enabled again

#### Scenario: Re-completing an already completed task saves further edits

- **GIVEN** a task with status `completed` that the user has re-opened and edited
- **WHEN** the user clicks "Mark as Completed"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** the response SHALL have status 200
- **AND** no "Cannot transition" error SHALL be shown

#### Scenario: Action bar disabled with no task selected

- **GIVEN** no task is selected in the task queue
- **WHEN** the annotation workspace renders
- **THEN** the "Mark as Completed" button SHALL be disabled
- **AND** clicking it SHALL send no request

### Requirement: Span Deselection

The workspace SHALL allow the user to deselect the currently selected span (close the span inspector) by clicking any document token that is not covered by a confirmed span, provided no entity type is currently armed.

#### Scenario: Clicking an unannotated token closes the span inspector

- **GIVEN** the span inspector is open for a confirmed span and no entity type is armed
- **WHEN** the user clicks a token that does not belong to any confirmed span
- **THEN** the span inspector SHALL close
- **AND** no span creation or modification request SHALL be sent

#### Scenario: Clicking unannotated token while armed does not deselect

- **GIVEN** an entity type is armed and the span inspector is open
- **WHEN** the user clicks an unannotated token
- **THEN** span creation SHALL proceed (armed behavior takes priority)
- **AND** the inspector SHALL remain open if the span creation fails

### Requirement: Char-Offset to Token-Index Conversion

The workspace SHALL perform all char-offset ↔ token-index conversions client-side. Tokenization SHALL split document text on whitespace (identical to the backend's export tokenizer). Given a flat list of confirmed spans (with `char_start`, `char_end`), the frontend SHALL determine which token indices each span covers. Given a token click, the frontend SHALL compute `char_start` as the sum of lengths of all preceding tokens plus the number of preceding spaces, and `char_end` as `char_start + token.length`.

#### Scenario: Token index maps to correct char offsets

- **GIVEN** document text "Hello World Foo" (tokens: ["Hello", "World", "Foo"] at indices 0, 1, 2)
- **WHEN** the user clicks token index 1 ("World")
- **THEN** the computed `char_start` SHALL be 6
- **AND** the computed `char_end` SHALL be 11

#### Scenario: Multi-token span covers correct token range

- **GIVEN** a confirmed span with `char_start: 0, char_end: 11` on text "Hello World Foo"
- **WHEN** the document viewer maps span to token indices
- **THEN** token 0 ("Hello") and token 1 ("World") SHALL be highlighted
- **AND** token 2 ("Foo") SHALL not be highlighted
