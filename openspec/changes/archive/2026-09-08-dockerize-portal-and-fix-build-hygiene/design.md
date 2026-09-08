## Context

Backend services are containerized via a single shared root `Dockerfile` and `docker-compose.yml` (established in the archived `dockerize-backend-services` change). The portal (`src/portal`, Next.js 14+, `output: "standalone"` already set) was never added. Build context hygiene (`.dockerignore`) was never addressed for any image. A stale `src/training_service/Dockerfile` and two dead `requirements.txt` files are leftovers from before the shared-Dockerfile pattern was adopted. Gateway's `NER_CHAT_API_URL` still points at `host.docker.internal:8006`, a holdover from when `chat_api` ran on the host outside Compose — it is now a `docker-compose.yml` service (`chat_api`, container port 8000) and should be reached via Docker DNS like every other sibling service, consistent with the existing `local-dev-stack` "Stable Inter-Service Communication via Docker DNS" requirement.

## Goals / Non-Goals

**Goals:**

- Portal buildable and runnable via `docker compose up` alongside backend services.
- All image builds (root Python image, portal image) exclude VCS, secrets, dependency caches, and non-build artifacts from build context via `.dockerignore`.
- Root Dockerfile split into build and runtime stages to shrink final image.
- Remove dead/duplicate Docker-adjacent files (`src/training_service/Dockerfile`, two `requirements.txt`).
- Gateway → chat_api traffic uses Docker service DNS, matching the pattern already used for every other inter-service call.

**Non-Goals:**

- Production/Kubernetes manifests (`deploy/k8s/**`) — untouched.
- CI pipeline changes (no CI config exists referencing these files today; if discovered, flagged not fixed here).
- Portal environment/secrets management beyond what's needed to boot against the existing gateway.
- Changing `celery_worker`/`celery_worker_extraction` bind-mount behavior — documented as-is, not modified.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| None | No ADR governs Docker build/compose topology. | — |

## Decisions

### Decision 1: Portal Dockerfile — 3-stage build

**Choice:** `src/portal/Dockerfile` with `deps` (install node_modules), `build` (Next.js build, produces `.next/standalone`), and `runner` (minimal `node:20-alpine`, copies only `.next/standalone`, `.next/static`, `public`) stages. Runs as non-root, `CMD ["node", "server.js"]`, `EXPOSE 3000`.

**Rationale:** `output: "standalone"` was already added specifically to enable this pattern (it bundles a minimal `server.js` + only the traced dependencies). Matches the size/security benefits already being introduced for the root Dockerfile (Decision 2).

**Alternatives considered:**
- Single-stage `node:20` image running `next start` — simpler but ships full `node_modules` and dev toolchain into the final image; rejected given `standalone` output makes multi-stage nearly free.

### Decision 2: Root Dockerfile — multi-stage (builder + runtime)

**Choice:** Stage `builder` (python:3.11-slim + poetry, installs deps into a venv or `--target`), stage final `python:3.11-slim` runtime that copies only the installed site-packages and app source — no Poetry, no pip cache, no build tooling in the final layer.

**Rationale:** Every backend service already shares this one Dockerfile; shrinking it benefits all nine service images at once. Poetry itself and its transitive install metadata have no runtime purpose.

**Alternatives considered:**
- Leave single-stage, only add `.dockerignore` — smaller win, but this is a natural pairing with the `.dockerignore` work and was explicitly flagged in the audit; doing both in one pass avoids a second image-layer churn later.

### Decision 3: Gateway → chat_api via Docker DNS

**Choice:** Change `NER_CHAT_API_URL` in `docker-compose.yml`'s `gateway` service from `http://host.docker.internal:8006` to `http://chat_api:8000` (container-internal port, matching how `chat_api` binds inside its own container). Add `chat_api: condition: service_started` to gateway's `depends_on`.

**Rationale:** `chat_api` is already a compose-managed service on the same Docker network; `host.docker.internal` is unnecessary indirection that only works with Docker Desktop's special DNS shim and silently breaks on plain Linux Docker Engine. This aligns with the existing (already-written) `local-dev-stack` requirement banning `host.docker.internal` for sibling-service calls.

**Alternatives considered:**
- Keep `host.docker.internal` but document the limitation — rejected, spec already forbids this pattern for exactly this reason.

### Decision 4: Delete stale `src/training_service/Dockerfile` and dead `requirements.txt` files

**Choice:** Delete outright rather than deprecate-in-place.

**Rationale:** `docker-compose.yml` already builds `training_service` from the root `Dockerfile` (verified: no compose service references `src/training_service/Dockerfile` or either `requirements.txt`). Grep confirms no other repo file (docs, CI, scripts) references these paths outside historical/archived OpenSpec change records, which are immutable history and unaffected by deletion.

**Alternatives considered:**
- Keep as reference — rejected; a Dockerfile with manually pinned deps that silently diverge from `poetry.lock` is an active foot-gun, not a harmless artifact.

## Risks / Trade-offs

- [Deleting `src/training_service/Dockerfile` could break an undiscovered external build pipeline outside this repo.] → Grep confirms zero in-repo references outside archived (immutable) change history; flagged as an Open Question in proposal.md for explicit confirmation before merge.
- [Portal's `.next/standalone` output layout can shift between Next.js minor versions, silently breaking the Dockerfile's COPY paths.] → Pin the copy to the documented standalone layout (`/.next/standalone`, `/.next/static`, `/public`) and verify with a real `docker compose build portal` + `docker compose up portal` run before merge.
- [Multi-stage root Dockerfile could accidentally drop a runtime dependency that was previously present transitively via Poetry's own install (e.g. a C extension's shared library).] → Verify with a full `docker compose up` smoke test across all nine services after the change, not just a build-succeeds check.
- [`.dockerignore` too broad could exclude a file a Dockerfile actually needs (e.g. `alembic/`, `tenant_schema_ddl.py`).] → Explicitly allow-list what root `Dockerfile` COPYs (`src/`, `alembic/`, `alembic.ini`, `tenant_schema_ddl.py`, `pyproject.toml`, `poetry.lock`) rather than only deny-listing; test full compose build after.

## Migration Plan

1. Add `.dockerignore` (root, portal) — no behavior change, verify builds still succeed.
2. Add `src/portal/Dockerfile` + `portal` compose service — additive, no existing service affected.
3. Fix gateway `NER_CHAT_API_URL` + `depends_on` — verify gateway→chat_api call still succeeds via `docker compose up gateway chat_api` before wider rollout.
4. Convert root `Dockerfile` to multi-stage — rebuild and smoke-test all nine backend services (`docker compose build && docker compose up`, hit each `/health` endpoint).
5. Delete `src/training_service/Dockerfile`, two `requirements.txt` files — final cleanup step, done last so any breakage in steps 1-4 isn't confused with deletions.

Rollback: each step is an independent commit; revert the specific commit if a step's smoke test fails. No data migrations involved.

## Open Questions

- None beyond those already tracked in proposal.md's Open Questions (external references to deleted files; portal runtime env vars).
