## MODIFIED Requirements

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as expandable sections below the message text. Each assistant message whose `answer_kind` equals `"answer"` SHALL display Thumbs Up and Thumbs Down feedback controls (Lucide `ThumbsUp`/`ThumbsDown` icons) beside the message, visible only when the authenticated user has role `business_user`. Assistant messages whose `answer_kind` is `"clarification"`, `"guardrail_blocked"`, or `"out_of_domain"` SHALL NOT display feedback controls, regardless of role. User messages SHALL NEVER display feedback controls, regardless of role.

Once a message has been rated, the selected icon SHALL render in a visually fixed/active state and the opposite icon SHALL become non-interactive (disabled), for that message, for the remainder of the session and across future sessions.

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

#### Scenario: Business user sees feedback controls on eligible answer messages only

- **GIVEN** a Business User viewing a conversation thread containing user messages and assistant messages of every `answer_kind`
- **WHEN** the thread renders
- **THEN** each assistant message with `answer_kind: "answer"` SHALL display Thumbs Up and Thumbs Down icons beside it
- **AND** no user message SHALL display feedback icons
- **AND** no clarification, guardrail-blocked, or out-of-domain assistant message SHALL display feedback icons

#### Scenario: Non-business_user does not see feedback controls

- **GIVEN** a Tenant Admin viewing a conversation thread
- **WHEN** the thread renders
- **THEN** no message SHALL display feedback icons

#### Scenario: Rating a message fixes the selection

- **GIVEN** a Business User viewing an unrated assistant message
- **WHEN** the user clicks Thumbs Up
- **THEN** the Thumbs Up icon SHALL render in a selected/active visual state
- **AND** the Thumbs Down icon SHALL become disabled and non-clickable for that message

#### Scenario: Rated message stays fixed after page refresh

- **GIVEN** an assistant message rated Thumbs Down in a previous page load
- **WHEN** the Business User refreshes the page and reopens the conversation
- **THEN** the Thumbs Down icon SHALL render in the selected/active state
- **AND** both icons SHALL be non-interactive for that message
