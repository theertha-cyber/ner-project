## MODIFIED Requirements

### Requirement: Attachment-bearing send interaction

The chat page SHALL submit the staged attachments' file content together with the message in the same send action, transported as `multipart/form-data`. The send control SHALL remain keyboard accessible and expose an accessible name. The composer SHALL clear the staged attachment tray after a successful send and SHALL preserve staged attachments when the send fails.

#### Scenario: Send a message with staged attachments

- **GIVEN** a user has one or more files staged in the attachment tray and has typed a message
- **WHEN** the user sends the message
- **THEN** the page SHALL pass the message and each staged file's content together to the chat backend in the same request
- **AND** the composer SHALL clear the staged attachment tray after a successful send

#### Scenario: Failed send preserves staged attachments

- **GIVEN** a user has staged files and sends a message
- **WHEN** the send fails
- **THEN** the staged files SHALL remain in the tray
- **AND** the user SHALL be shown an error

#### Scenario: A text-only send carries no attachment parts

- **GIVEN** a user has typed a message and staged no files
- **WHEN** the user sends the message
- **THEN** the page SHALL send the existing JSON request body unchanged
- **AND** the request SHALL NOT be sent as `multipart/form-data`

## ADDED Requirements

### Requirement: The composer reports attachment send progress

While an attachment-bearing send is in flight, the composer SHALL indicate that the attached files are being uploaded and prepared, and SHALL keep the send control disabled for the duration. When the send completes successfully the indication SHALL be removed along with the tray. When the send fails, the composer SHALL surface the failure and keep the staged files so the user can retry without re-picking them.

#### Scenario: An in-flight attachment send shows progress

- **GIVEN** a user sends a message with one or more staged files
- **WHEN** the request is in flight
- **THEN** the composer SHALL show that the attachments are being uploaded and prepared
- **AND** the send control SHALL be disabled

#### Scenario: A failed attachment send keeps the files and reports why

- **GIVEN** an attachment-bearing send that fails
- **WHEN** the failure is received
- **THEN** the composer SHALL surface the failure to the user
- **AND** every staged file SHALL remain in the tray
- **AND** the send control SHALL become operable again

#### Scenario: The user is told when an attachment could not be used

- **GIVEN** a send whose response reports that an attachment was not available to the answer
- **WHEN** the response is rendered
- **THEN** the user SHALL be shown that the attachment was not used for that answer
