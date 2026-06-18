## Why

The extraction Celery worker runs inside a Docker container but needs to call `document_service` (port 8001) and `model_serving` (port 8004), which run on the host. Currently, the worker uses hardcoded hostnames (`document_service:8001`) and `localhost:8004` that don't resolve to the host from inside the container, causing every document processing attempt to fail silently with `failed_count=1, processed_count=0`.

## What Changes

- Add configurable settings for `document_service_url` and update `model_serving_url` to be overridable via env vars for the container context
- Update `docker-compose.yml` to set `NER_DOCUMENT_SERVICE_URL` and `NER_MODEL_SERVING_URL` to `http://host.docker.internal:<port>` for the `celery_worker_extraction` service
- Add `extra_hosts: ["host.docker.internal:host-gateway"]` to enable host resolution on Linux/WSL2
- Update `worker.py` to use `settings.document_service_url` instead of the hardcoded `document_service:8001`
- Update `settings` defaults to keep `localhost` for local development
- Track the already-applied Dockerfile `psycopg2-binary` fix in the change scope

## Capabilities

### New Capabilities

- `worker-network-config`: Configure the extraction worker container to reach host services via `host.docker.internal` with env-var-driven URLs

### Modified Capabilities

- *None (no spec-level requirement changes)*

## Impact

- `src/extraction_service/worker.py`: Replace hardcoded `document_service:8001` URL with `settings.document_service_url`
- `src/shared/config.py`: Add `document_service_url` setting; ensure `model_serving_url` is env-overridable
- `docker-compose.yml`: Add `extra_hosts` and env vars to `celery_worker_extraction` service
- `src/training_service/Dockerfile`: Already patched with `psycopg2-binary` (being tracked here for completeness)

## Open Questions

- Does `host.docker.internal` work on the current Docker Desktop / WSL2 setup without `extra_hosts`? (Safe to add it regardless)
- Should the `celery_worker` (training) service also get these env vars for consistency? (Not needed now — its worker uses different URLs)
