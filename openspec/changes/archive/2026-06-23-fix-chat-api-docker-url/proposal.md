## Why

The gateway proxies chat API requests to `http://localhost:{chat_api_port}` (port 8006), but when the gateway runs in Docker, `localhost` resolves to the gateway container itself, not the host. The chat-api service running locally via uvicorn is unreachable, causing all chat API requests to return 404.

## What Changes

- Add `chat_api_url` setting to `src/shared/config.py` as a full URL (consistent with `extraction_service_url`, `document_service_url`, `model_serving_url`)
- Update `src/gateway/api/v1/chat_proxy.py` to use `settings.chat_api_url` instead of `f"http://localhost:{settings.chat_api_port}"`
- Add `NER_CHAT_API_URL=http://host.docker.internal:8006` override to the `gateway` service environment in `docker-compose.yml`

## Capabilities

### New Capabilities

*(none — this is a deployment configuration fix)*

### Modified Capabilities

- `chat-api`: Fix the internal service URL resolution so the gateway proxy can reach the chat-api service in Docker environments; default (`localhost:8006`) unchanged for local development

## Impact

- **Code**: One line change in `config.py` (add `chat_api_url`), one line change in `chat_proxy.py` (use the new setting)
- **Deployment**: One env var added to `docker-compose.yml` for the gateway service
- **No API changes**: All public API paths remain unchanged
- **No database changes**: No migrations

## Open Questions

- Is `chat_api_port` still used anywhere else? (If not, it could be removed, but keeping it avoids a breaking change.)
