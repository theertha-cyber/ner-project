## ADDED Requirements

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
