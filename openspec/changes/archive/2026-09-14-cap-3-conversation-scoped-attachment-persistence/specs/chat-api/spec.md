## ADDED Requirements

### Requirement: Attachment-bearing chat turns

The system SHALL accept a chat turn that includes message text and staged attachment payloads in the same request. When the request does not reference an existing conversation, the system SHALL create the conversation as part of that send and SHALL persist the attachment metadata with that conversation id.

#### Scenario: First send creates the conversation and stores attachments

- **GIVEN** a user has staged one or more attachments and has not yet created a conversation
- **WHEN** the user sends the first chat message with those attachments
- **THEN** the system SHALL create the conversation
- **AND** the system SHALL persist the attachment metadata against that conversation id

### Requirement: Conversation-scoped attachment retrieval

The system SHALL return attachments only for the conversation requested by the user. Attachments that belong to a different conversation SHALL not be returned when another conversation is opened.

#### Scenario: Another conversation does not see the attachments

- **GIVEN** a user has uploaded attachments to conversation A
- **WHEN** the user opens conversation B
- **THEN** the attachments from conversation A SHALL not be returned in conversation B

### Requirement: Text-only chat sends remain supported

The system SHALL continue to accept chat turns that contain no attachments. Existing text-only send behavior SHALL remain unchanged for those requests.

#### Scenario: Normal message without attachments still works

- **GIVEN** a user sends a chat message with no staged files
- **WHEN** the request reaches the chat endpoint
- **THEN** the existing text-only chat path SHALL continue to work
