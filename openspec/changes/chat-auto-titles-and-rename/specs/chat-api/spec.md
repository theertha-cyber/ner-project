## ADDED Requirements

### Requirement: Automatic conversation title generation

When a chat message is sent with `conversation_id: null` (creating a new conversation), the system SHALL derive a short title from that first user message and persist it to the new conversation's `title` field. The title SHALL be produced by collapsing whitespace, stripping leading/trailing punctuation, and truncating to a maximum of 60 characters at a word boundary (appending `…` when truncated). If the derived title would be empty, the system SHALL fall back to `"New conversation"`. Title generation SHALL NOT invoke an external LLM call or add measurable latency to the chat response.

#### Scenario: Title generated from a short first message

- **GIVEN** a user with no existing conversation sends `POST /api/v1/chat` with `{"message": "How many organizations did we extract last month?", "conversation_id": null}`
- **THEN** a new conversation SHALL be created
- **AND** the conversation's `title` SHALL be set to a non-null string derived from the message text
- **AND** subsequent `GET /api/v1/chat/conversations` SHALL return that title for the conversation

#### Scenario: Title truncated for a long first message

- **GIVEN** a first message longer than 60 characters
- **WHEN** the conversation is created
- **THEN** the persisted `title` SHALL be at most 60 characters
- **AND** the truncation SHALL occur at a word boundary, not mid-word
- **AND** the title SHALL end with `…`

#### Scenario: Empty-content first message falls back to placeholder title

- **GIVEN** a first message consisting only of whitespace or punctuation
- **WHEN** the conversation is created
- **THEN** the persisted `title` SHALL be `"New conversation"`

#### Scenario: Title is generated once and not overwritten by later messages

- **GIVEN** a conversation that already has a non-null `title`
- **WHEN** the user sends another message with that conversation's `conversation_id`
- **THEN** the conversation's `title` SHALL remain unchanged

### Requirement: Rename conversation endpoint

The system SHALL expose `PATCH /api/v1/chat/conversations/{conv_id}` that allows the authenticated owner of a conversation to set its `title` to a caller-supplied value. The request body SHALL contain a `title` field constrained to 1-100 characters after trimming whitespace. The endpoint SHALL be scoped to the conversation's owning tenant and user, matching the existing DELETE endpoint's ownership semantics.

#### Scenario: Owner renames their conversation

- **GIVEN** a conversation owned by user A with `title: "New conversation"`
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with `{"title": "Q3 entity counts"}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the updated `title` value `"Q3 entity counts"`
- **AND** a subsequent `GET /api/v1/chat/conversations/{conv_id}` SHALL return the updated title

#### Scenario: Renaming another user's conversation returns 404

- **GIVEN** a conversation owned by user A
- **WHEN** user B sends `PATCH /api/v1/chat/conversations/{conv_id}` with a new title
- **THEN** the response SHALL have status 404

#### Scenario: Renaming with an empty title is rejected

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with `{"title": "   "}`
- **THEN** the response SHALL have status 422

#### Scenario: Renaming with an over-length title is rejected

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends `PATCH /api/v1/chat/conversations/{conv_id}` with a `title` longer than 100 characters
- **THEN** the response SHALL have status 422

#### Scenario: Renaming requires authentication

- **GIVEN** no JWT token
- **WHEN** a PATCH request is sent to `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 401
