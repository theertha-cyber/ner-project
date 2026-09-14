## ADDED Requirements

### Requirement: Conversation deletion hard-deletes linked attachment files and derived artefacts

When a conversation is deleted, the system SHALL hard-delete every document row linked to that conversation by `conversation_id`, together with each linked row's persisted blob, text spans, chunks, extracted entities and derived relational projection rows, before the conversation row itself is removed. Non-chat document rows SHALL NOT be affected. The delete path SHALL be idempotent and safe to retry.

#### Scenario: Delete a conversation owning attachments removes every trace

- **GIVEN** a conversation that owns attachment document rows with stored blobs and derived artefact rows
- **WHEN** the owner deletes the conversation
- **THEN** the response SHALL have status 204
- **AND** the attachment document rows SHALL no longer exist in the database
- **AND** the attachment blobs SHALL no longer exist in the content store
- **AND** the derived span, chunk, entity and relational rows SHALL no longer exist
- **AND** the conversation SHALL no longer be retrievable through the product UI

#### Scenario: Retrying a conversation delete is safe

- **GIVEN** a conversation that has already been deleted
- **WHEN** the delete endpoint is called again for the same conversation id
- **THEN** the response SHALL be not-found
- **AND** no partial attachment state SHALL be left behind by the retry

#### Scenario: Deleting a conversation without attachments is unchanged

- **GIVEN** a conversation with no attachment document rows
- **WHEN** the owner deletes the conversation
- **THEN** the response SHALL have status 204
- **AND** the conversation and its messages SHALL be removed exactly as before