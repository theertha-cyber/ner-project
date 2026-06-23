## Purpose

Provide an embeddable chat widget that external websites can integrate via a `<script>` tag, allowing end-users to query tenant data through the RAG chatbot without requiring a platform login.

## Requirements

### Requirement: Hosted widget JS file

The system SHALL serve a JavaScript widget file at `GET /api/v1/public/widget.js` that tenants can embed on their websites via a `<script>` tag. The widget SHALL render a chat bubble in the bottom-right corner of the embedding page, with a slide-over chat panel. The widget JS file SHALL be served with `Content-Type: application/javascript` and appropriate CORS headers.

#### Scenario: Widget JS is served with correct headers

- **GIVEN** a valid tenant slug
- **WHEN** a browser requests `GET /api/v1/public/widget.js?tenant=<slug>`
- **THEN** the response SHALL have status 200
- **AND** `Content-Type` SHALL be `application/javascript`
- **AND** `Access-Control-Allow-Origin` SHALL be `*`
- **AND** the response body SHALL be valid JavaScript

#### Scenario: Widget renders chat bubble on page

- **GIVEN** a page with `<script src="/api/v1/public/widget.js?tenant=acme-corp&api_key=xyz">`
- **WHEN** the page loads
- **THEN** a chat bubble SHALL appear in the bottom-right corner
- **AND** clicking the bubble SHALL open a chat panel

#### Scenario: Widget sends messages to chat API

- **GIVEN** an open widget chat panel with a valid API key
- **WHEN** a user types a message and presses Enter
- **THEN** the widget SHALL send a POST to the chat API with the API key in the Authorization header
- **AND** the widget SHALL display the response in the chat panel

### Requirement: Widget API key management

The system SHALL expose endpoints for tenant admins to generate, list, and revoke widget API keys. Each key SHALL be a UUID v4 string, scoped to a single tenant, with read-only permissions. The key SHALL be stored hashed (SHA-256) in the `widget_api_keys` table.

#### Scenario: Generate widget API key

- **GIVEN** an authenticated Tenant Admin
- **WHEN** POST is sent to `/api/v1/widget-keys`
- **THEN** the response SHALL have status 201
- **AND** the response SHALL contain the raw API key (shown once)
- **AND** the key SHALL start with `ner_widget_` prefix

#### Scenario: List widget API keys

- **GIVEN** a tenant with 2 active widget API keys
- **WHEN** a Tenant Admin GETs `/api/v1/widget-keys`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 2 keys
- **AND** each key SHALL have `key_prefix` (first 8 chars), `created_at`, `last_used_at`
- **AND** the full key SHALL NOT be returned

#### Scenario: Revoke widget API key

- **GIVEN** an active widget API key
- **WHEN** a Tenant Admin sends DELETE to `/api/v1/widget-keys/{key_id}`
- **THEN** the response SHALL have status 204
- **AND** the key SHALL be immediately invalidated

#### Scenario: Chat with invalid widget API key

- **GIVEN** a revoked or invalid API key
- **WHEN** a widget sends a chat request with this key
- **THEN** the response SHALL have status 401

### Requirement: Widget-specific chat endpoint

The system SHALL expose a widget-specific chat endpoint at `POST /api/v1/public/chat` that authenticates via widget API key (Bearer token) instead of user JWT. This endpoint SHALL use the same RAG pipeline as the internal chat but SHALL NOT support conversation history (single-turn only for MVP). The tenant_id SHALL be resolved from the API key.

#### Scenario: Widget chat with valid API key

- **GIVEN** a valid widget API key for tenant acme-corp
- **WHEN** POST is sent to `/api/v1/public/chat` with `Authorization: Bearer ner_widget_<key>` and `{"message": "How many entities?"}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `reply` and `sources`
- **AND** the response SHALL NOT contain `conversation_id`

#### Scenario: Widget chat without API key

- **GIVEN** no API key
- **WHEN** POST is sent to `/api/v1/public/chat`
- **THEN** the response SHALL have status 401

### Requirement: CORS configuration for widget endpoints

All public widget endpoints (`/api/v1/public/*`) SHALL be configured with CORS allowing any origin (`Access-Control-Allow-Origin: *`), the `Authorization` header, and the `Content-Type` header.

#### Scenario: Widget endpoint responds to preflight

- **GIVEN** a browser from any origin
- **WHEN** OPTIONS is sent to `/api/v1/public/chat`
- **THEN** the response SHALL have status 204
- **AND** `Access-Control-Allow-Origin` SHALL be `*`
- **AND** `Access-Control-Allow-Headers` SHALL include `Authorization` and `Content-Type`
