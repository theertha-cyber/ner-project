## Context

The extraction Celery worker (`celery_worker_extraction`) runs in a Docker container but needs to call two host services:

1. **Document Service** (`src.document_service.main:app` on port 8001) — fetches document text via `GET /api/v1/tenants/{tenant_id}/documents/{doc_id}/text`
2. **Model Serving Layer** (`src.model_serving.main:app` on port 8004) — runs inference via `POST /internal/v1/infer`

Neither service is containerized in `docker-compose.yml`. They run directly on the host via `uvicorn --reload`. The worker hardcodes `http://document_service:8001` (line 110 of worker.py) and uses `settings.model_serving_url` defaulting to `http://localhost:8004` — both unresolvable from inside the container.

The Dockerfile was already patched with `psycopg2-binary` (previous change) to fix the initial `ModuleNotFoundError`, but the worker still can't process documents because API calls fail silently.

## Goals / Non-Goals

**Goals:**
- Extraction worker container can reach document service and model serving on the host
- Hostnames are configurable via environment variables, not hardcoded
- Local development (running uvicorn directly) continues to work with `localhost` defaults
- Minimal code changes — this is an infrastructure configuration fix

**Non-Goals:**
- Containerizing document_service or model_serving — those remain host-processes
- Changing the extraction worker's processing logic
- Adding service discovery or DNS infrastructure

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-003 Model Serving Topology | Extraction Service MUST route inference through Serving Layer internal endpoint | We preserve the routing — only the hostname changes |

## Decisions

### Decision 1: `host.docker.internal` for host service discovery

**Choice:** Use Docker's `host.docker.internal` DNS name (with `extra_hosts` fallback for Linux/WSL2) to reach host services from the container.

**Rationale:** Simplest approach — no new infrastructure, no containerizing additional services, works on both Docker Desktop and WSL2. The `extra_hosts: ["host.docker.internal:host-gateway"]` directive ensures it works on Linux hosts where `host.docker.internal` isn't automatically resolved.

**Alternatives considered:**
- **Add `document_service` to docker-compose** — Would require containerizing the document service and setting up port mappings. Bigger scope, more moving parts.
- **Run the worker on the host** — Avoids Docker networking entirely, but then we need `psycopg2` installed locally and lose container isolation for the worker.
- **`network_mode: host`** — Simplest but breaks container networking isolation and prevents the worker from reaching `postgres-test` and `redis` by their docker-compose hostnames.

### Decision 2: Configurable service URLs via `Settings`

**Choice:** Add `document_service_url: str = "http://localhost:8001"` to `Settings`, and use it in `worker.py` instead of the hardcoded `http://document_service:8001`. The existing `model_serving_url` is already in `Settings` and just needs the Docker env var override.

**Rationale:** Keeps local dev working (`localhost` defaults) while allowing Docker env vars (`NER_DOCUMENT_SERVICE_URL=http://host.docker.internal:8001`) to override for the container context. Follows the existing pattern of `NER_DATABASE_URL`, `NER_REDIS_URL`, etc.

**Alternatives considered:**
- **Inline env var read in worker.py** — Duplicates env-var logic that `pydantic-settings` already handles centrally.
- **Hardcode `host.docker.internal` in the worker** — Breaks local development.

## Risks / Trade-offs

- [**`host.docker.internal` not available on all Docker hosts**] → Mitigation: The `extra_hosts` directive in docker-compose ensures resolution on Linux/WSL2. Docker Desktop supports it natively.
- [**Hardcoded `document_service:8001` might exist elsewhere**] → Mitigation: Only one occurrence in worker.py. Grep-confirmed.
- [**Port conflict if host services change ports**] → Mitigation: Settings are env-overridable; no code change needed if ports change.

## Migration Plan

1. Add `document_service_url` to `src/shared/config.py`
2. Update `worker.py` to use `settings.document_service_url` instead of hardcoded URL
3. Update `docker-compose.yml` to add `extra_hosts` and env vars to `celery_worker_extraction`
4. Rebuild container and restart
5. Test: trigger batch extraction, verify `failed_count=0, processed_count=1`
6. Rollback: revert docker-compose env vars and rebuild; local dev unaffected

## Open Questions

- None — the user confirmed `host.docker.internal` is the preferred approach.
