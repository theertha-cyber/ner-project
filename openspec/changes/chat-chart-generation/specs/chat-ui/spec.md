## MODIFIED Requirements

### Requirement: Message thread display

The message area SHALL display the conversation's messages in a scrollable thread, with user messages right-aligned and assistant messages left-aligned. Each assistant message SHALL display source citations as expandable sections below the message text. An assistant message that carries a chart SHALL additionally render that chart between the message text and its citations.

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

#### Scenario: Assistant message with a chart renders it above its citations

- **GIVEN** an assistant message carrying a chart
- **WHEN** the message renders
- **THEN** the chart SHALL appear below the message text and above the citation section
- **AND** the citation section SHALL render as it does for any other assistant message

## ADDED Requirements

### Requirement: Chart rendering in the chat thread

The chat UI SHALL render a chart carried by an assistant message as an interactive chart, using the chart type named in the payload: a bar chart, a line chart, or a pie chart. The chart SHALL show its title, label its axes when the payload supplies labels, and render one visual series per entry in `series`, keyed to the payload's `categories`.

The chart SHALL be responsive to the width of the message column and SHALL remain legible at the narrowest width the chat thread supports. It SHALL draw its colours from the portal's design tokens rather than hardcoded hex values or Tailwind colour classes, so that it renders correctly in both light and dark themes.

A message with no chart SHALL render exactly as it does today, with no reserved space, placeholder, or empty container.

A chart payload the UI cannot render — an unrecognised `chart_type`, or series that do not line up with the categories — SHALL be skipped silently, leaving the text answer and citations intact. The UI SHALL NOT surface an error to the user for a malformed chart.

#### Scenario: Bar chart renders with title and categories

- **GIVEN** an assistant message carrying a `bar` chart with four categories and one series
- **WHEN** the message renders
- **THEN** an interactive bar chart SHALL be displayed
- **AND** the chart's title SHALL be shown
- **AND** the four categories SHALL be labelled on the category axis

#### Scenario: Line and pie types render their respective chart

- **GIVEN** assistant messages carrying a `line` chart and a `pie` chart
- **WHEN** each renders
- **THEN** the `line` payload SHALL render as a line chart
- **AND** the `pie` payload SHALL render as a pie chart

#### Scenario: Chart honours the active theme

- **GIVEN** a rendered chart
- **WHEN** the portal is switched between light and dark theme
- **THEN** the chart's colours SHALL follow the design tokens for the active theme
- **AND** the chart SHALL remain legible in both

#### Scenario: Chart is responsive at narrow widths

- **GIVEN** an assistant message carrying a chart
- **WHEN** the viewport narrows to the smallest width the chat thread supports
- **THEN** the chart SHALL resize to fit the message column
- **AND** the thread SHALL NOT scroll horizontally

#### Scenario: Message without a chart is unchanged

- **GIVEN** an assistant message carrying no chart
- **WHEN** the message renders
- **THEN** no chart container SHALL be present in the DOM
- **AND** the message SHALL render identically to its pre-change appearance

#### Scenario: Unrenderable chart payload is skipped

- **GIVEN** an assistant message carrying a chart whose `chart_type` the UI does not recognise
- **WHEN** the message renders
- **THEN** no chart SHALL be rendered
- **AND** the message text and citations SHALL render normally
- **AND** no error SHALL be shown to the user

### Requirement: Chart delivered over the streaming connection

The chat client SHALL handle a `chart` event on the streaming connection by attaching the chart to the assistant message currently being streamed, so that the chart appears alongside the answer as it arrives rather than only once the turn completes. Events the client does not recognise SHALL continue to be ignored without error.

When the turn completes, the chart carried by the completion payload SHALL be the authoritative value for the message, so that a chart is present even if the client missed or ignored the streamed event.

#### Scenario: Streamed chart attaches to the in-flight message

- **GIVEN** a streaming turn that emits a `chart` event before its first token
- **WHEN** the client processes the stream
- **THEN** the chart SHALL be attached to the streaming assistant message
- **AND** the chart SHALL be visible while the answer text is still arriving

#### Scenario: Completion payload is authoritative

- **GIVEN** a completed streaming turn whose completion payload carries a chart
- **WHEN** the client finalises the message
- **THEN** the message SHALL carry the chart from the completion payload

#### Scenario: Reloaded conversation renders persisted charts

- **GIVEN** a past conversation containing an assistant message that was answered with a chart
- **WHEN** the user reopens that conversation
- **THEN** the chart SHALL render in the thread as it did when the answer was first received
