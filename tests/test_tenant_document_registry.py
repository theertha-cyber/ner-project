"""Verification for `public.tenant_document_registry` (ADR-017).

Maps to `openspec/changes/tenant-postgresql-data-plane/verification.md` scenarios
#31-#37. This file starts with the schema and backfill scenarios (#31, #32); the write
path, reconciliation, and quota/fleet-count scenarios (#33-#37) land with task group 12
once `registry.record(...)` exists.

The table is created by alembic migration 043 in real deployments and mirrored for the
test database by `scripts/setup_test_db.py`, exactly like the other ADR-017 tables.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.shared.config import settings

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
async def registry_source_schema():
    """A throwaway tenant schema shaped like `documents` at head 042 (migration 038's
    provenance/retention columns included) — the columns the registry backfill actually
    projects. `tests/conftest.py`'s `tenant_schema` fixture predates those columns, so
    this test builds its own rather than widening a shared fixture other files depend on.
    """
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    tid = f"registry-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(
            text(
                f"""
                CREATE TABLE {schema}.documents (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    source_type VARCHAR(64) NOT NULL DEFAULT 'platform_upload',
                    status VARCHAR(20) DEFAULT 'uploaded',
                    file_size_bytes BIGINT,
                    checksum VARCHAR(64),
                    retention_mode VARCHAR(32) NOT NULL DEFAULT 'platform_blob',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid, "n": "Registry Fixture", "s": f"slug-{tid}"},
        )
    yield tid, schema
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(
            text("DELETE FROM public.tenant_document_registry WHERE tenant_id = :id"),
            {"id": tid},
        )
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    await engine.dispose()

# The exact finite column set the registry spec allows. No filename, storage
# reference, error message, or derived-content column may ever appear here.
SAFE_COLUMNS = {
    "document_id",
    "tenant_id",
    "source_type",
    "status",
    "file_size_bytes",
    "checksum",
    "retention_mode",
    "created_at",
    "updated_at",
}
FORBIDDEN_COLUMN_NAMES = {"filename", "storage_uri", "blob_path", "error_message"}


async def test_registry_schema_holds_no_content_columns(engine, setup_database):
    """Scenario: Registry schema holds no content columns."""
    async with engine.begin() as conn:
        columns = {
            row.column_name
            for row in (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'tenant_document_registry'"
                    )
                )
            ).fetchall()
        }
    assert columns == SAFE_COLUMNS
    assert columns.isdisjoint(FORBIDDEN_COLUMN_NAMES)


async def _backfill_registry_from_schema(conn, schema: str) -> None:
    """The same projection alembic migration 043 runs per platform tenant schema,
    scoped here to one schema so a test can exercise it without running alembic."""
    await conn.execute(
        text(
            f"""
            INSERT INTO public.tenant_document_registry
                (document_id, tenant_id, source_type, status, file_size_bytes,
                 checksum, retention_mode, created_at, updated_at)
            SELECT id, tenant_id, source_type, status,
                   file_size_bytes, checksum, retention_mode,
                   created_at, COALESCE(updated_at, created_at)
            FROM {schema}.documents
            ON CONFLICT (tenant_id, document_id) DO NOTHING
            """
        )
    )


async def test_existing_documents_are_backfilled(engine, setup_database, registry_source_schema):
    """Scenario: Existing documents are backfilled.

    Given a platform tenant with 5 documents before this change, the registry
    contains 5 rows for that tenant with matching id, status, size, and checksum.
    """
    tid, schema = registry_source_schema
    doc_ids = [f"doc-registry-{uuid.uuid4().hex[:8]}" for _ in range(5)]
    async with engine.begin() as conn:
        for i, doc_id in enumerate(doc_ids):
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.documents "
                    "(id, tenant_id, filename, status, checksum) "
                    "VALUES (:id, :tid, :fn, 'processed', :cs)"
                ),
                {"id": doc_id, "tid": tid, "fn": f"file-{i}.pdf", "cs": f"checksum-{i}"},
            )
        await _backfill_registry_from_schema(conn, schema)

        rows = (
            await conn.execute(
                text(
                    "SELECT document_id, status, checksum FROM public.tenant_document_registry "
                    "WHERE document_id = ANY(:ids)"
                ),
                {"ids": doc_ids},
            )
        ).fetchall()

    assert len(rows) == 5
    by_id = {r.document_id: r for r in rows}
    for i, doc_id in enumerate(doc_ids):
        assert by_id[doc_id].status == "processed"
        assert by_id[doc_id].checksum == f"checksum-{i}"


async def test_backfill_is_idempotent(engine, setup_database, registry_source_schema):
    tid, schema = registry_source_schema
    doc_id = f"doc-registry-{uuid.uuid4().hex[:8]}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) "
                "VALUES (:id, :tid, 'f.pdf', 'processed')"
            ),
            {"id": doc_id, "tid": tid},
        )
        await _backfill_registry_from_schema(conn, schema)
        await _backfill_registry_from_schema(conn, schema)

        count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM public.tenant_document_registry "
                    "WHERE document_id = :id"
                ),
                {"id": doc_id},
            )
        ).scalar_one()
    assert count == 1
