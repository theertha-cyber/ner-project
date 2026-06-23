## Purpose

Provide an internal chat user interface within the NER platform portal, allowing tenant admins and business users to interact with the RAG chatbot through a conversation sidebar and message thread with expandable source citations.

## Requirements

### Requirement: Chat screen route and access

The system SHALL expose a chat screen at the `/chat` route in the portal SPA. The screen SHALL be accessible to users with `tenant_admin` or `business_user` roles. Other roles SHALL see a 403 error or be redirected to the dashboard.

#### Scenario: Tenant admin accesses chat screen

- **GIVEN** an authenticated tenant_admin user
- **WHEN** the user navigates to `/chat`
- **THEN** the chat screen SHALL render with a conversation sidebar and message area
- **AND** the screen SHALL load the user's existing conversations

#### Scenario: Annotator accesses chat screen

- **GIVEN** an authenticated annotator user
- **WHEN** the user navigates to `/chat`
- **THEN** the user SHALL be redirected to the dashboard
- **OR** the screen SHALL show an access-denied message

### Requirement: Conversation sidebar

The chat screen SHALL display a conversation sidebar on the left, showing a list of the user's conversations ordered by most-recent-message date (descending). Each conversation item SHALL display a truncated title (derived from the first message) and the date of the last message. The sidebar SHALL include a "New conversation" button at the top.

#### Scenario: New conversation button creates conversation

- **GIVEN** the conversation sidebar is displayed
- **WHEN** the user clicks "New conversation"
- **THEN** a new empty conversation SHALL be created
- **AND** the message area SHALL show "Send a message to start"

#### Scenario: Clicking conversation loads messages

- **GIVEN** a list of conversations in the sidebar
- **WHEN** the user clicks on a conversation
- **THEN** the message area SHALL display the conversation's message history
- **AND** the selected conversation SHALL be visually highlighted

#### Scenario: Delete conversation from sidebar

- **GIVEN** a conversation in the sidebar
- **WHEN** the user clicks the delete icon on a conversation
- **THEN** a confirmation dialog SHALL appear
- **AND** upon confirmation, the conversation SHALL be deleted
- **AND** the sidebar SHALL remove the conversation from the list

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as expandable sections below the message text.

#### Scenario: Send message and receive response

- **GIVEN** a conversation is selected
- **WHEN** the user types a message in the input box and presses Enter
- **THEN** the message SHALL appear in the thread immediately (optimistic update)
- **AND** a loading indicator SHALL appear
- **AND** when the response arrives, it SHALL appear in the thread
- **AND** the thread SHALL auto-scroll to show the latest message

#### Scenario: Source citations are expandable

- **GIVEN** an assistant message with source citations
- **WHEN** the user clicks on a source citation
- **THEN** the citation SHALL expand to show the source details
- **AND** the details SHALL include `document_id` or `entity_type`, and relevant snippet text

### Requirement: Role-gated chat access

The `/chat` route SHALL be gated by role. The screen SHALL use `<RequireAuth roles={["tenant_admin", "business_user"]}>` from SP-02 to enforce access.

#### Scenario: Business user accesses chat

- **GIVEN** an authenticated business_user
- **WHEN** the user navigates to `/chat`
- **THEN** the chat screen SHALL render normally with all functionality
