## ADDED Requirements

### Requirement: Document Upload Zone

The system SHALL render a drag-drop upload zone at the top of the `/documents` page. The zone SHALL accept files via drag-and-drop (on a `<div>` with `onDragOver` / `onDrop` handlers) and via click-to-browse (hidden `<input type="file">`). The zone SHALL validate file types client-side and reject files whose MIME type is not one of `application/pdf`, `image/jpeg`, `image/png`, `image/tiff` — showing an inline error message before any API call. The zone SHALL reject files larger than 50MB client-side with an inline error. On valid file selection, the system SHALL immediately upload the file via `POST /api/v1/documents` using `XMLHttpRequest`.

#### Scenario: Drag a valid PDF onto the zone

- **GIVEN** the `/documents` page is open
- **WHEN** the user drags a PDF file over the zone and drops it
- **THEN** the file is accepted
- **AND** `POST /api/v1/documents` is called with the file as multipart/form-data
- **AND** a new row appears in the document table with `status: "pending"`

#### Scenario: Click to browse and select a valid PNG

- **GIVEN** the `/documents` page is open
- **WHEN** the user clicks the upload zone
- **AND** selects a PNG file from the file picker
- **THEN** the file is uploaded immediately
- **AND** a new row appears with `status: "pending"`

#### Scenario: Drop an unsupported file type

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops a `.exe` file onto the zone
- **THEN** an inline error message is shown stating the file type is not supported
- **AND** no API call is made

#### Scenario: Drop a file exceeding 50MB

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops a 100MB file onto the zone
- **THEN** an inline error message is shown stating the file exceeds the 50MB limit
- **AND** no API call is made

#### Scenario: Drag-over visual state change

- **GIVEN** the upload zone is idle
- **WHEN** the user drags a file over the zone (`onDragOver`)
- **THEN** the zone border changes to a highlighted state (e.g. primary colour, dashed border)
- **AND** the visual state returns to idle on `onDragLeave` or on drop

---

### Requirement: Upload Progress Bar

The system SHALL show a progress bar while a file is being uploaded. The progress bar SHALL use the `XMLHttpRequest.upload.onprogress` event to compute `(loaded / total) * 100` and display the percentage visually.

#### Scenario: Upload progress updates in real time

- **GIVEN** a file is being uploaded via `XMLHttpRequest`
- **WHEN** the upload progresses
- **THEN** the progress bar fills proportionally to the percentage of bytes transmitted
- **AND** the percentage text is shown alongside the bar

#### Scenario: Upload completes

- **GIVEN** a file upload reaches 100%
- **WHEN** the server responds with HTTP 201
- **THEN** the progress bar is replaced by a success indicator
- **AND** the document list query is invalidated to refresh the table

---

### Requirement: Document Table

The system SHALL render a paginated table of documents below the upload zone. The table SHALL show columns: filename, content type, file size (human-readable: KB/MB), status badge, created date (formatted), and delete action. The table SHALL use offset-based pagination with previous/next controls. Default `per_page` SHALL be 25.

#### Scenario: Table renders with correct columns

- **GIVEN** the tenant has documents in the system
- **WHEN** the document list loads
- **THEN** the table shows columns: Filename, Type, Size, Status, Created, Delete
- **AND** each row corresponds to a document from the API response

#### Scenario: Pagination next/previous

- **GIVEN** the tenant has 30 documents with default per_page of 25
- **WHEN** the table renders
- **THEN** only the first 25 documents are shown on page 1
- **AND** a "Next" control is visible
- **WHEN** the user clicks "Next"
- **THEN** the remaining 5 documents are shown on page 2
- **AND** a "Previous" control is now visible

#### Scenario: Empty state

- **GIVEN** the tenant has no documents
- **WHEN** the document list loads
- **THEN** the table shows an empty state message: "No documents yet — upload your first document"
- **AND** the upload zone remains visible above

#### Scenario: Loading state shows skeleton rows

- **GIVEN** the document query is in-flight
- **WHEN** the table renders
- **THEN** skeleton placeholder rows (3–5, `animate-pulse`) are shown instead of the table body
- **AND** no spinner or full-page loader is shown

---

### Requirement: Status Filter Tabs

The system SHALL render a row of filter tabs above the document table: All, Pending, Processing, Processed, Failed. Each tab SHALL show the count of documents in that status. Clicking a tab SHALL filter the table to show only documents matching that status. The active tab SHALL be visually distinguished.

#### Scenario: Click a status filter tab

- **GIVEN** the document table shows all documents (All tab active)
- **WHEN** the user clicks the "Processed" tab
- **THEN** the table refetches with `?status=processed`
- **AND** only documents with `status: "processed"` are shown
- **AND** the "Processed" tab is visually active

#### Scenario: Filter tab shows document counts

- **GIVEN** the tenant has 5 processed and 2 pending documents
- **WHEN** the filter tabs render
- **THEN** the "Processed" tab displays a count of 5
- **AND** the "Pending" tab displays a count of 2

---

### Requirement: Status Badge

Each document row SHALL render a status badge matching the mockup's colour convention. The badge SHALL be one of: `pending` (amber), `processing` (blue/pulse), `processed` (green), `failed` (red), `deleted` (grey/muted). The badge SHALL use the shared `<Badge>` primitive from SP-01. A `processing` badge SHALL show an animated pulse dot.

#### Scenario: Processing badge shows pulse animation

- **GIVEN** a document with `status: "processing"`
- **WHEN** its row renders
- **THEN** the badge shows a pulse animation (matching mockup's `pulse` keyframe)

#### Scenario: Deleted badge is visually muted

- **GIVEN** a document with `status: "deleted"`
- **WHEN** its row renders
- **THEN** the badge uses a grey/muted colour
- **AND** the row is still visible in the table (only removed when the "Deleted" filter is inactive)

---

### Requirement: Auto-Polling for In-Flight Documents

The system SHALL poll the document list endpoint every 3 seconds while any document in the visible list has `status: "pending"` or `status: "processing"`. When no documents are in-flight, polling SHALL stop. The poll SHALL be a background refetch (no loading spinner, no UI flash).

#### Scenario: Polling starts when pending document exists

- **GIVEN** the document table shows a document with `status: "pending"`
- **WHEN** 3 seconds elapse
- **THEN** `GET /api/v1/documents` is automatically re-fetched in the background

#### Scenario: Polling stops when all documents reach terminal state

- **GIVEN** polling is active due to a `processing` document
- **WHEN** the document transitions to `processed` (detected on the next poll)
- **THEN** polling stops on the subsequent refetch cycle

---

### Requirement: Soft Delete

The system SHALL allow soft-deleting a document via a delete action per row (icon button). On click, the system SHALL call `DELETE /api/v1/documents/{id}`, which sets `status: "deleted"`. After deletion, the row SHALL update to show the `deleted` badge. If the active filter is not "Deleted" or "All", the row SHALL slide out of the visible list after a brief delay.

#### Scenario: Delete a document from a filtered list

- **GIVEN** a document with `status: "processed"` is visible when the "Processed" filter is active
- **WHEN** the user clicks the delete action on that row
- **THEN** `DELETE /api/v1/documents/{id}` is called
- **AND** the row slides out (CSS transition) from the visible list after the response
- **AND** a success toast is shown

#### Scenario: Delete a document when "All" filter is active

- **GIVEN** a document with `status: "processed"` is visible when the "All" filter is active
- **WHEN** the user clicks the delete action on that row
- **THEN** `DELETE /api/v1/documents/{id}` is called
- **AND** the row remains visible with the `deleted` badge
