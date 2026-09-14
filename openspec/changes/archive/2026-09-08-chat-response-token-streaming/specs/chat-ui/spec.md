## MODIFIED Requirements

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as expandable sections below the message text.

While a turn is in flight, the thread SHALL show the existing Thinking indicator in the assistant bubble until the first generated content fragment arrives, then SHALL replace the indicator with the generated text in that same bubble and append each subsequent fragment to it as it arrives. The Thinking indicator SHALL NOT be cleared merely because the request was accepted or because retrieval finished. Source citations and the response-rating control SHALL be withheld until the turn completes, at which point the bubble's text SHALL be replaced with the authoritative complete reply and the citations, `answer_kind`, and `model_version` SHALL be attached. No new visual treatment SHALL be introduced: the streamed message SHALL use the existing assistant bubble and markdown rendering.

#### Scenario: Send message and receive streamed response

- **GIVEN** a conversation is selected
- **WHEN** the user types a message in the input box and presses Enter
- **THEN** the message SHALL appear in the thread immediately (optimistic update)
- **AND** the Thinking indicator SHALL appear in an assistant bubble
- **AND** the Thinking indicator SHALL remain visible until the first content fragment arrives
- **AND** when the first fragment arrives, the Thinking indicator SHALL be replaced by that fragment's text
- **AND** each subsequent fragment SHALL be appended to the same bubble
- **AND** when the turn completes, the bubble SHALL show the complete reply with its citations
- **AND** the thread SHALL auto-scroll to show the latest message

#### Scenario: Citations and rating appear only on completion

- **GIVEN** an assistant message that is still streaming
- **WHEN** the thread is rendered mid-stream
- **THEN** no citation chips SHALL be displayed for that message
- **AND** no rating control SHALL be displayed for that message

#### Scenario: Source citations are expandable

- **GIVEN** an assistant message with source citations
- **WHEN** the user clicks on a source citation
- **THEN** the citation SHALL expand to show the source details
- **AND** the details SHALL include `document_id` or `entity_type`, and relevant snippet text

#### Scenario: Failed turn clears the Thinking indicator

- **GIVEN** a turn whose response fails after the Thinking indicator has appeared
- **WHEN** the failure is surfaced to the thread
- **THEN** no message with the Thinking indicator SHALL remain in the thread
- **AND** the optimistic user message SHALL be removed
- **AND** the existing error notification SHALL be displayed
