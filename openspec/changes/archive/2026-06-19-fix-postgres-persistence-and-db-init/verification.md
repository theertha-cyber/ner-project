# Verification Plan

**Change:** fix-postgres-persistence-and-db-init
**Generated:** 2026-06-19
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | local-dev-stack | Postgres Data Persistence Across Compose Cycles | Database contents survive docker compose down and up | Given migrations have run and at least one tenant row exists, when `docker compose down` then `docker compose up` is run (without `-v`), then the tenant row is still queryable and no manual step was taken | Manual: query `SELECT * FROM public.tenants` before and after cycle | - [ ] |
| 2 | local-dev-stack | Postgres Data Persistence Across Compose Cycles | Named volume is declared alongside minio-data | Given the `docker-compose.yml`, when the top-level `volumes` block is inspected, then both `minio-data` and `postgres-data` are present | Code review: inspect `docker-compose.yml` volumes block | - [ ] |
| 3 | local-dev-stack | Postgres Data Persistence Across Compose Cycles | Explicit volume removal resets the database | Given the stack is stopped, when `docker compose down -v` is run then `docker compose up` is run, then the database is empty (no tenants, no tables beyond alembic_version) | Manual: `docker compose down -v && docker compose up` — check `ner_dev` DB is empty before `db-init` runs | - [ ] |
| 4 | local-dev-stack | Automated Database Initialization on Compose Up | Migrations are applied automatically on compose up | Given a valid `.env` and a healthy postgres container, when `docker compose up` is run from scratch, then `db-init` exits 0 and all Alembic migration versions are present in `alembic_version` before any app service starts | Manual: inspect `db-init` logs; `SELECT version_num FROM alembic_version` shows all versions | - [ ] |
| 5 | local-dev-stack | Automated Database Initialization on Compose Up | Seed admin is created automatically on compose up | Given `db-init` has run `alembic upgrade head` successfully, when `python -m src.gateway.seed` runs, then `id='system'` exists in `public.tenants` and `admin@nerplatform.io` with role `system_admin` exists in `public.tenant_users` | Manual: `SELECT id FROM public.tenants WHERE id='system'` and `SELECT email FROM public.tenant_users WHERE role='system_admin'` | - [ ] |
| 6 | local-dev-stack | Automated Database Initialization on Compose Up | Init is idempotent on subsequent compose up cycles | Given the database is already fully initialised, when `docker compose down` then `docker compose up` is run, then `db-init` exits 0, no duplicate tenants or admin users exist, and Alembic reports no new migrations | Manual: count rows in `public.tenants` and `public.tenant_users` before and after a second cycle | - [ ] |
| 7 | local-dev-stack | Automated Database Initialization on Compose Up | Application services wait for db-init to complete | Given `docker compose up` is starting, when `db-init` is still running, then `gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, and `celery_worker_extraction` do not start until `db-init` exits 0 | Code review: each of those 7 services has `depends_on: db-init: condition: service_completed_successfully` | - [ ] |
| 8 | local-dev-stack | Automated Database Initialization on Compose Up | Stack startup fails fast if db-init fails | Given `db-init` exits with a non-zero code, when `docker compose up` is running, then none of the application services start and `db-init` logs are visible in compose output | Manual: temporarily break a migration to force failure; confirm app services do not start | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Volume mount path | AI may mount the volume at the wrong path (e.g., `/var/lib/postgresql` instead of `/var/lib/postgresql/data`), causing postgres to ignore the volume and store data in the container layer | Verify the volume entry in `postgres-test` is exactly `postgres-data:/var/lib/postgresql/data` — the trailing `/data` is mandatory |
| 2 | `depends_on` condition value | AI may use `condition: service_healthy` instead of `condition: service_completed_successfully` for `db-init`; a one-shot service never becomes "healthy" so this would deadlock | Grep `docker-compose.yml` for `db-init` depends_on entries — every reference to `db-init` must use `service_completed_successfully` |
| 3 | `restart` policy on `db-init` | AI may omit `restart: "no"` on `db-init`, causing it to restart indefinitely after its first successful exit | Confirm `db-init` has `restart: "no"` in `docker-compose.yml` |
| 4 | Missing services in `depends_on` | AI may add `depends_on: db-init` to `gateway` only and omit the other six services that also require the schema | Verify all 7 services (`gateway`, `document_service`, `extraction_service`, `annotation_service`, `training_service`, `celery_worker`, `celery_worker_extraction`) have the `db-init` dependency |
| 5 | Top-level volumes block omission | AI may add the volume mount inside `postgres-test` but forget to add `postgres-data:` to the top-level `volumes:` block, causing compose to reject the file | Confirm top-level `volumes:` block contains both `minio-data:` and `postgres-data:` |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation | Separate PostgreSQL schema per tenant within a single `ner_dev` database | The named volume must persist the full postgres data directory so tenant schemas survive restarts; the init service must not drop or recreate existing schemas | After a compose down/up cycle (without `-v`), confirm tenant schemas created in a prior session still exist: `SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'` |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 — Row present after compose down/up: `SELECT count(*) FROM public.tenants` returns same count before and after the cycle (without `-v`); no manual steps taken
- [ ] Scenario 2 — Volumes block: `docker-compose.yml` diff shows `postgres-data:` in the top-level `volumes` block alongside `minio-data:`
- [ ] Scenario 3 — Volume removal resets DB: `docker compose down -v && docker compose up` shows a fresh database before `db-init` seed runs (`SELECT count(*) FROM public.tenants` returns 0 before seed, 1 after)
- [ ] Scenario 4 — Migrations auto-applied: `db-init` container log shows `alembic upgrade head` completing; `SELECT version_num FROM alembic_version` shows all expected versions
- [ ] Scenario 5 — Seed runs automatically: `SELECT id FROM public.tenants WHERE id='system'` and `SELECT email FROM public.tenant_users WHERE role='system_admin'` both return rows after a fresh `compose up`
- [ ] Scenario 6 — Idempotency: second `compose down` (without `-v`) + `compose up` cycle shows `db-init` exits 0 and row counts in `public.tenants` and `public.tenant_users` are unchanged
- [ ] Scenario 7 — Service ordering: `docker compose up` log shows `db-init` exits before any of the 7 app services log their first startup line
- [ ] Scenario 8 — Fail-fast: with a deliberately broken migration, app services do not appear in compose logs; `db-init` exit code is non-zero

### Structural Evidence

- [ ] Code review completed — `docker-compose.yml` diff matches all four design decisions (named volume, `db-init` service, `restart: "no"`, `service_completed_successfully` depends_on for all 7 services)
- [ ] ADR-001 compliance step confirmed (tenant schemas survive cycle)
- [ ] No new image or Dockerfile introduced — `db-init` reuses the root image with an overridden `command`
- [ ] No application source code changes (only `docker-compose.yml` is modified)

### Edge Case Evidence

- [ ] Risk 1 — Volume path: confirm `postgres-data:/var/lib/postgresql/data` (not `/var/lib/postgresql`) in compose file
- [ ] Risk 2 — Condition value: grep confirms all `db-init` `depends_on` entries use `service_completed_successfully`
- [ ] Risk 3 — Restart policy: `restart: "no"` present on `db-init`
- [ ] Risk 4 — All 7 services covered: grep for `db-init` in `depends_on` blocks returns exactly 7 matches
- [ ] Risk 5 — Top-level volumes block: both `minio-data:` and `postgres-data:` appear in the top-level `volumes:` section

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-postgres-persistence-and-db-init
**Proposal:** `openspec/changes/fix-postgres-persistence-and-db-init/proposal.md`
**Spec files reviewed:**
  - specs/local-dev-stack/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items. -->
