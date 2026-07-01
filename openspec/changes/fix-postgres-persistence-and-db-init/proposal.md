## Why

The `postgres-test` service in `docker-compose.yml` has no named volume, so every `docker compose down` destroys all database schemas, tables, and data. This forces developers to manually run `alembic upgrade head` and `python -m src.gateway.seed` after every `compose up`, breaking the single-command startup promise of the local dev stack.

## What Changes

- Add a named Docker volume `postgres-data` mounted at `/var/lib/postgresql/data` in the `postgres-test` service so database contents survive `docker compose down` / `docker compose up` cycles.
- Add a `db-init` one-shot service that runs `alembic upgrade head` and `python -m src.gateway.seed` on every `compose up`, succeeding silently when schemas and the seed admin already exist (both operations are idempotent).
- Add `depends_on: db-init: condition: service_completed_successfully` to every application service that requires the schema (`gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction`).
- Register `postgres-data` in the top-level `volumes` block alongside the existing `minio-data` entry.

## Capabilities

### New Capabilities

*(none)*

### Modified Capabilities

- `local-dev-stack`: Requirements extend to mandate (1) postgres data persists across `compose down` / `compose up` via a named volume, and (2) DB migrations and seed data are applied automatically before any application service starts, requiring no manual developer steps after first run.

## Impact

- **`docker-compose.yml`**: three changes — postgres volume mount, new `db-init` service definition, updated `depends_on` blocks on all application services.
- **`Dockerfile`** (or a new `entrypoint/init.sh`): the `db-init` service needs `alembic` and the `src.gateway.seed` module available; the existing root `Dockerfile` already installs all dependencies, so the same image can be reused with a different `command`.
- **Developer workflow**: `docker compose down` no longer wipes the database; `docker compose up` is fully self-bootstrapping with no manual follow-up steps required.
- **`openspec/specs/local-dev-stack/spec.md`**: two new requirements and scenarios will be added.
- **No API or schema changes** — this is infrastructure-only.

## Open Questions

- Should `compose down -v` (explicit volume removal) remain the intentional escape hatch for a full database reset, or do we also want a `make db-reset` target for convenience? 
answer: No blocker — `compose down -v` works today and is the standard Docker idiom.
- The `db-init` service uses the same root `Dockerfile` image with an overridden `command`. If the Dockerfile ever gains an `ENTRYPOINT` instead of a bare `CMD`, the override approach needs revisiting.
