## ADDED Requirements

### Requirement: Documents library excludes conversation-linked rows

The system SHALL exclude document rows that belong to a conversation (a row whose `conversation_id` is not null) from every tenant-wide Documents library surface: listing, fetch-by-id, text retrieval, and library delete. Behavior for non-chat documents SHALL remain unchanged — a row whose `conversation_id` is null SHALL continue to list, fetch, return text, and soft-delete exactly as before.

#### Scenario: Library listing omits a chat attachment

- **GIVEN** a tenant has a non-chat upload and a conversation-linked attachment row
- **WHEN** the tenant-wide Documents list is fetched
- **THEN** only the non-chat upload is returned
- **AND** the conversation-linked attachment row is absent from the results and from the total count

#### Scenario: Fetching a chat attachment by id from the library is refused

- **GIVEN** a conversation-linked attachment row exists for the tenant
- **WHEN** the library fetch-by-id endpoint is called for that row's id
- **THEN** the response SHALL be not-found
- **AND** nothing about the attachment row is returned

#### Scenario: Library text retrieval of a chat attachment is refused

- **GIVEN** a conversation-linked attachment row exists for the tenant
- **WHEN** the library text-retrieval endpoint is called for that row's id
- **THEN** the response SHALL be not-found
- **AND** no span text derived from the attachment is returned

#### Scenario: Library delete refuses a chat attachment

- **GIVEN** a conversation-linked attachment row exists for the tenant
- **WHEN** the library delete endpoint is called for that row's id
- **THEN** the response SHALL be not-found
- **AND** the attachment row SHALL remain unchanged

#### Scenario: Non-chat documents behave unchanged

- **GIVEN** a non-chat upload with processed spans
- **WHEN** the library list, fetch-by-id, text-retrieval and delete endpoints are exercised
- **THEN** each response SHALL match existing behavior — the row lists, fetches, returns text and soft-deletes as before