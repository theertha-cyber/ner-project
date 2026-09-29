## ADDED Requirements

### Requirement: Uploaded files section

The `/settings/data-sources` route SHALL show an "Uploaded files" section, separate from the connection collection, listing the tenant's files that are not deleted. Each entry SHALL show display name, served version, status label (`profiling`, `needs_review`, `ready`, `failed`), row count when known, and last update. When a newer version is in review, the entry SHALL show both the served version and the pending version. The section SHALL be visible only to tenant administrators and SHALL present loading, empty and safe error states. An "Upload file" control SHALL accept `.csv` and `.xlsx` only. The control SHALL show the 100 MB and 20-file limits, and SHALL surface `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE` and `FILE_LIMIT_REACHED` as fixed messages.

#### Scenario: Administrator sees uploaded files

- **GIVEN** a tenant administrator whose tenant has `sales_q3` (`ready`, v1) and `targets` (`needs_review`, v1)
- **WHEN** the administrator opens `/settings/data-sources`
- **THEN** the "Uploaded files" section SHALL list both with their status labels, separate from connections

#### Scenario: Pending version shown alongside served version

- **GIVEN** `sales_q3` v1 is `ready` and v2 is `needs_review`
- **WHEN** the section renders
- **THEN** the entry SHALL show v1 as served and v2 as pending review

#### Scenario: Unsupported file is refused with a fixed message

- **GIVEN** a tenant administrator using "Upload file"
- **WHEN** the server responds `UNSUPPORTED_FILE_TYPE`
- **THEN** the portal SHALL show the fixed unsupported-type message and SHALL NOT add a list entry

### Requirement: File review interface

For a file in `needs_review` the portal SHALL provide a review screen showing, for each column:
- original header and editable identifier
- inferred type with a type selector
- date-format selector when relevant
- warnings and null and distinct counts
- a value-hint list with approve controls
- a description field and an exclude toggle

The screen SHALL also offer table-description and null-token fields, the load report (rows read, to load, rejected, with reasons for the first 100 rejects), a 20-row typed preview, and, for a version greater than 1, the schema diff against the served version. The publish control SHALL be disabled, with the blocking reasons listed, while any publish-gate condition is unmet.

#### Scenario: Review shows blocking reasons

- **GIVEN** a profile with a column marked `date_format_required` and no table description
- **WHEN** the administrator opens the review screen
- **THEN** publish SHALL be disabled and both blocking reasons SHALL be listed

#### Scenario: Type change refreshes the load report

- **GIVEN** the review screen for `sales_q3`
- **WHEN** the administrator changes `amount` from `text` to `numeric`
- **THEN** the portal SHALL request the recomputed load report and display the new rejected-row count

#### Scenario: Successful publish returns to the list

- **GIVEN** a review with no blocking reasons
- **WHEN** the administrator publishes
- **THEN** the portal SHALL send the publish request with a fresh `Idempotency-Key` and, on success, show the file as `ready` in the "Uploaded files" section

### Requirement: File replace and delete controls

Each file entry SHALL offer "Upload new version" and "Delete". Delete SHALL require explicit confirmation naming the file and stating that chat will stop using it immediately.

#### Scenario: Delete requires confirmation

- **GIVEN** a `ready` file entry
- **WHEN** the administrator activates "Delete"
- **THEN** the portal SHALL show a confirmation naming the file, and SHALL send the delete request only after confirmation
