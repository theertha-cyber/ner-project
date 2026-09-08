## ADDED Requirements

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
