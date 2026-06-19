## 1. Postgres Named Volume

- [x] 1.1 In `docker-compose.yml`, add `volumes: - postgres-data:/var/lib/postgresql/data` under the `postgres-test` service
- [x] 1.2 Add `postgres-data:` to the top-level `volumes:` block alongside the existing `minio-data:` entry
- [x] 1.3 Verify: `docker compose config` parses without error and the `postgres-data` volume appears in the output

## 2. db-init One-Shot Service

- [x] 2.1 Add a `db-init` service to `docker-compose.yml` with the following properties:
  - `build: context: . / dockerfile: Dockerfile` (reuse root image)
  - `command: sh -c "alembic upgrade head && python -m src.gateway.seed"`
  - `restart: "no"`
  - `env_file: .env`
  - `environment: NER_DATABASE_URL: "postgresql+asyncpg://ner:ner@postgres-test:5432/ner_dev"`
  - `depends_on: postgres-test: condition: service_healthy`
- [x] 2.2 Confirm `db-init` has `restart: "no"` (not `always` or `on-failure`)

## 3. Service Dependency Wiring

- [x] 3.1 Add `db-init: condition: service_completed_successfully` under `depends_on` in the `gateway` service
- [x] 3.2 Add the same `db-init` dependency to `document_service`
- [x] 3.3 Add the same `db-init` dependency to `extraction_service`
- [x] 3.4 Add the same `db-init` dependency to `annotation_service`
- [x] 3.5 Add the same `db-init` dependency to `training_service`
- [x] 3.6 Add the same `db-init` dependency to `celery_worker`
- [x] 3.7 Add the same `db-init` dependency to `celery_worker_extraction`

## 4. Smoke Test — Fresh Stack

- [ ] 4.1 Run `docker compose down -v` to remove any existing state
- [x] 4.2 Run `docker compose up --build` and confirm `db-init` logs show `alembic upgrade head` completing and "Seed complete" before any app service logs appear (Scenario 4 & 5)
- [ ] 4.3 Query `SELECT version_num FROM alembic_version` — confirm all expected migration versions are present
- [x] 4.4 Query `SELECT id FROM public.tenants WHERE id='system'` — confirm 1 row returned
- [x] 4.5 Query `SELECT email FROM public.tenant_users WHERE role='system_admin'` — confirm `admin@nerplatform.io` returned

## 5. Smoke Test — Persistence Cycle

- [ ] 5.1 With the stack running and seeded, create a test tenant row (or note current row count in `public.tenants`)
- [ ] 5.2 Run `docker compose down` (without `-v`)
- [ ] 5.3 Run `docker compose up` and wait for all services to start
- [ ] 5.4 Query `public.tenants` — confirm the test row (and all prior data) still exists; confirm row count is unchanged and no manual steps were taken (Scenario 1)
- [ ] 5.5 Query `public.tenants` and `public.tenant_users` — confirm `db-init` did not create duplicates (Scenario 6)

## 6. Smoke Test — Reset Behaviour

- [ ] 6.1 Run `docker compose down -v` — confirm the `postgres-data` volume is removed (`docker volume ls` shows no `ner-project_postgres-data` or equivalent)
- [ ] 6.2 Run `docker compose up` — confirm the database starts empty (0 tenant rows before seed runs) and `db-init` repopulates it (Scenario 3)

## 7. Smoke Test — Fail-Fast Behaviour

- [ ] 7.1 Temporarily break a migration (e.g., rename one migration file so it cannot be found)
- [ ] 7.2 Run `docker compose up` — confirm `db-init` exits non-zero and none of the 7 app services appear in compose output (Scenario 8)
- [ ] 7.3 Restore the migration file

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (rows 1–8)
- [ ] 8.2 Collect functional evidence (log excerpt or terminal output) for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register:
  - Risk 1: volume path is `postgres-data:/var/lib/postgresql/data`
  - Risk 2: all 7 `depends_on` entries use `service_completed_successfully`
  - Risk 3: `db-init` has `restart: "no"`
  - Risk 4: all 7 app services have the `db-init` dependency
  - Risk 5: top-level `volumes:` block contains both `minio-data:` and `postgres-data:`
- [ ] 8.4 Confirm ADR-001 compliance: after a compose down/up cycle (without `-v`), tenant schemas survive — `SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'` returns existing schemas
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 8.6 Run `openspec validate fix-postgres-persistence-and-db-init --type change --strict` and confirm it exits clean before archive
