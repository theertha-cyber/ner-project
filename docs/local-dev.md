# Local Development: Clean Database Rebuild

Use this procedure when the local `ner_dev` database has drifted from what the
Alembic migration chain declares — for example, `docker compose up`'s
`db-init` service fails with a schema-verification error (see
`src/gateway/verify_schema.py`), or you're seeing errors like
`column "..." does not exist` or `relation "..." does not exist` for tables
the application expects.

## This procedure is destructive

**Running the steps below permanently deletes every tenant, user, document,
annotation, model version, and training run in your local `postgres-data`
Docker volume.** There is no undo. If anything in the current database is
worth keeping, take a backup first:

```bash
docker exec ner-project-postgres-test-1 pg_dump -U ner ner_dev > ner_dev_backup.sql
```

The local database is treated as disposable dev data — this is the intended
and supported remedy for a drifted database, not a last resort.

## Procedure

Run these in order. Do not skip the build step — the running containers may
predate migrations or code changes on disk, in which case reapplying
migrations against an old image reproduces the same drift you're trying to
fix.

```bash
docker compose down -v      # Removes the postgres-data volume and all its contents
docker compose build        # Rebuilds images from the current working tree
docker compose up           # Applies the full migration chain to an empty database, seeds, and verifies
```

`db-init` runs `alembic upgrade head`, `python -m src.gateway.seed`, and
`python -m src.gateway.verify_schema`, in that order, before any application
service starts. If verification finds drift, `db-init` exits non-zero and
none of the dependent services (`gateway`, `document_service`,
`extraction_service`, `annotation_service`, `training_service`,
`celery_worker`, `celery_worker_extraction`) will start — check the `db-init`
logs for the specific schema, table, or column named as missing.

## Confirming the rebuild worked

```bash
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "SELECT version_num FROM alembic_version;"
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "\d tenant_template.documents"
docker exec ner-project-postgres-test-1 psql -U ner -d ner_dev -c "\dt public.*"
```

- `alembic_version` should equal the highest revision number under
  `alembic/versions/`.
- `tenant_template.documents` should exist and include `purpose`,
  `content_type`, `file_size`, and `blob_path`.
- `public` should **not** contain `model_versions` — that table is a
  test-fixture artifact (`scripts/setup_test_db.py`) and should never appear
  in `ner_dev`.

Then exercise the paths that regress most visibly under drift: create an
entity type, create a tenant and upload a document to it, and load the
`system_admin` dashboard.
