## MODIFIED Requirements

### Requirement: Document Upload Zone

The system SHALL render a drag-drop upload zone at the top of the `/documents` page. The zone SHALL accept one or more files via drag-and-drop (on a `<div>` with `onDragOver` / `onDrop` handlers, reading every entry of `dataTransfer.files`) and via click-to-browse (hidden `<input type="file" multiple>`). The zone SHALL validate each selected file independently, and SHALL reject a file whose MIME type is not one of `application/pdf`, `image/jpeg`, `image/png`, `image/tiff` — showing an inline per-file error message for that file before any API call for it. The zone SHALL reject any file larger than 50MB client-side with an inline per-file error. Rejecting one file SHALL NOT prevent the remaining valid files in the same selection from uploading. The zone SHALL accept at most 20 files per selection; a selection exceeding 20 files SHALL be rejected in full with an inline error and SHALL trigger no API call. On valid file selection, the system SHALL upload the valid files sequentially — one in-flight request at a time — each via `POST /api/v1/documents` using `XMLHttpRequest`, applying the currently selected `purpose` (query or training) to every file in the selection.

#### Scenario: Drag a single valid PDF onto the zone

- **GIVEN** the `/documents` page is open
- **WHEN** the user drags a PDF file over the zone and drops it
- **THEN** the file is accepted
- **AND** `POST /api/v1/documents` is called with the file as multipart/form-data
- **AND** a new row appears in the document table with `status: "pending"`

#### Scenario: Drag three valid files onto the zone

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops a PDF, a PNG, and a TIFF onto the zone in one drop
- **THEN** all three files are accepted
- **AND** `POST /api/v1/documents` is called three times, one request at a time with no two requests in flight simultaneously
- **AND** three new rows appear in the document table with `status: "pending"`

#### Scenario: Click to browse and multi-select files

- **GIVEN** the `/documents` page is open
- **WHEN** the user clicks the upload zone
- **AND** selects two PNG files from the file picker
- **THEN** both files are uploaded sequentially
- **AND** two new rows appear with `status: "pending"`

#### Scenario: Click to browse and select a single valid PNG

- **GIVEN** the `/documents` page is open
- **WHEN** the user clicks the upload zone
- **AND** selects one PNG file from the file picker
- **THEN** the file is uploaded immediately
- **AND** a new row appears with `status: "pending"`

#### Scenario: Drop an unsupported file type

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops a `.exe` file onto the zone
- **THEN** an inline error message is shown for that file stating the file type is not supported
- **AND** no API call is made

#### Scenario: Drop a mixed batch of valid and invalid files

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops one valid PDF, one `.exe`, and one 100MB PDF in a single drop
- **THEN** the `.exe` shows an inline "not supported" error and the 100MB PDF shows an inline "exceeds the 50MB limit" error
- **AND** the valid PDF is still uploaded via `POST /api/v1/documents`
- **AND** exactly one API call is made

#### Scenario: Drop a file exceeding 50MB

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops a 100MB file onto the zone
- **THEN** an inline error message is shown stating the file exceeds the 50MB limit
- **AND** no API call is made

#### Scenario: Selection exceeds the 20-file cap

- **GIVEN** the `/documents` page is open
- **WHEN** the user drops 25 valid PDF files in a single drop
- **THEN** an inline error message is shown stating at most 20 files may be uploaded at once
- **AND** no API call is made for any file in the selection

#### Scenario: Purpose applies to every file in the batch

- **GIVEN** the `/documents` page is open with `purpose` set to "training"
- **WHEN** the user drops three valid files
- **THEN** each `POST /api/v1/documents` request carries `purpose: "training"` in its form data

#### Scenario: Drag-over visual state change

- **GIVEN** the upload zone is idle
- **WHEN** the user drags a file over the zone (`onDragOver`)
- **THEN** the zone border changes to a highlighted state (e.g. primary colour, dashed border)
- **AND** the visual state returns to idle on `onDragLeave` or on drop

---

### Requirement: Upload Progress Bar

The system SHALL show upload progress while files are being uploaded. For the file currently in flight, the progress bar SHALL use the `XMLHttpRequest.upload.onprogress` event to compute `(loaded / total) * 100` and display the percentage visually. When a selection contains more than one valid file, the system SHALL additionally display the batch position of the in-flight file as "file N of M" alongside the filename. On successful upload of each file, the system SHALL invalidate the document list query so the table refreshes progressively during the batch. A failed file SHALL NOT abort the batch: the system SHALL record the failure with its filename and reason and SHALL continue with the next queued file. When the batch finishes, the system SHALL show a summary reporting the count of succeeded and failed files, listing each failed filename with its reason.

#### Scenario: Upload progress updates in real time

- **GIVEN** a file is being uploaded via `XMLHttpRequest`
- **WHEN** the upload progresses
- **THEN** the progress bar fills proportionally to the percentage of bytes transmitted
- **AND** the percentage text is shown alongside the bar

#### Scenario: Batch position is shown during a multi-file upload

- **GIVEN** a batch of 3 valid files is uploading and the second file is in flight
- **WHEN** the progress area renders
- **THEN** it shows the in-flight filename and a "file 2 of 3" indicator
- **AND** the progress bar reflects only the in-flight file's byte progress

#### Scenario: Single-file upload shows no batch position

- **GIVEN** a batch of exactly 1 valid file is uploading
- **WHEN** the progress area renders
- **THEN** the progress bar and percentage are shown
- **AND** no "file N of M" indicator is shown

#### Scenario: Upload completes

- **GIVEN** a single-file upload reaches 100%
- **WHEN** the server responds with HTTP 201
- **THEN** the progress bar is replaced by a success indicator
- **AND** the document list query is invalidated to refresh the table

#### Scenario: One file fails mid-batch

- **GIVEN** a batch of 3 valid files is uploading
- **WHEN** the second file's request returns HTTP 500
- **THEN** the third file is still uploaded
- **AND** the batch summary reports 2 succeeded and 1 failed
- **AND** the failed filename is listed with the server's error reason

#### Scenario: Batch summary after all files succeed

- **GIVEN** a batch of 3 valid files
- **WHEN** all three requests return HTTP 201
- **THEN** the summary reports 3 succeeded and 0 failed
- **AND** the document list query has been invalidated for each successful file

---

## ADDED Requirements

### Requirement: Cancel an In-Progress Batch

The system SHALL offer a cancel control while a multi-file batch is uploading. Activating it SHALL abort the in-flight `XMLHttpRequest` and SHALL skip all files still queued. Documents already uploaded successfully in that batch SHALL NOT be rolled back or deleted. After cancelling, the system SHALL show a summary reporting how many files succeeded and how many were cancelled, and the zone SHALL return to an idle state ready to accept a new selection.

#### Scenario: Cancel a batch after the first file succeeds

- **GIVEN** a batch of 5 valid files is uploading and file 1 has completed with HTTP 201
- **WHEN** the user activates the cancel control while file 2 is in flight
- **THEN** file 2's `XMLHttpRequest` is aborted
- **AND** files 3, 4, and 5 are never sent
- **AND** the summary reports 1 succeeded and 4 cancelled
- **AND** the row for file 1 remains in the document table

#### Scenario: Zone accepts a new selection after cancel

- **GIVEN** a batch was cancelled mid-upload
- **WHEN** the user drops a new valid PDF onto the zone
- **THEN** the previous batch's progress and summary state is cleared
- **AND** the new file uploads normally
