## ADDED Requirements

### Requirement: Chat attachment staging

The chat composer SHALL let a user stage one or more supported files without creating or reserving a conversation. The chat composer SHALL allow a user to remove a staged file before send. Supported files are `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.doc`, `.docx`, and `.csv`; files outside that set SHALL be rejected and not staged.

#### Scenario: Stage files before first send

- **GIVEN** a chat composer in a conversation (or inbox) where no message has been sent yet
- **WHEN** a user selects one or more supported files in the chat composer before sending a message
- **THEN** the files SHALL appear in a staged attachment tray
- **AND** no conversation SHALL be reserved or created until the user sends the message

#### Scenario: Remove a staged file before send

- **GIVEN** one or more files staged in the attachment tray
- **WHEN** the user activates the remove control on a staged file
- **THEN** that file SHALL be removed from the tray
- **AND** the other staged files SHALL remain staged

#### Scenario: Reject an unsupported file type

- **GIVEN** the chat composer's file input
- **WHEN** a user selects a file whose extension is not in the supported set
- **THEN** the file SHALL NOT be staged
- **AND** the user SHALL be shown an indication of the supported file set

### Requirement: Attachment-bearing send interaction

The chat page SHALL submit the staged attachments together with the message in the same send action. The send control SHALL remain keyboard accessible and expose an accessible name. The composer SHALL clear the staged attachment tray after a successful send and SHALL preserve staged attachments when the send fails.

#### Scenario: Send a message with staged attachments

- **GIVEN** a user has one or more files staged in the attachment tray and has typed a message
- **WHEN** the user sends the message
- **THEN** the page SHALL pass the message and the attachment metadata together to the chat backend in the same request
- **AND** the composer SHALL clear the staged attachment tray after a successful send

#### Scenario: Failed send preserves staged attachments

- **GIVEN** a user has staged files and sends a message
- **WHEN** the send fails
- **THEN** the staged files SHALL remain in the tray
- **AND** the user SHALL be shown an error

### Requirement: Accessible attachment control

The chat composer's attachment control SHALL be operable from the keyboard via Tab focus and Enter/Space activation, SHALL expose an accessible name, and SHALL show a visible focus state. Staged-file remove controls SHALL expose accessible names identifying the file they remove. Staged attachments SHALL NOT enable the send control when the message is still empty.

#### Scenario: Keyboard users stage and remove attachments

- **GIVEN** an attachment control in the chat composer
- **WHEN** a keyboard user tabs to the control, activates it, selects a file, and tabs to its remove control
- **THEN** each interactive control SHALL be reachable and operable without a mouse
- **AND** the attachment and remove controls SHALL expose accessible names

#### Scenario: Staged attachments do not enable send with an empty message

- **GIVEN** one or more files staged in the attachment tray and no message text
- **WHEN** the composer evaluates whether the send control is enabled
- **THEN** the send control SHALL remain disabled
- **AND** it SHALL become enabled only once message text is present (and sending is not already in progress)