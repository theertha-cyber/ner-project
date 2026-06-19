## Context

The local development stack is defined by a single `docker-compose.yml`. The `postgres-test` service stores its data in the container's ephemeral filesystem — no named volume is declared. Consequently, `docker compose down` destroys all schemas, tables, and rows. Developers must manually run `alembic upgrade head` and `python -m src.gateway.seed` after every `compose up` to restore a usable state.

This change is infrastructure-only: no application code, API contracts, or data model changes.

## Goals / Non-Goals

**Goals:**

- Postgres data (schemas, tables, rows) survives `docker compose down` / `docker compose up` cycles.
- A single `docker compose up` fully bootstraps the database: migrations applied, seed admin created.
- No manual developer steps are required after first run.
- The fix is idempotent — running `compose up` on an already-initialised database has no side effects.

**Non-Goals:**

- Automated DB reset / clean-slate workflow (intentionally left to `docker compose down -v`).
- Production database lifecycle management — this is local dev only.
- Changing application startup logic or the gateway `lifespan` hook.
- Modifying Alembic migration files or the seed script itself.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation | Separate PostgreSQL schema per tenant | The named volume must preserve the full postgres data directory so tenant schemas survive restarts. No constraint on the init mechanism. |

All other ADRs (002–008) cover model strategy, serving topology, governance, agents, training, chatbot architecture, and model defaults — none constrain local dev infrastructure.

## Decisions

### Decision 1: Named Docker volume for postgres data directory

**Choice:** Mount a named volume `postgres-data` at `/var/lib/postgresql/data` in `postgres-test`. Register it in the top-level `volumes` block.

**Rationale:** This is the standard Docker pattern for stateful services. A named volume is managed by Docker, survives `compose down`, and is only removed by explicit `compose down -v`. It requires zero application code change and zero operational overhead.

**Alternatives considered:**
- **Bind mount to a host directory** (e.g., `./data/postgres:/var/lib/postgresql/data`) — works but creates a host-owned directory in the repo, risks permission issues on Windows/Linux, and clutters `.gitignore`. Named volumes are portable and Docker-managed.
- **`compose stop` instead of `compose down`** — stops containers without removing them, so data persists without a volume. Rejected because it requires developer discipline and doesn't survive explicit `down` or CI teardown.

---

### Decision 2: Dedicated `db-init` one-shot service for migrations and seeding

**Choice:** Add a `db-init` service to `docker-compose.yml` that uses the existing root image, runs `alembic upgrade head && python -m src.gateway.seed`, and declares `restart: "no"`. All application services that require the schema add `depends_on: db-init: condition: service_completed_successfully`.

**Rationale:**
- Migrations are infrastructure bootstrap, not application responsibility. Decoupling them into their own service makes the dependency graph explicit and honest: services only start once the schema exists.
- The seed script already guards against duplicate inserts (`SELECT` before `INSERT`), making both steps fully idempotent — safe to run on every `compose up`.
- The same root `Dockerfile` image is reused with an overridden `command`, so no new image is needed.
- `service_completed_successfully` is the correct compose condition for a one-shot init container — it waits for exit code 0.

**Alternatives considered:**
- **Entrypoint script on the gateway container** — wraps `alembic upgrade head && python -m src.gateway.seed && exec uvicorn ...`. Simpler but conflates migration responsibility with the gateway process. If the gateway is restarted independently (e.g., after a code change), migrations re-run unnecessarily. Also doesn't help services other than gateway that also depend on the schema.
- **`lifespan` hook in `src/gateway/main.py`** — call alembic programmatically at FastAPI startup. Rejected: mixes runtime application code with infrastructure setup, and other services (document_service, annotation_service, etc.) would still start on a bare schema.
- **`POSTGRES_INITDB_SCRIPTS` docker entrypoint** — PostgreSQL supports running `.sql` or `.sh` scripts on first init via `/docker-entrypoint-initdb.d/`. Rejected: only runs on a fresh/empty data directory, not on subsequent startups. Would not re-apply new migrations added during development.

---

### Decision 3: `db-init` commands run as a combined shell invocation

**Choice:** `command: sh -c "alembic upgrade head && python -m src.gateway.seed"`

**Rationale:** Both commands must run sequentially with failure propagation (`&&`). A shell wrapper is the simplest compose-native way to express this without a custom entrypoint script or an additional file in the repo.

**Alternatives considered:**
- **Separate `alembic-migrate` and `db-seed` services chained with `depends_on`** — more explicit but adds two services and two `depends_on` entries to every application service. The added verbosity is not justified for two commands that always run together.
- **A dedicated `scripts/init-db.sh` entrypoint script** — cleaner if the init logic grows, but unnecessary for two commands. Can be introduced later without changing the spec.

## Risks / Trade-offs

- [**`compose down -v` destroys all data**] → This is the intended escape hatch for a full reset. Document it clearly in the project README / developer guide.
- [**`db-init` adds latency to `compose up`**] → Alembic and seed are fast (< 5 seconds on a warm DB). Application services still wait on `service_completed_successfully`, which was previously implicit. Latency increase is negligible.
- [**Dockerfile gains an `ENTRYPOINT` later**] → If a future change adds an `ENTRYPOINT` to the root Dockerfile, the `command:` override in `db-init` will compose with it rather than replace it. Flag for review at that point.
- [**`db-init` failure silently blocks all services**] → `compose up` will stall if init fails (e.g., bad migration). This is the desired failure mode — a partially-initialised stack is worse than no stack. Developers see the `db-init` logs.

## Migration Plan

1. Add `postgres-data` volume to `postgres-test` in `docker-compose.yml`.
2. Add `db-init` service definition.
3. Add `depends_on: db-init: condition: service_completed_successfully` to `gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction`.
4. Add `postgres-data:` to the top-level `volumes` block.
5. Run `docker compose down -v` once to clear any existing ephemeral state, then `docker compose up` to validate the new flow.

**Rollback:** Remove the volume mount and `db-init` service from `docker-compose.yml`. Run `docker compose down -v` to clean up the named volume. No application code was changed.

## Open Questions

- Should a developer convenience target (e.g., `make db-reset`) be added as an alias for `docker compose down -v && docker compose up`? Not a blocker — `compose down -v` is sufficient and standard.
