## MODIFIED Requirements

### Requirement: Attachment-bearing chat turns

The system SHALL accept a chat turn that includes message text and the attached files' content in the same request, transported as `multipart/form-data`. When the request does not reference an existing conversation, the system SHALL create the conversation as part of that send and SHALL record every attachment as owned by that conversation id. Each attachment SHALL be ingested through the document ingestion service — the single code path permitted to create a document row — so that it acquires a content-store write, checksum, retention resolution, text extraction, chunking and embeddings like any other document. The system SHALL NOT insert an attachment's document row directly.

#### Scenario: First send creates the conversation and stores attachments

- **GIVEN** a user has staged one or more attachments and has not yet created a conversation
- **WHEN** the user sends the first chat message with those attachments
- **THEN** the system SHALL create the conversation
- **AND** the system SHALL persist each attachment as a document owned by that conversation id

#### Scenario: An attachment is ingested rather than inserted directly

- **GIVEN** a chat turn carrying one attachment
- **WHEN** the send is processed
- **THEN** the attachment SHALL be ingested through the document ingestion service
- **AND** the stored document row SHALL carry a checksum, a content-store reference, and a resolved retention mode
- **AND** the chat endpoint SHALL NOT execute its own insert into the documents table

#### Scenario: An unsupported attachment type is rejected

- **GIVEN** a chat turn carrying a file whose extension is outside the ingestion allow-list
- **WHEN** the send is processed
- **THEN** the system SHALL reject the request with a client error naming the unsupported type
- **AND** the system SHALL NOT create a conversation for a first send that was rejected

### Requirement: Text-only chat sends remain supported

The system SHALL continue to accept chat turns that contain no attachments, using the existing JSON request body. Existing text-only send behavior SHALL remain unchanged for those requests, on both the streaming and non-streaming endpoints. The endpoint SHALL select its request handling from the request's content type, so that a text-only send is byte-for-byte the request it was before this change.

#### Scenario: Normal message without attachments still works

- **GIVEN** a user sends a chat message with no staged files
- **WHEN** the request reaches the chat endpoint
- **THEN** the existing text-only chat path SHALL continue to work

#### Scenario: A JSON send is handled as it was before this change

- **GIVEN** a chat request with a JSON content type and no attachment parts
- **WHEN** the request reaches either the streaming or the non-streaming endpoint
- **THEN** the system SHALL parse it as the existing JSON chat request
- **AND** no ingestion SHALL be attempted for that turn

## ADDED Requirements

### Requirement: Attachments are indexed before the turn is answered

The system SHALL complete each attachment's processing — extraction, chunking, and embedding — before running retrieval for the turn that carried it, so the same message that supplies a document can be answered from that document. If an attachment's processing fails or exceeds a bounded wait, the system SHALL answer the turn without it and SHALL tell the user that the attachment was not available to the answer, rather than failing the turn silently or reporting success.

#### Scenario: The same turn can answer from its own attachment

- **GIVEN** a user attaches a job description and asks a question about it in the same send
- **WHEN** the turn is answered
- **THEN** retrieval for that turn SHALL be able to return chunks derived from that attachment
- **AND** the answer SHALL be able to cite it

#### Scenario: A failed attachment does not silently degrade the answer

- **GIVEN** a chat turn carrying an attachment whose processing fails
- **WHEN** the turn is answered
- **THEN** the response SHALL indicate that the attachment was not available to the answer
- **AND** the turn SHALL still produce an answer from the remaining available context

#### Scenario: Attachment processing that exceeds the bounded wait degrades gracefully

- **GIVEN** a chat turn carrying an attachment whose processing does not finish within the bounded wait
- **WHEN** the wait elapses
- **THEN** the system SHALL proceed to answer the turn
- **AND** the response SHALL indicate that the attachment was not available to the answer

### Requirement: Attachment content is retrievable only within its own conversation

An attachment's indexed content SHALL be retrievable while answering turns in the conversation that owns it, and SHALL NOT be retrievable while answering turns in any other conversation of the same tenant. This restriction SHALL be enforced from the request's conversation context, not from the user's message text or a model-selected retrieval argument.

#### Scenario: A job description attached in one session does not answer another session

- **GIVEN** a user attached a job description in conversation A and received an answer citing it
- **WHEN** the same user opens conversation B and asks a question whose text matches that job description
- **THEN** the answer in conversation B SHALL NOT cite or draw on that attachment

#### Scenario: Tenant library documents remain answerable in every conversation

- **GIVEN** a tenant library document that is not owned by any conversation
- **WHEN** a matching question is asked in any conversation
- **THEN** the answer SHALL be able to cite that library document
