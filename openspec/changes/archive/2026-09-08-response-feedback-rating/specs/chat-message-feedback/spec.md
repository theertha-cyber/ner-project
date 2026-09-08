## ADDED Requirements

### Requirement: Only eligible assistant answer messages are rateable

The system SHALL classify every assistant-generated chat message with an `answer_kind` of exactly one of: `answer` (a grounded RAG response), `clarification` (an entity-resolution or disambiguation prompt), `guardrail_blocked` (a declined response from the blocked-question-type guardrail), or `out_of_domain` (a declined response from domain classification). Only messages with `answer_kind = "answer"` SHALL be eligible for feedback. User-authored messages SHALL NOT be rateable under any circumstance, independent of `answer_kind`.

#### Scenario: Grounded answer message is eligible

- **GIVEN** an assistant message classified as `answer_kind: "answer"`
- **WHEN** a Business User submits a rating for that message
- **THEN** the rating SHALL be accepted and persisted

#### Scenario: Clarification message is not eligible

- **GIVEN** an assistant message classified as `answer_kind: "clarification"` (e.g. an entity-resolution disambiguation prompt)
- **WHEN** a rating is attempted against that message
- **THEN** the system SHALL reject the request
- **AND** no feedback row SHALL be created

#### Scenario: Guardrail-blocked message is not eligible

- **GIVEN** an assistant message classified as `answer_kind: "guardrail_blocked"` (a declined response to a blocked question type)
- **WHEN** a rating is attempted against that message
- **THEN** the system SHALL reject the request
- **AND** no feedback row SHALL be created

#### Scenario: Out-of-domain message is not eligible

- **GIVEN** an assistant message classified as `answer_kind: "out_of_domain"`
- **WHEN** a rating is attempted against that message
- **THEN** the system SHALL reject the request
- **AND** no feedback row SHALL be created

#### Scenario: User message is never eligible regardless of classification

- **GIVEN** a message with `role: "user"`
- **WHEN** a rating is attempted against that message's id
- **THEN** the system SHALL reject the request
- **AND** no feedback row SHALL be created

### Requirement: Feedback restricted to the Business User role

Only users with the `business_user` role SHALL be permitted to submit a rating, regardless of the target message's eligibility.

#### Scenario: Non-business_user role cannot submit a rating

- **GIVEN** an authenticated user with role `tenant_admin` or `system_admin`
- **WHEN** that user attempts to submit a rating for an eligible assistant answer message
- **THEN** the system SHALL reject the request with an authorization error
- **AND** no feedback row SHALL be created

### Requirement: One immutable rating per eligible assistant message

The system SHALL allow a Business User to submit exactly one rating (`up` or `down`) per eligible (`answer_kind = "answer"`) assistant message. Once a rating exists for a message, it SHALL be permanently fixed: no endpoint SHALL update or delete an existing rating, and any further submission attempt for that message — whether the same value or the opposite value — SHALL be rejected outright rather than silently accepted, ignored, or overwritten. The rating SHALL be persisted in a tenant-scoped `chat_message_feedback` table (per ADR-001, tenant-schema isolation), keyed uniquely by the assistant message it rates, and SHALL record the rating value, the rating user, and a timestamp.

#### Scenario: First rating on a message is accepted

- **GIVEN** an eligible assistant message with no existing feedback
- **WHEN** a Business User submits a `down` rating for that message
- **THEN** the rating SHALL be persisted
- **AND** subsequent reads of that message SHALL report `rating: "down"`

#### Scenario: Duplicate submission with the same value is rejected

- **GIVEN** an eligible assistant message already rated `up`
- **WHEN** a Business User submits another `up` rating for that same message
- **THEN** the attempt SHALL be rejected
- **AND** no second feedback row SHALL be created

#### Scenario: Duplicate submission with the opposite value is rejected

- **GIVEN** an eligible assistant message already rated `up`
- **WHEN** a Business User submits a `down` rating for that same message
- **THEN** the attempt SHALL be rejected
- **AND** the message's stored rating SHALL remain `up`, unchanged

#### Scenario: Rating persists across sessions and page refreshes

- **GIVEN** a message rated `up` in a prior session
- **WHEN** the user reloads the chat page or returns in a new session
- **THEN** the message SHALL still display the `up` rating as fixed and selected

### Requirement: Feedback data model supports future extension

The `chat_message_feedback` table SHALL be a standalone table (not a column on `chat_messages`) so that future fields — richer categories, free-text comments explaining negative ratings, or retraining-dataset annotations — can be added additively without a breaking migration or touching the high-traffic message read path. `chat_messages` SHALL separately carry `answer_kind` and `model_version` as properties of the message itself (independent of whether or how it is rated), so that model-attribution analytics remain possible even for unrated messages.

#### Scenario: Feedback table is independent of message content

- **GIVEN** the `chat_message_feedback` table schema
- **WHEN** inspected
- **THEN** it SHALL reference `chat_messages.id` by foreign key rather than embedding rating data inside the `chat_messages` row
- **AND** it SHALL NOT require any change to the `chat_messages` table to add new feedback attributes later

#### Scenario: A new feedback attribute can be added without breaking existing rows

- **GIVEN** the `chat_message_feedback` table already contains rated rows
- **WHEN** a future migration adds a nullable `category` or `comment` column to `chat_message_feedback`
- **THEN** existing rows SHALL remain valid with the new column `NULL`
- **AND** no change to `chat_messages` or the feedback-submission endpoint's core immutability behaviour SHALL be required

### Requirement: Assistant messages carry model-identity metadata for future evaluation

Each assistant message SHALL persist a `model_version` value identifying which model produced it, reusing the same `model_version` identifier already returned by model-serving inference (`InferResponse.model_version`, distinguishing base model `"0"` from trained versions) rather than introducing a new identifier. Where a chat turn's answer did not involve an NER inference call, `model_version` SHALL be `null`, signifying "not applicable" rather than "unknown."

#### Scenario: Assistant message from an NER-grounded answer records model_version

- **GIVEN** a chat turn whose answer is enriched by an NER inference call against a retrieved document snippet
- **WHEN** the assistant message is persisted
- **THEN** its `model_version` SHALL equal the `model_version` returned by that inference call

#### Scenario: Assistant message with no NER inference has a null model_version

- **GIVEN** a chat turn answered purely from SQL aggregation or document text with no NER inference call
- **WHEN** the assistant message is persisted
- **THEN** its `model_version` SHALL be `null`
