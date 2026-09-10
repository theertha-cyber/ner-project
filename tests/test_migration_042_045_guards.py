"""Guard tests for migrations 042-045.

Each runs the migration's real `upgrade()` / `downgrade()` (via `importlib` +
`MigrationContext`/`Operations`, the pattern used by `test_migration_037_*`) against a
minimal pre-migration schema, and asserts the columns / tables it declares appear on
upgrade and disappear on downgrade — for `tenant_template` and for one real tenant schema
(the `apply_to_all_tenant_schemas` fan-out).

The pre-state per migration mirrors what the *previous* migration would have left:
039 created `prelabel_batches` / `schema_proposals` / `documents` in every tenant schema,
014/041 created `imported_annotations` / `annotation_imports`.
"""

import importlib.util
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_VERSIONS = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")


def _load(filename: str):
    path = os.path.join(_VERSIONS, filename)
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(sync_engine, module, direction):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original = module.op
        module.op = op
        try:
            getattr(module, direction)()
        finally:
            module.op = original
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


TENANT_ID = "mig-042-045-tenant"
TENANT_SCHEMA = f"tenant_{TENANT_ID.replace('-', '_')}"


def _base_tables(conn, schema: str):
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.documents ("
            "  id VARCHAR PRIMARY KEY, tenant_id VARCHAR, filename VARCHAR, "
            "  purpose VARCHAR(20) NOT NULL DEFAULT 'query')"
        )
    )
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.prelabel_batches ("
            "  id VARCHAR PRIMARY KEY, status VARCHAR(16) NOT NULL DEFAULT 'queued')"
        )
    )
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.schema_proposals ("
            "  id VARCHAR PRIMARY KEY, status VARCHAR(16) NOT NULL DEFAULT 'queued', "
            "  seed_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb)"
        )
    )
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.imported_annotations ("
            "  id VARCHAR PRIMARY KEY, tokens TEXT[] NOT NULL, "
            "  tags TEXT[] NOT NULL, source_file VARCHAR NOT NULL, "
            "  row_index INTEGER NOT NULL DEFAULT 0)"
        )
    )
    conn.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.annotation_imports ("
            "  source_file VARCHAR PRIMARY KEY, row_count INTEGER NOT NULL DEFAULT 0, "
            "  type_map JSONB, training_eligible_at TIMESTAMPTZ, "
            "  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
    )


@pytest.fixture
def prepared(sync_engine, setup_database):
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": TENANT_ID},
        )
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TENANT_SCHEMA}"))
        # `apply_to_all_tenant_schemas` fans out over EVERY `tenant_%` schema in the DB
        # (stray ones left by other test files included), and it is not guarded for table
        # existence. Give every such schema the pre-migration tables so the fan-out runs.
        existing = [
            r[0]
            for r in conn.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\\_%'")
            ).fetchall()
        ]
        for schema in existing:
            _base_tables(conn, schema)
    yield sync_engine
    with sync_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TENANT_SCHEMA} CASCADE"))
        conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": TENANT_ID})


def _has_column(conn, schema, table, column) -> bool:
    return conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = :s "
            "AND table_name = :t AND column_name = :c"
        ),
        {"s": schema, "t": table, "c": column},
    ).fetchone() is not None


def _has_table(conn, schema, table) -> bool:
    return conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = :t"
        ),
        {"s": schema, "t": table},
    ).fetchone() is not None


class TestMigration042:
    def test_upgrade_adds_batch_kind_state_and_guidance(self, prepared):
        module = _load("042_automated_annotation_guided_workflow.py")
        _run(prepared, module, "upgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert _has_column(conn, schema, "prelabel_batches", "batch_kind")
                assert _has_column(conn, schema, "prelabel_batches", "state")
                assert _has_table(conn, schema, "prelabel_batch_guidance")
        _run(prepared, module, "downgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert not _has_column(conn, schema, "prelabel_batches", "batch_kind")
                assert not _has_table(conn, schema, "prelabel_batch_guidance")

    def test_upgrade_is_rerunnable(self, prepared):
        module = _load("042_automated_annotation_guided_workflow.py")
        _run(prepared, module, "upgrade")
        _run(prepared, module, "upgrade")
        with prepared.connect() as conn:
            assert _has_column(conn, TENANT_SCHEMA, "prelabel_batches", "batch_kind")


class TestMigration043:
    def test_upgrade_adds_qa_pair_document_id(self, prepared):
        module = _load("043_schema_proposal_qa_pair.py")
        _run(prepared, module, "upgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert _has_column(conn, schema, "schema_proposals", "qa_pair_document_id")
        _run(prepared, module, "downgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert not _has_column(conn, schema, "schema_proposals", "qa_pair_document_id")


@pytest.mark.usefixtures("setup_database")
class TestMigration044:
    def test_upgrade_adds_provenance_to_entity_definitions(self, sync_engine, setup_database):
        module = _load("044_entity_type_provenance.py")
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE public.entity_definitions "
                    "DROP COLUMN IF EXISTS provenance, DROP COLUMN IF EXISTS provenance_ref"
                )
            )
        _run(sync_engine, module, "upgrade")
        with sync_engine.connect() as conn:
            assert _has_column(conn, "public", "entity_definitions", "provenance")
            assert _has_column(conn, "public", "entity_definitions", "provenance_ref")
            default = conn.execute(
                text(
                    "SELECT column_default FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name='entity_definitions' AND column_name='provenance'"
                )
            ).scalar()
        assert "manual" in (default or "")
        _run(sync_engine, module, "downgrade")
        with sync_engine.connect() as conn:
            assert not _has_column(conn, "public", "entity_definitions", "provenance")
        # Restore for other tests (setup_database recreates from models, but be tidy).
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE public.entity_definitions "
                    "ADD COLUMN IF NOT EXISTS provenance VARCHAR(16) NOT NULL DEFAULT 'manual', "
                    "ADD COLUMN IF NOT EXISTS provenance_ref VARCHAR(255)"
                )
            )

    def test_preexisting_row_backfills_to_manual(self, sync_engine, setup_database):
        module = _load("044_entity_type_provenance.py")
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE public.entity_definitions "
                    "DROP COLUMN IF EXISTS provenance, DROP COLUMN IF EXISTS provenance_ref"
                )
            )
            eid = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO public.entity_definitions (id, tenant_id, name, version, is_active) "
                    "VALUES (:id, 'test-tenant', 'legacy', 1, true)"
                ),
                {"id": eid},
            )
        _run(sync_engine, module, "upgrade")
        with sync_engine.connect() as conn:
            prov = conn.execute(
                text("SELECT provenance FROM public.entity_definitions WHERE id = :id"),
                {"id": eid},
            ).scalar()
        assert prov == "manual"
        with sync_engine.begin() as conn:
            conn.execute(text("DELETE FROM public.entity_definitions WHERE id = :id"), {"id": eid})


class TestMigration045:
    def test_upgrade_adds_pending_mapping_and_backfills_header(self, prepared):
        module = _load("045_imported_annotation_pending_mapping.py")
        with prepared.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {TENANT_SCHEMA}.imported_annotations "
                    "(id, tokens, tags, source_file, row_index) "
                    "VALUES (:id, :tok, :tag, 'legacy.jsonl', 0)"
                ),
                {"id": str(uuid.uuid4()), "tok": ["a"], "tag": ["O"]},
            )
        _run(prepared, module, "upgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert _has_column(conn, schema, "imported_annotations", "pending_mapping")
            header = conn.execute(
                text(
                    f"SELECT training_eligible_at FROM {TENANT_SCHEMA}.annotation_imports "
                    "WHERE source_file = 'legacy.jsonl'"
                )
            ).fetchone()
        assert header is not None and header[0] is not None
        _run(prepared, module, "downgrade")
        with prepared.connect() as conn:
            for schema in ("tenant_template", TENANT_SCHEMA):
                assert not _has_column(conn, schema, "imported_annotations", "pending_mapping")
