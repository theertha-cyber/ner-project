## ADDED Requirements

### Requirement: Message feedback submission endpoint

The system SHALL expose `POST /api/v1/chat/messages/{message_id}/feedback` accepting `{"rating": "up" | "down"}` from an authenticated `business_user`. On success the endpoint SHALL return status 201 with the created feedback record. If the target message does not exist, does not belong to the caller's tenant, is not an assistant message, or is an assistant message whose `answer_kind` is not `"answer"` (i.e. it is a `clarification`, `guardrail_blocked`, or `out_of_domain` message), the endpoint SHALL return 404. If the message already has a rating, the endpoint SHALL return 409 with the existing rating in the response body — the endpoint SHALL NOT overwrite, update, or delete an existing rating under any request. If the caller is not a `business_user`, the endpoint SHALL return 403.

#### Scenario: Business user submits first rating on an eligible answer

- **GIVEN** an assistant message with `answer_kind: "answer"` and no existing feedback, in a conversation owned by the caller
- **WHEN** the Business User sends `POST /api/v1/chat/messages/{message_id}/feedback` with `{"rating": "up"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `{"message_id", "rating": "up", "created_at"}`

#### Scenario: Rating an already-rated message returns 409 and does not overwrite

- **GIVEN** an assistant message already rated `down`
- **WHEN** the Business User sends a new rating request (same or opposite value) for that message
- **THEN** the response SHALL have status 409
- **AND** the response body SHALL contain the existing `rating: "down"`
- **AND** the stored rating SHALL remain `down`, unchanged by the request

#### Scenario: Rating a user message returns 404

- **GIVEN** a message with `role: "user"`
- **WHEN** a rating request targets that message's id
- **THEN** the response SHALL have status 404

#### Scenario: Rating a clarification message returns 404

- **GIVEN** an assistant message with `answer_kind: "clarification"`
- **WHEN** a rating request targets that message's id
- **THEN** the response SHALL have status 404

#### Scenario: Rating a guardrail-blocked message returns 404

- **GIVEN** an assistant message with `answer_kind: "guardrail_blocked"`
- **WHEN** a rating request targets that message's id
- **THEN** the response SHALL have status 404

#### Scenario: Rating an out-of-domain message returns 404

- **GIVEN** an assistant message with `answer_kind: "out_of_domain"`
- **WHEN** a rating request targets that message's id
- **THEN** the response SHALL have status 404

#### Scenario: Non-business_user role is rejected

- **GIVEN** an authenticated `tenant_admin`
- **WHEN** they send `POST /api/v1/chat/messages/{message_id}/feedback`
- **THEN** the response SHALL have status 403

#### Scenario: Unauthenticated request rejected

- **GIVEN** no JWT token
- **WHEN** `POST /api/v1/chat/messages/{message_id}/feedback` is called
- **THEN** the response SHALL have status 401

## MODIFIED Requirements

### Requirement: Conversation CRUD

The system SHALL expose endpoints to create, list, retrieve, and delete conversations. Each conversation SHALL be scoped to a single tenant and user. Messages SHALL be stored with `role` (user/assistant), `content`, `sources` (JSON array), `answer_kind` (`"answer" | "clarification" | "guardrail_blocked" | "out_of_domain"`, `null`/absent for user messages), and `model_version` (string or `null`, only meaningful for assistant messages). Each returned message SHALL additionally include a `feedback` field: `null` if unrated, or `{"rating": "up" | "down", "created_at": <timestamp>}` if a Business User has rated it.

#### Scenario: List conversations for a user

- **GIVEN** a user with 3 existing conversations
- **WHEN** a Tenant Admin GETs `/api/v1/chat/conversations`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 3 conversations
- **AND** each conversation SHALL have `id`, `title`, `created_at`, `message_count`

#### Scenario: Get conversation messages

- **GIVEN** a conversation with 5 messages
- **WHEN** a Tenant Admin GETs `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 5 messages
- **AND** each message SHALL have `role`, `content`, `sources`, `created_at`, `answer_kind`, `model_version`, `feedback`

#### Scenario: Get conversation messages includes existing feedback

- **GIVEN** a conversation containing an assistant message previously rated `up`
- **WHEN** a Business User GETs that conversation
- **THEN** the rated message's `feedback` field SHALL equal `{"rating": "up", "created_at": <timestamp>}`

#### Scenario: Get conversation messages reports answer_kind for non-answer replies

- **GIVEN** a conversation containing a clarification prompt and a guardrail-blocked decline
- **WHEN** a Business User GETs that conversation
- **THEN** the clarification message's `answer_kind` SHALL equal `"clarification"`
- **AND** the guardrail-blocked message's `answer_kind` SHALL equal `"guardrail_blocked"`
- **AND** neither message's `feedback` SHALL be settable (per the feedback endpoint's 404 behaviour)

#### Scenario: Delete conversation

- **GIVEN** a conversation owned by user A
- **WHEN** user A sends DELETE `/api/v1/chat/conversations/{conv_id}`
- **THEN** the response SHALL have status 204

#### Scenario: Delete another user's conversation returns 404

- **GIVEN** a conversation owned by user A
- **WHEN** user B sends DELETE to the same conversation
- **THEN** the response SHALL have status 404
