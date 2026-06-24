## ADDED Requirements

### Requirement: Configurable chat API service URL

The chat API service URL SHALL be configurable via a `chat_api_url` setting that defaults to `http://localhost:8006`. The gateway proxy SHALL use this setting to route chat API requests, allowing Docker compose to override it with a service-specific URL.

#### Scenario: Gateway proxies to configured URL

- **GIVEN** a running gateway with `chat_api_url` set to `http://chat_api:8000`
- **WHEN** a chat request is proxied
- **THEN** the request SHALL be sent to `http://chat_api:8000/api/v1/chat/...`

#### Scenario: Default URL works for local development

- **GIVEN** a running gateway with default settings
- **WHEN** a chat request is proxied
- **THEN** the request SHALL be sent to `http://localhost:8006/api/v1/chat/...`
