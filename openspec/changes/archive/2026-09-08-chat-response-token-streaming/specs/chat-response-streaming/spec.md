## ADDED Requirements

### Requirement: Streaming chat endpoint

The system SHALL expose `POST /api/v1/chat/stream` on chat_api, accepting the same request body as `POST /api/v1/chat` (`message`, optional `conversation_id`) and the same `Authorization: Bearer` authentication, and returning a Server-Sent Events stream with `Content-Type: text/event-stream`. The endpoint SHALL apply the same tenant-context check and the same per-tenant rate limit as the non-streaming endpoint, and SHALL return the same rate-limit response headers. The response SHALL set `Cache-Control: no-cache` and `X-Accel-Buffering: no` so that intermediate proxies do not coalesce the stream.

#### Scenario: Streaming endpoint returns an event stream

- **GIVEN** an authenticated tenant user with an existing conversation
- **WHEN** the user sends `POST /api/v1/chat/stream` with `{"message": "How many organizations did we extract?", "conversation_id": "conv-abc"}`
- **THEN** the response SHALL have status 200
- **AND** the `Content-Type` header SHALL be `text/event-stream`
- **AND** the `Cache-Control` header SHALL be `no-cache`
- **AND** the `X-Accel-Buffering` header SHALL be `no`

#### Scenario: Streaming request without authentication is rejected

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to `/api/v1/chat/stream`
- **THEN** the response SHALL have status 401
- **AND** no event stream SHALL be opened

#### Scenario: Streaming request over the rate limit is rejected

- **GIVEN** a tenant that has exhausted its internal chat rate limit
- **WHEN** the user sends `POST /api/v1/chat/stream`
- **THEN** the response SHALL have status 429
- **AND** the response SHALL carry the `Retry-After` header
- **AND** no event stream SHALL be opened

### Requirement: SSE event protocol

The stream SHALL emit exactly three named event types. A `token` event SHALL carry `{"delta": "<content fragment>"}` and represents one fragment of generated assistant content. A `done` event SHALL carry the complete response payload — `reply`, `sources`, `conversation_id`, `message_id`, `disclaimer`, `answer_kind`, `model_version`, and `pending_clarification` when non-null — identical in content to the JSON body the non-streaming endpoint returns for the same turn, with `pending_clarification` omitted entirely when it is null. An `error` event SHALL carry `{"code": "<code>", "message": "<human-readable message>"}`. Every successful stream SHALL terminate with exactly one `done` event; every failed stream SHALL terminate with exactly one `error` event. A stream SHALL NOT emit both.

#### Scenario: Successful turn emits tokens then done

- **GIVEN** a generation LLM scripted to emit the content deltas `"Based"`, `" on"`, `" the documents"` and a turn whose retrieval produced at least one source
- **WHEN** the client consumes `POST /api/v1/chat/stream`
- **THEN** the stream SHALL emit three `token` events whose `delta` values are `"Based"`, `" on"`, and `" the documents"` in that order
- **AND** the stream SHALL then emit exactly one `done` event
- **AND** no `error` event SHALL be emitted

#### Scenario: done payload matches the non-streaming response body

- **GIVEN** the same question, tenant, and conversation state issued to both endpoints with an identical scripted LLM
- **WHEN** the `done` event's data is compared with the non-streaming endpoint's JSON body
- **THEN** the `reply`, `sources`, `answer_kind`, `model_version`, and `disclaimer` fields SHALL be equal
- **AND** both SHALL contain a `conversation_id` and a `message_id`

#### Scenario: Null pending_clarification is omitted from done

- **GIVEN** a turn that produces no pending clarification
- **WHEN** the `done` event's data is parsed
- **THEN** the payload SHALL NOT contain a `pending_clarification` key

#### Scenario: Concatenated token deltas equal the final reply

- **GIVEN** a successful streaming turn that emitted one or more `token` events
- **WHEN** the `delta` values of every `token` event are concatenated in arrival order
- **THEN** the result SHALL equal the `reply` field of the `done` event

### Requirement: Streaming generation mode in the chat graph

The `generation` graph node SHALL support a streaming mode selected by the presence of a token sink in the graph state. When a sink is present and the turn's assembled sources are non-empty, the node SHALL invoke the LLM with streaming enabled, forward each content delta to the sink as it arrives, accumulate the deltas into the complete reply, and return that complete reply in the terminal graph state. When no sink is present, the node SHALL behave exactly as the non-streaming implementation does, making a single buffered completion call. The graph topology SHALL be unchanged: no node is added, removed, or reordered, and the compiled graph SHALL remain acyclic. Nodes other than `generation` SHALL NOT read the sink.

#### Scenario: Sink absent preserves non-streaming behaviour

- **GIVEN** a chat graph invoked without a token sink in state
- **WHEN** the generation node runs
- **THEN** the LLM SHALL be called without streaming enabled
- **AND** the terminal state's `reply` SHALL be the model's complete content

#### Scenario: Sink present streams and accumulates

- **GIVEN** a chat graph invoked with a token sink and a turn whose sources are non-empty
- **WHEN** the generation node runs against an LLM scripted to emit several content deltas
- **THEN** each delta SHALL be pushed to the sink in arrival order
- **AND** the terminal state's `reply` SHALL equal the concatenation of those deltas

#### Scenario: Graph topology is unchanged by streaming

- **GIVEN** the compiled chat graph
- **WHEN** its nodes and edges are inspected with streaming available
- **THEN** the node set and edge set SHALL be identical to the non-streaming topology
- **AND** the compiled graph SHALL report no cycle

### Requirement: Thinking state ends on the first generated token

The stream SHALL NOT emit a `token` event before the generation LLM has produced its first content fragment. Request acceptance, guardrail evaluation, retrieval planning, retrieval execution, source assembly, and prompt assembly SHALL NOT produce any `token` event. The client SHALL keep the Thinking indicator visible until it receives either the first `token` event or the `done` event, whichever arrives first.

#### Scenario: No token is emitted during retrieval

- **GIVEN** a turn whose retrieval stage is slow
- **WHEN** the stream is observed between request acceptance and the LLM's first content fragment
- **THEN** no `token` event SHALL have been emitted

#### Scenario: First token arrives before generation completes

- **GIVEN** a generation LLM scripted to emit deltas with a delay between them
- **WHEN** the client receives the first `token` event
- **THEN** the `done` event SHALL NOT yet have been received

### Requirement: Turns that produce no model output stream no tokens

A turn terminated before the generation node — a blocked question type, an out-of-domain decline, or an entity-resolution clarification — SHALL emit zero `token` events and SHALL terminate with a single `done` event carrying the terminal reply and its metadata. A turn whose assembled sources are empty SHALL likewise emit zero `token` events, and its `done` event SHALL carry the source-enforcement fallback reply.

#### Scenario: Guardrail decline streams no tokens

- **GIVEN** a message classified as out-of-domain
- **WHEN** the client consumes `POST /api/v1/chat/stream`
- **THEN** no `token` event SHALL be emitted
- **AND** exactly one `done` event SHALL be emitted whose `reply` is the out-of-domain decline message
- **AND** its `answer_kind` SHALL be `out_of_domain`

#### Scenario: Entity-resolution clarification streams no tokens

- **GIVEN** an ambiguous person reference that produces a clarification
- **WHEN** the client consumes `POST /api/v1/chat/stream`
- **THEN** no `token` event SHALL be emitted
- **AND** the `done` event SHALL carry the clarification reply and a `pending_clarification` payload
- **AND** its `answer_kind` SHALL be `clarification`

#### Scenario: Empty sources stream no tokens

- **GIVEN** a turn whose retrieval produces no sources
- **WHEN** the client consumes `POST /api/v1/chat/stream`
- **THEN** no `token` event SHALL be emitted
- **AND** the `done` event's `reply` SHALL be the source-enforcement fallback reply
- **AND** the `done` event's `sources` SHALL be empty

### Requirement: Persistence is unchanged by streaming

A streaming turn SHALL persist exactly one user message row and exactly one assistant message row, written after generation completes and before the `done` event is emitted, with the assistant row's `content` equal to the complete accumulated reply. No partial or intermediate content SHALL be written to the database. The persisted `sources`, `answer_kind`, `model_version`, and `response_time_ms` columns SHALL be populated exactly as the non-streaming endpoint populates them.

#### Scenario: One assistant row with the full reply

- **GIVEN** a successful streaming turn that emitted several `token` events
- **WHEN** the conversation's messages are read back after the stream closes
- **THEN** exactly one assistant row SHALL have been added
- **AND** its `content` SHALL equal the `done` event's `reply`
- **AND** its `sources` SHALL equal the `done` event's `sources`

#### Scenario: Failed stream persists nothing

- **GIVEN** a streaming turn in which generation raises after several `token` events have been emitted
- **WHEN** the conversation's messages are read back after the stream closes
- **THEN** no assistant row SHALL have been added for that turn
- **AND** no user row SHALL have been added for that turn

### Requirement: Streaming error handling

When generation fails after the stream has opened, the system SHALL emit a single `error` event and close the stream, and SHALL NOT emit a `done` event for that turn. The client SHALL treat an `error` event, and equally an unexpected close of the stream without a `done` event, as a failed turn: it SHALL remove the optimistic user message and the streaming assistant message, SHALL clear the Thinking indicator, and SHALL surface the existing error notification.

#### Scenario: Failure after first token emits an error event

- **GIVEN** a generation LLM that raises after emitting two content deltas
- **WHEN** the client consumes `POST /api/v1/chat/stream`
- **THEN** two `token` events SHALL have been emitted
- **AND** the stream SHALL then emit exactly one `error` event carrying a `code` and a `message`
- **AND** no `done` event SHALL be emitted

#### Scenario: Error clears the Thinking state in the UI

- **GIVEN** a chat turn whose stream emits an `error` event
- **WHEN** the client finishes reading the stream
- **THEN** no message with the Thinking indicator SHALL remain in the thread
- **AND** the error notification SHALL be displayed

#### Scenario: Abrupt stream close clears the Thinking state in the UI

- **GIVEN** a chat turn whose stream closes without emitting either `done` or `error`
- **WHEN** the client finishes reading the stream
- **THEN** no message with the Thinking indicator SHALL remain in the thread
- **AND** the error notification SHALL be displayed

### Requirement: Gateway streams the chat stream without buffering

The gateway SHALL expose `POST /api/v1/chat/stream` and SHALL proxy it to chat_api as a pass-through stream, forwarding each SSE frame to the client as it is received rather than buffering the response body. The proxied response SHALL preserve `Content-Type: text/event-stream` and SHALL set `Cache-Control: no-cache` and `X-Accel-Buffering: no`. The gateway's existing buffered proxy helper SHALL continue to serve every other chat route unchanged.

#### Scenario: Gateway forwards frames incrementally

- **GIVEN** a chat_api stream that emits a `token` event and then pauses before the next frame
- **WHEN** the client reads the gateway's response
- **THEN** the first `token` event SHALL be readable by the client before chat_api emits its next frame

#### Scenario: Gateway preserves streaming headers

- **GIVEN** an authenticated request to the gateway's `/api/v1/chat/stream`
- **WHEN** the response headers are inspected
- **THEN** `Content-Type` SHALL be `text/event-stream`
- **AND** `X-Accel-Buffering` SHALL be `no`

#### Scenario: Non-streaming chat routes are unaffected

- **GIVEN** the gateway's existing chat routes for send, conversation CRUD, and feedback
- **WHEN** each is exercised
- **THEN** each SHALL return the same buffered JSON response as before this change

### Requirement: Non-streaming chat endpoint is preserved

`POST /api/v1/chat` on chat_api, its gateway proxy route, and the widget endpoint `POST /api/v1/public/chat` SHALL continue to behave exactly as they do today: same request body, same JSON response shape, same status codes, same headers, same persistence. The streaming path SHALL be additive.

#### Scenario: Existing endpoint is unchanged

- **GIVEN** an authenticated tenant user
- **WHEN** the user sends `POST /api/v1/chat` with a message
- **THEN** the response SHALL be a single JSON body containing `reply`, `sources`, `conversation_id`, `message_id`, and `disclaimer`
- **AND** the `Content-Type` SHALL be `application/json`

#### Scenario: Widget endpoint remains non-streaming

- **GIVEN** a valid widget key
- **WHEN** a request is sent to `POST /api/v1/public/chat`
- **THEN** the response SHALL be a single JSON body
- **AND** no event stream SHALL be opened

### Requirement: Client streaming kill switch

The portal SHALL select its chat transport from the `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` environment variable, defaulting to streaming when the variable is unset. When streaming is disabled, the portal SHALL send chat messages to the non-streaming `POST /api/v1/chat` endpoint using the pre-existing request/response handling.

#### Scenario: Streaming disabled falls back to the non-streaming endpoint

- **GIVEN** `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` is set to `false`
- **WHEN** the user sends a chat message
- **THEN** the request SHALL be sent to `/api/v1/chat`
- **AND** the Thinking indicator SHALL remain until the complete response arrives

#### Scenario: Unset flag defaults to streaming

- **GIVEN** `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` is unset
- **WHEN** the user sends a chat message
- **THEN** the request SHALL be sent to `/api/v1/chat/stream`
