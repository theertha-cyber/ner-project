"""Verification for migration 038 — verification.md rows 82-87.

The migration is run against a real database with pre-existing rows and several tenant
schemas, because the failure this row exists to catch is a migration that reaches
`tenant_template` and stops — the mistake migrations 030 and 034 had to guard against.
"""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings

# The pre-change shape: what `documents` looked like before migration 038.
PRE_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255),
    file_size BIGINT,
    checksum VARCHAR(64),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    blob_path VARCHAR(500),
    purpose VARCHAR(20) NOT NULL DEFAULT 'query',
    uploaded_by VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

ADDED_COLUMNS = {
    "origin",
    "source_type",
    "source_id",
    "external_id",
    "source_version",
    "source_created_at",
    "source_modified_at",
    "origin_metadata",
    "retention_mode",
    "ingested_by_kind",
}


def _migration():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migration_038",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic",
            "versions",
            "038_document_provenance_and_retention.py",
        ),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
async def migrated_database():
    """A template schema, two tenant schemas with pre-existing rows, then the migration."""
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    suffix = uuid.uuid4().hex[:12]
    tenant_schemas = [f"tenant_{suffix}_a", f"tenant_{suffix}_b"]
    schemas = ["tenant_template"] + tenant_schemas
    existing_rows = {}

    async with engine.connect() as conn:
        # `tenant_template` is shared with the rest of the suite. If it already carries a
        # `documents` table, leave it alone: the migration is additive and `IF NOT EXISTS`,
        # so running it over the real template is harmless — and dropping the table at
        # teardown would break every other test file in the session.
        template_existed = bool(
            (
                await conn.execute(
                    text("SELECT to_regclass('tenant_template.documents') IS NOT NULL")
                )
            ).scalar()
        )
        for schema in schemas:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            if schema == "tenant_template" and template_existed:
                continue
            await conn.execute(text(PRE_MIGRATION_DDL.format(schema=schema)))
        for schema in tenant_schemas:
            document_id = str(uuid.uuid4())
            existing_rows[schema] = document_id
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) "
                    f"VALUES (:id, :tid, 'pre-existing.pdf', 'processed')"
                ),
                {"id": document_id, "tid": suffix},
            )

    # Run the migration's own statements, so what is verified is the shipped SQL.
    module = _migration()
    statements = []

    class _CollectingOp:
        @staticmethod
        def execute(statement):
            statements.append(statement)

    module.op = _CollectingOp
    module.upgrade()

    async with engine.connect() as conn:
        for statement in statements:
            await conn.execute(text(statement))

    yield {
        "engine": engine,
        "schemas": schemas,
        "tenant_schemas": tenant_schemas,
        "existing_rows": existing_rows,
        "module": module,
    }

    async with engine.connect() as conn:
        for schema in tenant_schemas:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        if not template_existed:
            await conn.execute(
                text("DROP TABLE IF EXISTS tenant_template.documents CASCADE")
            )
    await engine.dispose()


async def _columns(engine, schema) -> set[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = 'documents'"
            ),
            {"s": schema},
        )
        return {r[0] for r in rows}


# --- Row 82: existing rows remain readable, with the declared defaults -----------------


@pytest.mark.asyncio
async def test_row_82_existing_rows_are_readable_with_the_declared_defaults(
    migrated_database,
):
    engine = migrated_database["engine"]
    for schema, document_id in migrated_database["existing_rows"].items():
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT source_type, source_id, retention_mode, origin, "
                        f"ingested_by_kind FROM {schema}.documents WHERE id = :id"
                    ),
                    {"id": document_id},
                )
            ).fetchone()
        assert row is not None, f"a pre-existing row in {schema} became unreadable"
        assert row.source_type == "platform_upload"
        assert row.source_id == "platform-upload"
        assert row.retention_mode == "platform_blob"
        assert row.origin == "push"
        assert row.ingested_by_kind == "human"


# --- Row 83: the migration reaches every tenant schema ---------------------------------


@pytest.mark.asyncio
async def test_row_83_every_tenant_schema_and_the_template_carry_the_columns(
    migrated_database,
):
    engine = migrated_database["engine"]
    for schema in migrated_database["schemas"]:
        columns = await _columns(engine, schema)
        missing = ADDED_COLUMNS - columns
        assert missing == set(), f"{schema} is missing {sorted(missing)}"


# --- Row 84: a newly provisioned tenant inherits them ----------------------------------


@pytest.mark.asyncio
async def test_row_84_a_new_tenant_provisioned_from_the_template_inherits_them(
    migrated_database,
):
    """Provisioning clones `tenant_template`, so inheriting is a property of the template."""
    engine = migrated_database["engine"]
    new_schema = f"tenant_{uuid.uuid4().hex[:12]}_new"

    template_columns = await _columns(engine, "tenant_template")
    async with engine.connect() as conn:
        await conn.execute(text(f"CREATE SCHEMA {new_schema}"))
        await conn.execute(
            text(
                f"CREATE TABLE {new_schema}.documents "
                f"(LIKE tenant_template.documents INCLUDING ALL)"
            )
        )
    try:
        assert ADDED_COLUMNS <= await _columns(engine, new_schema)
        assert ADDED_COLUMNS <= template_columns
    finally:
        async with engine.connect() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {new_schema} CASCADE"))


# --- Row 85: retention mode is constrained ---------------------------------------------


@pytest.mark.asyncio
async def test_row_85_retention_mode_is_constrained_to_the_declared_values(
    migrated_database,
):
    engine = migrated_database["engine"]
    schema = migrated_database["tenant_schemas"][0]

    for mode in ("platform_blob", "ephemeral", "source_only"):
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents (id, tenant_id, filename, retention_mode) "
                    f"VALUES (:id, 't', 'ok.pdf', :mode)"
                ),
                {"id": str(uuid.uuid4()), "mode": mode},
            )

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents (id, tenant_id, filename, retention_mode) "
                    f"VALUES (:id, 't', 'bad.pdf', 'keep_forever')"
                ),
                {"id": str(uuid.uuid4())},
            )


# --- Row 86: duplicate external identities are permitted -------------------------------


@pytest.mark.asyncio
async def test_row_86_duplicate_external_identities_are_permitted(migrated_database):
    """No unique constraint: `documents` is soft-deleted, and content-addressed reuse
    makes the relationship many-to-one. The ledger that owns uniqueness arrives later."""
    engine = migrated_database["engine"]
    schema = migrated_database["tenant_schemas"][0]

    async with engine.connect() as conn:
        for _ in range(2):
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents "
                    f"(id, tenant_id, filename, source_id, external_id) "
                    f"VALUES (:id, 't', 'dup.pdf', 'keka-prod', 'employee-991')"
                ),
                {"id": str(uuid.uuid4())},
            )
        count = (
            await conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.documents "
                    f"WHERE external_id = 'employee-991'"
                )
            )
        ).scalar()
    assert count == 2


# --- Row 87: no second storage-reference column ----------------------------------------


@pytest.mark.asyncio
async def test_row_87_no_added_column_duplicates_blob_path(migrated_database):
    module = migrated_database["module"]
    added = {name for name, _, _ in module.COLUMNS}
    assert added == ADDED_COLUMNS

    # `storage_reference` is the application term; introducing it as a column here would
    # create a fourth name for one value, which is what the deferred reconciliation change
    # exists to close.
    for forbidden in ("storage_reference", "blob_path", "storage_uri", "object_key"):
        assert forbidden not in added, f"the migration adds {forbidden}"

    engine = migrated_database["engine"]
    columns = await _columns(engine, migrated_database["tenant_schemas"][0])
    assert "blob_path" in columns
    assert "storage_reference" not in columns
