## Context

The gateway proxies chat API requests via `chat_proxy.py`, which currently constructs the target URL as `f"http://localhost:{settings.chat_api_port}"`. This works when the gateway and chat-api both run directly on the host, but breaks in Docker: `localhost` inside the gateway container refers to the container itself, not the host running the chat-api.

Other service proxies (`extraction_proxy`, `document_proxy`) use full URL settings (`extraction_service_url`, `document_service_url`) rather than port-based construction, allowing Docker compose to override them with service DNS names.

## Goals / Non-Goals

**Goals:**

- Make `CHAT_API_BASE` configurable as a full URL that works in both local and Docker environments
- Match the existing pattern used by other service proxies
- Keep `localhost:8006` as the default for local development

**Non-Goals:**

- No changes to the chat-api service itself
- No changes to Docker networking beyond the env var override
- No removal of `chat_api_port` (backward compatibility — may be cleaned up separately)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-007 | Chatbot Architecture — Full RAG with Guardrails | Chat API is a separate microservice accessed through the gateway proxy; the proxy must be able to reach it |

## Decisions

### Decision 1: Full URL setting matching existing pattern

**Choice:** Add `chat_api_url: str = "http://localhost:8006"` to `Settings` and use it in `chat_proxy.py` instead of `f"http://localhost:{settings.chat_api_port}"`.

**Rationale:** Every other service proxy uses a full URL setting (`extraction_service_url`, `document_service_url`, `model_serving_url`). This is the consistent pattern. Docker compose overrides via `NER_CHAT_API_URL=http://chat_api:8000` (or `http://host.docker.internal:8006` for host-local services).

**Alternatives considered:**
- Keep port-based approach and document that `NER_CHAT_API_PORT` should be set to `8006` with `host.docker.internal` — doesn't work because the URL scheme and hostname need to change, not just the port
- Use `host.docker.internal` as default — breaks for non-Docker local development and for Docker-on-Linux where `host.docker.internal` isn't available by default

## Risks / Trade-offs

- [If both `chat_api_url` and `chat_api_port` are set to inconsistent values] → The new `chat_api_url` takes precedence in `chat_proxy.py`; `chat_api_port` is only used by `chat_proxy.py` so this is safe
- [Docker on Linux doesn't support `host.docker.internal` by default] → The compose override would use `http://chat_api:8000` when chat-api runs in Docker, or `--add-host host.docker.internal:host-gateway` flag for host-local services

## Migration Plan

1. Add `chat_api_url: str = "http://localhost:8006"` to `Settings` in `config.py`
2. Replace `CHAT_API_BASE = f"http://localhost:{settings.chat_api_port}"` with `CHAT_API_BASE = settings.chat_api_url` in `chat_proxy.py`
3. Add `NER_CHAT_API_URL: "http://host.docker.internal:8006"` to the gateway service env in `docker-compose.yml`

Rollback: Revert `chat_proxy.py` to use `chat_api_port`; remove the docker-compose env var.

## Open Questions

- Should we remove `chat_api_port` from `Settings` entirely? (Proposed: leave it for now to avoid a breaking change; can clean up in a future change.)
