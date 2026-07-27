## Why

The local `ner_dev` database drifted away from what the Alembic migration chain declares, and three user-facing features broke as a result: entity-type creation returns 500 (`column "validation_rule" does not exist`), document upload and listing return 500 for newly created tenants (`relation "tenant_<id>.documents" does not exist`), and the `system_admin` dashboard logs a stack trace per non-existent tenant schema (`tenant_system.documents`). The investigation traced this to `scripts/setup_test_db.py` having been run against `ner_dev` with an abbreviated `public` schema, `tenant_template.documents` having been dropped out of band, and the running containers being built from an image that predates migration `021`.

The database itself is disposable dev data, so the fix is to rebuild it from a clean state rather than repair it — but the code paths that let the drift happen silently, and that turn drift into 500s, need to be closed so this does not recur.

## What Changes

- Rebuild the local stack from a clean state: rebuild Docker images so containers carry the current migration chain and `src/shared/retrieval`, recreate the Postgres volume, run `alembic upgrade head` from empty, and seed. **BREAKING** for local dev only — every tenant, user, document, annotation, model version, and training run in the current `postgres-data` volume is destroyed. No production or shared environment is affected.
- Add a schema-verification step that asserts the rebuilt database matches what the migration chain declares, so a drifted database is detected at startup rather than at first 500.
- Fix `_all_tenant_schemas` in the dashboard so it enumerates tenant schemas that actually exist instead of deriving a schema name from every `public.tenants` row. This removes the `tenant_system` failure and the four test-fixture tenants from the system-admin aggregate, and makes the document count correct rather than silently short.
- Make the per-tenant-schema DDL loops in migrations robust: guard statements that assume a tenant table exists (migration `022`'s `UPDATE ... FROM %I.annotation_tasks` has no such guard and aborts the whole `DO` block on any schema lacking `annotation_tasks`).
- Add a reconciliation migration that brings every existing tenant schema up to the current `tenant_template` shape, covering columns that earlier migrations added to the template only (`003`'s `content_type`, `file_size`, `blob_path`, `updated_at`).
- Guard `scripts/setup_test_db.py` so it refuses to run against a database whose name is not a recognised test database, instead of silently honouring whatever `NER_DATABASE_URL` points at.
- Commit `src/shared/retrieval/`, which is currently untracked while the `chat_api/services/chunking_service.py` deletion that depends on it is staged.

## Capabilities

### New Capabilities

- `dev-database-reset`: A documented, repeatable procedure for tearing down and rebuilding the local development database and images from a clean state, plus the post-rebuild schema verification that proves the result matches the migration chain.
- `test-fixture-db-isolation`: Guarantees that test-fixture setup scripts cannot create or mutate schema objects in a non-test database.

### Modified Capabilities

- `dashboard-summary-endpoint`: The system-admin aggregate SHALL enumerate tenant schemas from schemas that exist in the database, not from `public.tenants` rows, and SHALL NOT count a tenant whose schema is absent as a silent zero.
- `tenant-schema-migrations`: The existing propagation requirement gains robustness and reconciliation requirements — per-tenant DDL SHALL tolerate tenant schemas missing a given table, and a reconciliation migration SHALL bring already-provisioned schemas up to the current template shape.

## Impact

- **Code**: `src/gateway/api/v1/dashboard.py` (`_all_tenant_schemas`, `_system_admin_data`), `scripts/setup_test_db.py`, `alembic/versions/022_document_purpose_scoping.py`, one new reconciliation migration, `src/shared/retrieval/` (newly tracked).
- **Data**: The local `postgres-data` Docker volume is deleted and recreated. Nothing else.
- **Operations**: `docker compose build` becomes a required step; the existing `db-init` service gains a verification stage.
- **Downstream**: Migration `022` finally applies, so the `purpose` column exists and the staged document-purpose-scoping work (upload form field, `src/shared/retrieval` chunking, purpose-filtered listing) becomes exercisable end to end.

## Open Questions

- The four fixture tenants (`test-tenant`, `tenant-b`, `no-model`, `no-model-tenant`) currently live in `ner_dev`. After the rebuild they will be gone. Assumption: they are only needed in `ner_test` and no dev workflow depends on them being present in `ner_dev`.
- Whether schema verification should hard-fail `db-init` (blocking stack startup on drift) or log loudly and continue. Proposed: hard-fail, on the grounds that the failure mode this change exists to prevent was precisely a drifted database starting successfully.
- Which database names count as "test" for the `setup_test_db.py` guard. Proposed: names ending in `_test`, overridable by an explicit opt-in environment variable.
- The mechanism that dropped `tenant_template.documents` and deleted the Acme Corp tenant's users was never identified — no code path in the repo does either. This change prevents drift from being silent but does not explain that event.
