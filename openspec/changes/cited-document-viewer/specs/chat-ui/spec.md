## MODIFIED Requirements

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as expandable sections below the message text.

A citation that names a document SHALL additionally offer to open that document in the viewer, without leaving the conversation. A citation that names no document SHALL continue to expand to its details only. An attachment shown on a user message SHALL offer to open the attached file in the same viewer.

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

#### Scenario: A citation naming a document offers to open it

- **GIVEN** an assistant message with a citation carrying a `document_id`
- **WHEN** the user looks at that citation
- **THEN** an affordance to open the cited document SHALL be present

#### Scenario: A citation without a document offers no viewer

- **GIVEN** an assistant message with a citation carrying no `document_id`
- **WHEN** the user looks at that citation
- **THEN** no affordance to open a document SHALL be present
- **AND** its details SHALL remain expandable as before

#### Scenario: An attachment on a user message offers to open it

- **GIVEN** a user message carrying an attachment
- **WHEN** the user looks at that attachment
- **THEN** an affordance to open the attached file SHALL be present

#### Scenario: Opening a document keeps the conversation in place

- **GIVEN** a thread scrolled to a particular message
- **WHEN** the user opens a cited document and then closes it
- **THEN** the thread SHALL still be showing that message
- **AND** no navigation away from the conversation SHALL have occurred
