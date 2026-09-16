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

### Requirement: Authenticated API calls from chat page

The chat page SHALL authenticate all API requests (list conversations, get messages, delete conversation, send message) using a Bearer JWT token obtained from the authentication system. Requests without a valid token SHALL be rejected by the gateway with status 401.

#### Scenario: Chat page sends authenticated requests

- **GIVEN** an authenticated tenant_admin user on the chat page
- **WHEN** the page loads and fetches conversations
- **THEN** the request SHALL include an `Authorization: Bearer <token>` header
- **AND** the gateway SHALL accept the token and return conversations

#### Scenario: Unauthenticated chat request returns 401

- **GIVEN** no valid JWT token
- **WHEN** a fetch is sent to `/api/v1/chat/conversations`
- **THEN** the response SHALL have status 401

### Requirement: Role-gated chat access

The `/chat` route SHALL be gated by role. The screen SHALL use `<RequireAuth roles={["tenant_admin", "business_user"]}>` from SP-02 to enforce access.

#### Scenario: Business user accesses chat

- **GIVEN** an authenticated business_user
- **WHEN** the user navigates to `/chat`
- **THEN** the chat screen SHALL render normally with all functionality

### Requirement: Rename conversation from sidebar

Each conversation item in the sidebar SHALL display a rename (edit) control alongside the existing delete control. Clicking it SHALL turn the title into an inline editable text field. Confirming the edit (Enter key or blur) SHALL call the rename API and update the displayed title on success; pressing Escape SHALL cancel the edit without calling the API.

#### Scenario: User renames a conversation via the sidebar

- **GIVEN** a conversation in the sidebar with title "How many organizations..."
- **WHEN** the user clicks the rename icon, clears the field, types "Org counts Q3", and presses Enter
- **THEN** the sidebar SHALL call the rename API with the new title
- **AND** on success the sidebar SHALL display "Org counts Q3" for that conversation

#### Scenario: User cancels a rename in progress

- **GIVEN** a conversation's title is being edited inline
- **WHEN** the user presses Escape
- **THEN** the inline edit SHALL close without calling the rename API
- **AND** the original title SHALL remain displayed

#### Scenario: Rename API failure keeps the previous title

- **GIVEN** a conversation's title is being edited inline
- **WHEN** the user confirms the edit and the rename API call fails
- **THEN** the sidebar SHALL keep displaying the previous title
- **AND** an error indication SHALL be shown to the user

#### Scenario: Newly created conversation shows placeholder until first message

- **GIVEN** a conversation just created via "New conversation" with no messages yet
- **WHEN** the sidebar renders that conversation
- **THEN** the displayed title SHALL be the placeholder "New conversation"
- **AND** once the first message is sent and the conversation list is refreshed, the sidebar SHALL display the backend-generated title instead

### Requirement: Authenticated download from the revealed format actions

Clicking a download action (once revealed, per the "Export prompt reveals download actions only after the user opts in" requirement below) SHALL fetch the file from the export endpoint using the same Bearer JWT authentication as other chat API calls, and SHALL NOT expose the token in the resulting file URL.

#### Scenario: Clicking download triggers an authenticated fetch

- **GIVEN** a revealed "Download CSV" action for an assistant message
- **WHEN** the user clicks it
- **THEN** a fetch SHALL be sent to `/api/v1/chat/messages/{message_id}/export?format=csv` with an `Authorization: Bearer <token>` header
- **AND** the returned file SHALL be saved via a blob URL, not a direct navigation to a URL containing the token

### Requirement: Inline preview truncation is independent of export availability

Whether an assistant message's reply text truncates with a "See more" toggle SHALL be determined by whether the rendered reply visually overflows a bounded display height — not by `export.row_count`, not by counting the reply's text lines, and not by any other business-logic proxy for length. This holds regardless of whether the turn has an associated export at all: a long reply with no structured result behind it (`export` absent) truncates on overflow exactly the same as a long reply that does have one.

Truncation and export availability (see the "Export offer" requirement below) are independent conditions evaluated separately. A short reply with a large `export.row_count` does not truncate (nothing overflows). A long reply with `export.row_count = 1` still truncates if it visually overflows, even though it describes only one result.

#### Scenario: A reply that visually overflows truncates with a See more toggle

- **GIVEN** an assistant message whose rendered reply exceeds the bounded display height
- **WHEN** the message thread renders that message
- **THEN** the reply SHALL be visually clipped to the bounded height
- **AND** a "See more" toggle SHALL appear below it

#### Scenario: Clicking See more reveals the full reply

- **GIVEN** a truncated assistant message as above
- **WHEN** the user clicks "See more"
- **THEN** the full reply SHALL render in place
- **AND** the toggle SHALL read "See less"
- **AND** clicking it again SHALL collapse back to the bounded height

#### Scenario: A reply that fits within the bounded height is never truncated, regardless of export.row_count

- **GIVEN** an assistant message whose rendered reply does not exceed the bounded display height, with `export.row_count = 28`
- **WHEN** the message thread renders that message
- **THEN** the full reply SHALL be shown
- **AND** no "See more" toggle SHALL appear

#### Scenario: A long reply with no structured result behind it still truncates on overflow

- **GIVEN** an assistant message whose `export` field is absent and whose rendered reply exceeds the bounded display height
- **WHEN** the message thread renders that message
- **THEN** the reply SHALL be visually clipped to the bounded height
- **AND** a "See more" toggle SHALL appear below it, exactly as it would for a message with an export

#### Scenario: Truncation is suppressed while a message is still streaming

- **GIVEN** an assistant message that is still `isThinking` or `isStreaming`
- **WHEN** the message thread renders that message
- **THEN** no truncation or "See more" toggle SHALL appear until the message finishes (matching the existing suppression of citation chips and the rating control while streaming)

### Requirement: Export offer appears whenever structured data exists, regardless of result count

When an assistant message's `export` field is present (`export.row_count >= 1`), the message thread SHALL show an export prompt below the reply, regardless of how many results that is and regardless of whether the reply's own text happens to be truncated. There is no row-count threshold gating whether the prompt appears — offering the option costs nothing and a small result is exactly as legitimately downloadable as a large one.

The prompt SHALL state the actual result count (e.g. "This includes 45 results — want a downloadable version?"), so the user is not opting in blind.

When a message's `export` field is absent, no export prompt SHALL appear.

#### Scenario: A small result still gets an export prompt

- **GIVEN** an assistant message with `export.row_count = 1`
- **WHEN** the message thread renders that message
- **THEN** an export prompt SHALL appear below the reply, stating "1 result"
- **AND** this holds even though the reply itself is not truncated (per the truncation requirement above)

#### Scenario: A large result gets an export prompt stating the count

- **GIVEN** an assistant message with `export.row_count = 45`
- **WHEN** the message thread renders that message
- **THEN** an export prompt SHALL appear below the reply, stating "45 results"

#### Scenario: No export prompt when there is no structured result

- **GIVEN** an assistant message whose `export` field is absent
- **WHEN** the message thread renders that message
- **THEN** no export prompt SHALL appear

#### Scenario: The export prompt is suppressed while a message is still streaming

- **GIVEN** an assistant message that is still `isThinking` or `isStreaming`, with `export.row_count = 8`
- **WHEN** the message thread renders that message
- **THEN** no export prompt SHALL appear until the message finishes

### Requirement: Export prompt reveals download actions only after the user opts in

The export prompt SHALL NOT render "Download CSV"/"Download XLSX" actions immediately. It SHALL first render as a lightweight, low-visual-weight question stating the result count. Only after the user responds affirmatively (clicks the prompt) SHALL the CSV and XLSX download actions render.

#### Scenario: The prompt does not show download actions before the user responds

- **GIVEN** an assistant message with `export.row_count = 12`
- **WHEN** the message thread renders that message
- **THEN** an export prompt stating "12 results" SHALL appear
- **AND** no "Download CSV" or "Download XLSX" action SHALL be visible yet

#### Scenario: Responding to the prompt reveals the format actions

- **GIVEN** a rendered export prompt as above
- **WHEN** the user clicks the prompt
- **THEN** "Download CSV" and "Download XLSX" actions SHALL appear in its place
