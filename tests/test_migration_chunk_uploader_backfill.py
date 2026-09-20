"""Verification for migration 056 — verification.md rows 30-31.

The migration is run against a real database holding pre-existing chunks across several
tenant schemas, because the two failures worth catching are a migration that reaches
`tenant_template` and stops (the mistake migrations 030 and 034 had to guard against)
and a backfill that leaves rows with no ingesting actor. A chunk with no actor has
undefined visibility: depending on how the predicate treats NULL it is either hidden
from everyone or shown to everyone, and both are wrong.

Mirrors `tests/test_document_provenance_migration.py`, including running the migration's
own statements so what is verified is the shipped SQL rather than a restatement of it.
"""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:55432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings

# The pre-change shape: `document_chunks` as migration 054 left it.
PRE_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    page_number INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    purpose VARCHAR(20),
    conversation_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
)
"""

DOCUMENTS_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    filename VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    purpose VARCHAR(20) NOT NULL DEFAULT 'query',
    uploaded_by VARCHAR,
    ingested_by_kind VARCHAR(32) NOT NULL DEFAULT 'human',
    created_at TIMESTAMPTZ DEFAULT NOW()
)
"""

ADDED_COLUMNS = {"uploaded_by", "ingested_by_kind"}


def _migration():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migration_056",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic",
            "versions",
            "056_document_chunks_uploader_visibility.py",
        ),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _statements(module):
    collected = []

    class _CollectingOp:
        @staticmethod
        def execute(statement):
            collected.append(statement)

    module.op = _CollectingOp
    module.upgrade()
    return collected


@pytest.fixture
async def migrated_database():
    """Two tenant schemas, each with documents and chunks predating the migration."""
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    suffix = uuid.uuid4().hex[:12]
    tenant_schemas = [f"tenant_{suffix}_a", f"tenant_{suffix}_b"]
    seeded = {}

    async with engine.connect() as conn:
        template_existed = bool(
            (
                await conn.execute(
                    text("SELECT to_regclass('tenant_template.document_chunks') IS NOT NULL")
                )
            ).scalar()
        )
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS tenant_template"))
        if not template_existed:
            await conn.execute(text(PRE_MIGRATION_DDL.format(schema="tenant_template")))

        for schema in tenant_schemas:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(DOCUMENTS_DDL.format(schema=schema)))
            await conn.execute(text(PRE_MIGRATION_DDL.format(schema=schema)))

            human_doc = str(uuid.uuid4())
            system_doc = str(uuid.uuid4())
            orphan_chunk = str(uuid.uuid4())
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents "
                    "(id, tenant_id, filename, status, uploaded_by, ingested_by_kind) VALUES "
                    "(:h, :tid, 'resume.pdf', 'processed', 'recruiter-1', 'human'), "
                    "(:s, :tid, 'synced.pdf', 'processed', NULL, 'source_system')"
                ),
                {"h": human_doc, "s": system_doc, "tid": suffix},
            )
            for i, doc in enumerate([human_doc, human_doc, system_doc]):
                await conn.execute(
                    text(
                        f"INSERT INTO {schema}.document_chunks "
                        "(id, document_id, chunk_index, chunk_text, purpose) "
                        "VALUES (:id, :doc, :i, 'body', 'query')"
                    ),
                    {"id": str(uuid.uuid4()), "doc": doc, "i": i},
                )
            # A chunk whose document is gone. Real schemas have these: the FK is
            # ON DELETE CASCADE, but hard-delete paths and older data both leave strays.
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.document_chunks "
                    "(id, document_id, chunk_index, chunk_text, purpose) "
                    "VALUES (:id, :doc, 99, 'orphan body', 'query')"
                ),
                {"id": orphan_chunk, "doc": str(uuid.uuid4())},
            )
            seeded[schema] = {
                "human_doc": human_doc,
                "system_doc": system_doc,
                "orphan_chunk": orphan_chunk,
            }

    module = _migration()
    async with engine.connect() as conn:
        for statement in _statements(module):
            await conn.execute(text(statement))

    yield {
        "engine": engine,
        "tenant_schemas": tenant_schemas,
        "seeded": seeded,
        "module": module,
    }

    async with engine.connect() as conn:
        for schema in tenant_schemas:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    await engine.dispose()


# --- Row 30: existing chunks are backfilled ----------------------------------------


@pytest.mark.integration
@pytest.mark.verification
async def test_columns_exist_in_every_tenant_schema(migrated_database):
    """The failure this catches is a migration that updates `tenant_template` and stops."""
    engine = migrated_database["engine"]
    async with engine.connect() as conn:
        for schema in migrated_database["tenant_schemas"] + ["tenant_template"]:
            present = {
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = :s AND table_name = 'document_chunks'"
                        ),
                        {"s": schema},
                    )
                ).fetchall()
            }
            assert ADDED_COLUMNS <= present, f"{schema} is missing {ADDED_COLUMNS - present}"


@pytest.mark.integration
@pytest.mark.verification
async def test_no_chunk_is_left_without_an_ingesting_actor(migrated_database):
    """Row 30's second clause, and the one that matters most: a NULL actor is a chunk
    whose visibility is decided by accident."""
    engine = migrated_database["engine"]
    async with engine.connect() as conn:
        for schema in migrated_database["tenant_schemas"]:
            unset = (
                await conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM {schema}.document_chunks "
                        "WHERE ingested_by_kind IS NULL"
                    )
                )
            ).scalar()
            assert unset == 0, f"{schema} left {unset} chunks with no ingesting actor"


@pytest.mark.integration
@pytest.mark.verification
async def test_orphan_chunk_is_marked_source_system_not_human(migrated_database):
    """A chunk with no document has no honest uploader. Marking it human with a NULL
    uploader would hide it from every user including whoever owned it."""
    engine = migrated_database["engine"]
    async with engine.connect() as conn:
        for schema, seeded in migrated_database["seeded"].items():
            row = (
                await conn.execute(
                    text(
                        f"SELECT uploaded_by, ingested_by_kind FROM {schema}.document_chunks "
                        "WHERE id = :id"
                    ),
                    {"id": seeded["orphan_chunk"]},
                )
            ).fetchone()
            assert row.ingested_by_kind == "source_system"
            assert row.uploaded_by is None


# --- Row 31: the denormalized value agrees with the document -----------------------


@pytest.mark.integration
@pytest.mark.verification
async def test_every_chunk_matches_its_own_document(migrated_database):
    engine = migrated_database["engine"]
    async with engine.connect() as conn:
        for schema in migrated_database["tenant_schemas"]:
            mismatched = (
                await conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM {schema}.document_chunks c
                        JOIN {schema}.documents d ON d.id = c.document_id
                        WHERE c.uploaded_by IS DISTINCT FROM d.uploaded_by
                           OR c.ingested_by_kind IS DISTINCT FROM d.ingested_by_kind
                    """)
                )
            ).scalar()
            assert mismatched == 0, f"{schema} has {mismatched} chunks disagreeing with their document"


@pytest.mark.integration
@pytest.mark.verification
async def test_human_and_source_system_documents_backfill_differently(migrated_database):
    """The backfill is only useful if it distinguishes the two cases — a blanket value
    would satisfy 'no NULLs' while destroying the rule."""
    engine = migrated_database["engine"]
    async with engine.connect() as conn:
        for schema, seeded in migrated_database["seeded"].items():
            human_rows = (
                await conn.execute(
                    text(
                        f"SELECT uploaded_by, ingested_by_kind FROM {schema}.document_chunks "
                        "WHERE document_id = :d"
                    ),
                    {"d": seeded["human_doc"]},
                )
            ).fetchall()
            assert human_rows
            assert all(r.uploaded_by == "recruiter-1" for r in human_rows)
            assert all(r.ingested_by_kind == "human" for r in human_rows)

            system_rows = (
                await conn.execute(
                    text(
                        f"SELECT uploaded_by, ingested_by_kind FROM {schema}.document_chunks "
                        "WHERE document_id = :d"
                    ),
                    {"d": seeded["system_doc"]},
                )
            ).fetchall()
            assert system_rows
            assert all(r.uploaded_by is None for r in system_rows)
            assert all(r.ingested_by_kind == "source_system" for r in system_rows)


@pytest.mark.integration
@pytest.mark.verification
async def test_migration_is_rerunnable(migrated_database):
    """Re-running must not fail and must not rewrite what it already set. The fixture
    has run it once; running it again is the assertion."""
    engine = migrated_database["engine"]
    module = migrated_database["module"]
    schema = migrated_database["tenant_schemas"][0]
    seeded = migrated_database["seeded"][schema]

    async with engine.connect() as conn:
        before = (
            await conn.execute(
                text(
                    f"SELECT id, uploaded_by, ingested_by_kind FROM {schema}.document_chunks "
                    "ORDER BY id"
                )
            )
        ).fetchall()

        for statement in _statements(module):
            await conn.execute(text(statement))

        after = (
            await conn.execute(
                text(
                    f"SELECT id, uploaded_by, ingested_by_kind FROM {schema}.document_chunks "
                    "ORDER BY id"
                )
            )
        ).fetchall()

    assert [tuple(r) for r in before] == [tuple(r) for r in after]
    assert any(r.id == seeded["orphan_chunk"] for r in after)
