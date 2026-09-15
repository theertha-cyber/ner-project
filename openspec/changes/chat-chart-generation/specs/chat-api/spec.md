## ADDED Requirements

### Requirement: Chart in the chat response contract

The chat response SHALL carry an optional `chart` object describing a chart to render alongside the answer. The field SHALL be additive on the same terms as `pending_clarification` and `retrieval_status`: it SHALL be omitted entirely from the payload when the turn produced no chart, rather than serialized as null, so that clients which ignore it observe no change in any other field.

The object SHALL contain `chart_type` (one of `bar`, `line`, `pie`), `title`, `categories` (array of strings), and `series` (array of objects, each with `name` and a `data` array of numbers), and MAY contain `x_label` and `y_label`.

A chart SHALL never be accompanied by an empty `sources` array. The chart is evidence-bearing content and is subject to the same citation requirement as the answer it accompanies; the citations already returned for the turn SHALL serve as the chart's sourcing, and no separate chart-specific citation field SHALL be introduced.

The widget chat response SHALL be unchanged by this requirement and SHALL NOT carry a chart.

#### Scenario: Response without a chart omits the field

- **GIVEN** a chat turn that produced no chart
- **WHEN** the client receives the response
- **THEN** the payload SHALL NOT contain a `chart` key
- **AND** every other field SHALL be identical to the pre-change response for the same inputs

#### Scenario: Response with a chart carries the payload and citations

- **GIVEN** a chat turn whose chart passed validation
- **WHEN** the client receives the response
- **THEN** the payload SHALL contain a `chart` object with `chart_type`, `title`, `categories`, and `series`
- **AND** `sources` SHALL contain at least one citation

#### Scenario: Widget response is unaffected

- **GIVEN** a widget chat request whose turn would have been chart-eligible on the internal endpoint
- **WHEN** the widget response is returned
- **THEN** the payload SHALL contain only `reply`, `sources`, and `disclaimer`
- **AND** it SHALL NOT contain a `chart` key

### Requirement: Chart event on the streaming endpoint

The streaming endpoint SHALL deliver a chart, when one exists, as a distinct `chart` Server-Sent Event whose data is the chart object. The event SHALL be emitted after the turn's chart is decided and before the first `token` event, so that a client can reserve or render the chart while the answer text is still streaming.

At most one `chart` event SHALL be emitted per turn. A turn with no chart SHALL emit no `chart` event. The `done` event's payload SHALL continue to carry the complete response, including the chart when present, so that a client which ignores `chart` events still receives the chart.

Clients that do not recognise the `chart` event SHALL be unaffected: the existing `token`, `done`, and `error` events SHALL retain their current names, ordering, and payloads.

#### Scenario: Chart event precedes the first token

- **GIVEN** a streaming turn whose chart passed validation
- **WHEN** the client consumes the stream
- **THEN** a `chart` event SHALL be received
- **AND** it SHALL arrive before any `token` event
- **AND** exactly one `chart` event SHALL be received for the turn

#### Scenario: Turn without a chart emits no chart event

- **GIVEN** a streaming turn that produced no chart
- **WHEN** the client consumes the stream
- **THEN** no `chart` event SHALL be emitted
- **AND** the sequence of `token` and `done` events SHALL be unchanged from the pre-change behaviour

#### Scenario: Done event repeats the chart

- **GIVEN** a streaming turn that emitted a `chart` event
- **WHEN** the `done` event arrives
- **THEN** its payload SHALL contain the same chart object

#### Scenario: Suppressed chart emits no event

- **GIVEN** a streaming turn whose reply is replaced by citation enforcement
- **WHEN** the client consumes the stream
- **THEN** no `chart` event SHALL be emitted
- **AND** the `done` payload SHALL contain no `chart` key

### Requirement: Chart persisted with the assistant turn

The chart SHALL be persisted with the assistant message it accompanies, in the same write that persists the turn's reply and sources, so that a chart survives reload of the conversation. Persistence SHALL follow the precedent set by `sources`: a nullable JSONB column on `chat_messages`, written as the serialized chart object and null when the turn produced no chart.

The conversation detail endpoint SHALL return the persisted chart for each assistant message that has one, on the same additive terms as the live response: absent rather than null when the message has no chart. User messages SHALL never carry a chart.

The column SHALL be added to the tenant template schema and to every existing tenant schema, so that the change applies uniformly across tenants.

#### Scenario: Chart survives conversation reload

- **GIVEN** a completed turn whose response carried a chart
- **WHEN** the client reloads the conversation via the conversation detail endpoint
- **THEN** the assistant message SHALL carry the same chart object that was returned live

#### Scenario: Messages without charts are unchanged on reload

- **GIVEN** a conversation of turns that produced no charts
- **WHEN** the client reloads the conversation
- **THEN** no message SHALL contain a `chart` key
- **AND** every returned field SHALL be identical to the pre-change response

#### Scenario: Existing tenants receive the column

- **GIVEN** a deployment with tenant schemas created before this change
- **WHEN** the migration runs
- **THEN** every existing tenant schema's `chat_messages` table SHALL have the nullable chart column
- **AND** the tenant template SHALL have it, so newly provisioned tenants inherit it

#### Scenario: Rows written before the change read back cleanly

- **GIVEN** assistant messages persisted before the column existed
- **WHEN** the conversation is reloaded
- **THEN** those messages SHALL be returned without a chart and without error
