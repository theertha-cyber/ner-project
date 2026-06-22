# Portal Annotation Workspace

## Purpose

Frontend annotation workspace at `/annotation` for annotators and tenant admins to perform document labeling, manage annotation tasks, and trigger pre-labeling.

---

## Requirements

### Requirement: Layout and Navigation

The annotation workspace SHALL render at `/annotation` inside the authenticated app shell. The workspace SHALL support two layout modes: **3-pane** (default) with a fixed-width task queue on the left, a scrollable document viewer in the center, and a fixed-width entity palette on the right; and **focus mode** where the task queue is hidden and the entity palette becomes a floating `position: fixed` panel. The selected layout mode SHALL be persisted to `localStorage` under the key `"ner-annotation-layout"`.

#### Scenario: Default layout renders three columns

- **GIVEN** an authenticated annotator navigates to `/annotation`
- **WHEN** the page mounts for the first time (no localStorage preference)
- **THEN** the workspace SHALL render with a task queue column, a document viewer column, and an entity palette column visible simultaneously
- **AND** the layout mode toggle SHALL show "3-pane" as the active option

#### Scenario: Focus mode hides queue and floats palette

- **GIVEN** the annotation workspace is in 3-pane mode
- **WHEN** the user switches the layout toggle to "Focus"
- **THEN** the task queue column SHALL be hidden
- **AND** the entity palette SHALL render as a `position: fixed` panel at `top: 140px; right: 30px`
- **AND** the document viewer SHALL expand to fill the full available width
- **AND** the layout preference SHALL be written to `localStorage`

#### Scenario: Layout preference is restored on reload

- **GIVEN** the user previously selected "Focus" mode (stored in `localStorage`)
- **WHEN** the user navigates to `/annotation`
- **THEN** the workspace SHALL render in focus mode without requiring re-selection

### Requirement: Annotation Task Queue

The workspace SHALL display a list of annotation tasks from `GET /api/v1/annotation-tasks` in the left queue panel. For `annotator` users the list SHALL show only tasks assigned to the current user. For `tenant_admin` users the list SHALL show all tasks for the tenant. Each task row SHALL display the document filename, task status badge (`unannotated`, `in-progress`, `completed`), and be selectable. Selecting a task SHALL load that document into the document viewer and reset span state.

#### Scenario: Annotator sees only assigned tasks

- **GIVEN** an authenticated annotator user with two assigned tasks and three tasks assigned to other users
- **WHEN** the annotation workspace loads
- **THEN** the queue SHALL show exactly two task rows

#### Scenario: Tenant admin sees all tasks

- **GIVEN** an authenticated tenant_admin with five tasks across the tenant
- **WHEN** the annotation workspace loads
- **THEN** the queue SHALL show all five task rows

#### Scenario: Selecting a task loads the document

- **GIVEN** the task queue is populated with at least two tasks
- **WHEN** the user clicks the second task row
- **THEN** the document viewer SHALL load the text for that task's document via `GET /documents/{id}/text`
- **AND** the confirmed spans SHALL be fetched via `GET /documents/{id}/spans`
- **AND** the suggested spans SHALL be fetched via `GET /documents/{id}/spans?type=suggested`
- **AND** the previously active task's document SHALL be cleared from the viewer

#### Scenario: Empty queue shows contextual message

- **GIVEN** there are no annotation tasks for the current user
- **WHEN** the annotation workspace loads
- **THEN** the queue panel SHALL display "No tasks assigned" with a prompt to contact a tenant admin

### Requirement: Document Viewer and Token Rendering

The workspace SHALL render the active document's text as a sequence of word tokens in a flex-wrapped container. Tokens belonging to confirmed spans SHALL be highlighted with the entity type's assigned color. Tokens belonging to suggested spans SHALL be highlighted with a dashed-border overlay in a muted variant of the entity type's color. The token rendering SHALL support documents up to 1,000 words without layout jank, using CSS `flex-wrap` token layout (not a virtualized list).

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

The entity palette panel SHALL display all active entity types from `GET /api/v1/entity-types` as clickable chips with their assigned color and a count of confirmed spans of that type on the active document. Clicking an entity type chip SHALL arm it — setting it as the active labeling type. The armed entity type SHALL be visually emphasized (ring/border highlight). A banner SHALL appear at the top of the document viewer indicating the armed type and instructing the user to click tokens. Pressing `Escape` or clicking the armed chip again SHALL disarm the palette.

#### Scenario: Palette shows entity types with span counts

- **GIVEN** an active document with 3 confirmed "PER" spans and 1 confirmed "ORG" span
- **WHEN** the entity palette renders
- **THEN** each entity type chip SHALL display the entity type name and its confirmed span count
- **AND** PER SHALL show count 3, ORG SHALL show count 1, other types SHALL show count 0

#### Scenario: Clicking a chip arms the entity type

- **GIVEN** the entity palette is idle (no type armed)
- **WHEN** the user clicks the "PER" chip
- **THEN** the "PER" chip SHALL render with an active ring highlight
- **AND** the armed-mode banner SHALL appear above the document viewer with text indicating "PER" is armed

#### Scenario: Escape key disarms the palette

- **GIVEN** the "PER" entity type is currently armed
- **WHEN** the user presses the `Escape` key
- **THEN** the armed type SHALL be cleared
- **AND** the armed-mode banner SHALL disappear
- **AND** no token clicks SHALL create spans until a type is re-armed

#### Scenario: Clicking the armed chip again disarms it

- **GIVEN** the "PER" entity type is currently armed
- **WHEN** the user clicks the "PER" chip again
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

When a user clicks a confirmed-span token while no entity type is armed, the workspace SHALL open a span inspector panel. The inspector SHALL display the span's entity type, `char_start`, `char_end`, `text`, and `confidence` values. The inspector SHALL provide a retype action (dropdown of all entity types) that calls `PATCH /documents/{id}/spans/{span_id}` with the new entity type. The inspector SHALL provide a delete action that calls `DELETE /documents/{id}/spans/{span_id}`. Both actions SHALL update the document viewer optimistically and dismiss the inspector on success.

#### Scenario: Clicking a confirmed span opens the inspector

- **GIVEN** the document has a confirmed span "John Doe" (PER) at char offsets 10-18 and no type is armed
- **WHEN** the user clicks the token "John"
- **THEN** the span inspector SHALL open showing entity_type "PER", char_start 10, char_end 18, text "John Doe", confidence 1.0

#### Scenario: Retype updates the span entity type

- **GIVEN** the span inspector is open for span "John Doe" (PER)
- **WHEN** the user selects "ORG" from the retype dropdown and confirms
- **THEN** a `PATCH /documents/{id}/spans/{span_id}` request SHALL be sent with `{entity_type: "ORG"}`
- **AND** on success, the token highlight SHALL change to the ORG color
- **AND** the inspector SHALL close

#### Scenario: Delete removes the span

- **GIVEN** the span inspector is open for span "John Doe" (PER)
- **WHEN** the user clicks the delete button
- **THEN** a `DELETE /documents/{id}/spans/{span_id}` request SHALL be sent
- **AND** on success (204), the token highlights for "John" and "Doe" SHALL be removed
- **AND** the inspector SHALL close

### Requirement: Pre-labeling and Suggestion Flow

The workspace SHALL provide a "Pre-label" button that triggers `POST /api/v1/documents/{id}/prelabel`. On success, suggested spans SHALL be fetched and rendered with dashed-border styling in the document viewer. Each suggestion group SHALL display a "Promote" button and a "Dismiss" button in the suggestion panel. Promoting calls `POST /documents/{id}/spans/promote/{suggest_id}` and converts the suggestion to a confirmed span. Dismissing removes the suggestion from the UI without an API call (suggestions are replaced on the next pre-label call). The pre-label button SHALL be disabled while a pre-label request is in-flight.

#### Scenario: Pre-label populates the suggestion panel

- **GIVEN** an active document with no existing suggested spans
- **WHEN** the user clicks the "Pre-label" button
- **THEN** a `POST /documents/{id}/prelabel` request SHALL be sent
- **AND** on success, the returned suggested spans SHALL appear in the suggestion panel
- **AND** the corresponding tokens in the document viewer SHALL render with dashed-border styling

#### Scenario: Promote converts a suggestion to a confirmed span

- **GIVEN** a suggested span for "Acme Corp" (ORG, suggest_id "s-1") is in the suggestion panel
- **WHEN** the user clicks "Promote" on that suggestion
- **THEN** a `POST /documents/{id}/spans/promote/s-1` request SHALL be sent
- **AND** on success (201), the confirmed span SHALL replace the suggested span in the viewer
- **AND** the dashed styling SHALL change to solid ORG color
- **AND** the suggestion row SHALL be removed from the suggestion panel

#### Scenario: Dismiss removes the suggestion locally

- **GIVEN** a suggested span for "John Doe" (PER) is in the suggestion panel
- **WHEN** the user clicks "Dismiss" on that suggestion
- **THEN** the suggestion row SHALL be removed from the suggestion panel
- **AND** the dashed-border token highlight SHALL be removed from the document viewer
- **AND** no API request SHALL be sent for dismiss

#### Scenario: Pre-label button is disabled during in-flight request

- **GIVEN** a `POST /documents/{id}/prelabel` request is in-flight
- **WHEN** the pre-label button is rendered
- **THEN** the button SHALL be visually disabled and non-interactive until the request settles

### Requirement: Task Status Lifecycle

The workspace SHALL manage annotation task status transitions. When an annotator creates the first confirmed span on a task's document, the task SHALL automatically transition from `unannotated` to `in-progress` via `PATCH /annotation-tasks/{id}`. A "Mark Complete" button SHALL be visible in the workspace. Clicking it SHALL attempt to transition the task to `completed` via `PATCH /annotation-tasks/{id}`. If the document has no confirmed spans, the button SHALL be disabled with a tooltip explaining the minimum span requirement. On successful completion, the task SHALL move to the bottom of the queue (or be de-emphasized visually) and the next available task SHALL be auto-selected.

#### Scenario: First span creation triggers in-progress transition

- **GIVEN** an active task with status `unannotated` and no confirmed spans
- **WHEN** the user creates the first confirmed span
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "in-progress"}`
- **AND** the task row in the queue SHALL update its status badge to "in-progress"

#### Scenario: Mark Complete is disabled with no spans

- **GIVEN** an active task with status `in-progress` and the document has zero confirmed spans
- **WHEN** the workspace renders
- **THEN** the "Mark Complete" button SHALL be disabled
- **AND** a tooltip on hover SHALL read "Add at least one confirmed span before completing"

#### Scenario: Mark Complete transitions task to completed

- **GIVEN** an active task with status `in-progress` and the document has at least one confirmed span
- **WHEN** the user clicks "Mark Complete"
- **THEN** a `PATCH /annotation-tasks/{id}` request SHALL be sent with `{status: "completed"}`
- **AND** on success, the task status badge in the queue SHALL update to "completed"
- **AND** the next available (non-completed) task in the queue SHALL be auto-selected if one exists

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
