## ADDED Requirements

### Requirement: Chat response export availability

`ChatResponse` SHALL include an `export` field describing whether a structured-result snapshot is available for download for that turn. When available, it SHALL include the `message_id`, the snapshot's `row_count`, and the list of supported formats (`csv`, `xlsx`). `export` is additive, following the same convention as the existing `pending_clarification` and `retrieval_status` fields: when no structured retrieval snapshot exists for the turn, the key SHALL be omitted from the serialized JSON body entirely (not sent as `null`), so a client that ignores it observes no change. The full row data SHALL NOT be inlined into `ChatResponse` — only this availability metadata.

`MessageResponse` (returned by `GET /api/v1/chat/conversations/{conv_id}`, per the `chat-api` capability's Conversation CRUD requirement) SHALL carry the same `export` availability metadata for each past assistant message that has a snapshot, using only the message's stored row count — never the `export_rows` JSONB snapshot itself — so a file card can still be shown after a page reload or conversation switch, without growing that endpoint's response in proportion to snapshot size.

#### Scenario: Response includes export metadata when structured source succeeded

- **GIVEN** a chat turn whose structured entity data source succeeded with 60 rows
- **WHEN** a Tenant Admin sends `POST /api/v1/chat`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `export` field with `row_count: 60` and `formats: ["csv", "xlsx"]`

#### Scenario: Response omits export availability when no structured result exists

- **GIVEN** a chat turn answered entirely from document/semantic sources
- **WHEN** a Tenant Admin sends `POST /api/v1/chat`
- **THEN** the response SHALL have status 200
- **AND** the serialized JSON body SHALL NOT contain an `export` key

#### Scenario: Conversation history retains export availability for past turns

- **GIVEN** a conversation whose earlier assistant message has an export snapshot with 60 rows
- **WHEN** a Tenant Admin sends `GET /api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 200
- **AND** that message's entry SHALL include `export.row_count: 60` and `export.formats: ["csv", "xlsx"]`
- **AND** an assistant message with no export snapshot SHALL have `export: null` on its entry (unlike `ChatResponse`, `MessageResponse`/`ConversationDetail` does not omit absent optional fields — `answer_kind`, `model_version`, and `feedback` already serialize as explicit `null` there, and `export` follows that existing convention rather than introducing field-exclusion to this endpoint)
