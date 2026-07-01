## ADDED Requirements

### Requirement: Citation card display

The chat message area SHALL display source citations as compact inline cards below each assistant message. Each citation card SHALL prominently show the `document_name` as a clickable heading, followed by `entity_type`, `entity_value`, and `confidence` on a single line. An optional expandable section SHALL reveal the `context_snippet`. The old source-type-specific expandable sections (`source_type: "sql"` / `"ner"` / `"document_chunk"`) SHALL be replaced by this unified card.

#### Scenario: Assistant message shows citation cards

- **GIVEN** an assistant message with 3 citations from documents "report.pdf", "data.xlsx", and "notes.txt"
- **WHEN** the message is rendered
- **THEN** each citation SHALL display the document name as the primary label
- **AND** each citation SHALL show entity type, value, and confidence
- **AND** citations SHALL be numbered or bulleted for readability

#### Scenario: Citation card expands to show context

- **GIVEN** a citation card with a `context_snippet`
- **WHEN** the user clicks the expand toggle on the card
- **THEN** the snippet text SHALL be revealed
- **AND** the toggle SHALL change from "Show context" to "Hide context"

#### Scenario: Citation card without context snippet

- **GIVEN** a citation card without `context_snippet`
- **WHEN** the card is rendered
- **THEN** the card SHALL NOT show an expand toggle
- **AND** the card SHALL display only the document name and entity details

## MODIFIED Requirements

### Requirement: Conversation sidebar

The chat screen SHALL display a conversation sidebar on the left, showing a list of the user's conversations ordered by most-recent-message date (descending). Each conversation item SHALL display a truncated title (derived from the first message) and the date of the last message. The sidebar SHALL include a "New conversation" button at the top that creates a new conversation via the API and navigates to it immediately.

#### Scenario: New conversation button creates conversation via API

- **GIVEN** the conversation sidebar is displayed
- **WHEN** the user clicks "New conversation"
- **THEN** a POST request SHALL be sent to `/api/v1/chat/conversations`
- **AND** upon success, the new conversation SHALL appear in the sidebar
- **AND** the new conversation SHALL be selected as the active conversation
- **AND** the message area SHALL show "Send a message to start"
- **AND** the chat input SHALL be visible and focused

#### Scenario: New conversation API fails

- **GIVEN** the conversation sidebar is displayed
- **WHEN** the user clicks "New conversation" and the API returns an error
- **THEN** an error message SHALL be displayed to the user
- **AND** the current conversation (if any) SHALL remain active
- **AND** the user SHALL be able to retry

#### Scenario: New conversation button shows loading state

- **GIVEN** the conversation sidebar is displayed
- **WHEN** the user clicks "New conversation" and the API request is in flight
- **THEN** the button SHALL be disabled
- **AND** the button SHALL show a loading indicator

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as unified citation cards below the message text.

#### Scenario: Send message and receive response

- **GIVEN** a conversation is selected
- **WHEN** the user types a message in the input box and presses Enter
- **THEN** the message SHALL appear in the thread immediately (optimistic update)
- **AND** a loading indicator SHALL appear
- **AND** when the response arrives, it SHALL appear in the thread with citation cards
- **AND** the thread SHALL auto-scroll to show the latest message

#### Scenario: Empty conversation state

- **GIVEN** a new empty conversation with no messages
- **WHEN** the conversation is displayed
- **THEN** the message area SHALL show "Send a message to start"
- **AND** the chat input SHALL be visible
