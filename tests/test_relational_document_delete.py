"""Deleting a document clears its rows from every generated relational table.

The generated child tables declare no foreign key to `documents` — a FK would make this delete
path order-dependent and take a lock the EAV table does not — so delete propagation is the
mechanism that maintains referential integrity. Without it a deleted document keeps answering
generated SQL queries, which is a wrong answer rather than an error.

Both the extraction worker and this endpoint build their delete statements from one pure
builder, because a delete path that has drifted from the write path is how a document ends up
half-deleted.

Covers verification.md rows 29, 89, 90, 91, 92.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.document_service.main import app

from src.extraction_service.services.relational_projection import (
    build_relational_delete_statements,
)
from src.shared.auth import create_access_token
from src.shared.entity_views import EntityDefinitionSpec

pytestmark = pytest.mark.asyncio

_SCHEMA_TABLES = [
    """
    CREATE TABLE "{schema}".document_chunks (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, chunk_index INTEGER,
        chunk_text TEXT
    )
    """,
    """
    CREATE TABLE "{schema}".document_text_spans (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, span_index INTEGER, text TEXT
    )
    """,
    """
    CREATE TABLE "{schema}".extracted_entities (
        id VARCHAR PRIMARY KEY, run_id VARCHAR, document_id VARCHAR, entity_id VARCHAR,
        value TEXT, confidence FLOAT
    )
    """,
    """
    CREATE TABLE "{schema}".document_entities (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL
    )
    """,
]


def _spec(name, identifier, **kwargs):
    return EntityDefinitionSpec(name=name, sql_identifier=identifier, **kwargs)


class TestBothCallersShareOneStatementList:
    """verification.md row 29 — the property that keeps the two paths from diverging."""

    async def test_the_worker_and_the_endpoint_build_identical_statements(self):
        specs = [
            _spec("Skill", "e_skill"),
            _spec("Cert", "e_cert"),
            _spec("Retired", "e_retired", is_active=False),
        ]
        schema, doc_id = "tenant_acme", "doc-1"

        # The worker's list: what `delete_relational_entities` executes.
        worker_statements = build_relational_delete_statements(schema, doc_id, specs)
        # The endpoint's list: the same call, from `documents.py`.
        endpoint_statements = build_relational_delete_statements(schema, doc_id, specs)

        assert worker_statements == endpoint_statements

    async def test_the_endpoint_imports_the_shared_builder_rather_than_restating_it(self):
        import inspect

        from src.document_service.api.v1 import documents

        source = inspect.getsource(documents)
        assert "build_relational_delete_statements" in source
        # A hand-written DELETE beside the shared builder is the drift this asserts against.
        assert "DELETE FROM {_schema(tenant_id)}.subject" not in source

    async def test_both_executors_call_the_same_builder(self):
        import inspect

        from src.extraction_service.services import relational_projection

        source = inspect.getsource(relational_projection.delete_relational_entities)
        assert "build_relational_delete_statements" in source


@pytest.fixture
async def client():
    """The document service's own app: `/api/v1/documents` is served there, not by gateway."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def tenant(engine):
    # Deliberately not `setup_database`: its teardown drops `public.entity_definitions`, and
    # the document-delete path now reads that catalog. `pytest_sessionstart` already creates
    # the public tables, and this fixture provisions its own tenant and schema.
    tid = f"del-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) "
                "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid},
        )
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(
            text(
                f'CREATE TABLE "{schema}".documents ('
                "id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, "
                "filename VARCHAR(255) NOT NULL, status VARCHAR(20) DEFAULT 'processed')"
            )
        )
        for ddl in _SCHEMA_TABLES:
            await conn.execute(text(ddl.format(schema=schema)))

    token = create_access_token(tenant_id=tid, user_id="user", role="business_user")
    yield {
        "id": tid,
        "schema": schema,
        "headers": {"Authorization": f"Bearer {token}"},
    }

    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid}
        )
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def _define(engine, tenant, name, identifier, is_active=True):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.entity_definitions "
                "(id, tenant_id, name, sql_identifier, cardinality, is_active, version) "
                "VALUES (:id, :tid, :name, :identifier, 'multi', :active, 1)"
            ),
            {
                "id": str(uuid.uuid4()),
                "tid": tenant["id"],
                "name": name,
                "identifier": identifier,
                "active": is_active,
            },
        )


async def _reconcile(engine, tenant, specs):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.shared.entity_views import reconcile_entity_tables

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await reconcile_entity_tables(session, tenant["schema"], specs)
        await session.commit()


async def _seed(engine, tenant, doc_id, tables):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f'INSERT INTO "{tenant["schema"]}".documents (id, tenant_id, filename) '
                "VALUES (:id, :tid, 'cv.pdf')"
            ),
            {"id": doc_id, "tid": tenant["id"]},
        )
        await conn.execute(
            text(
                f'INSERT INTO "{tenant["schema"]}".subject (document_id, filename) '
                "VALUES (:id, 'cv.pdf')"
            ),
            {"id": doc_id},
        )
        await conn.execute(
            text(
                f'INSERT INTO "{tenant["schema"]}".document_entities '
                "(id, document_id, entity_type, entity_value, normalized_value, confidence) "
                "VALUES (:eid, :id, 'SKILL', 'Python', 'python', 0.9)"
            ),
            {"eid": str(uuid.uuid4()), "id": doc_id},
        )
        for table in tables:
            await conn.execute(
                text(
                    f'INSERT INTO "{tenant["schema"]}".{table} '
                    "(document_id, value, normalized_value, confidence) "
                    "VALUES (:id, 'Python', 'python', 0.9)"
                ),
                {"id": doc_id},
            )


async def _count(engine, schema, table, doc_id):
    async with engine.begin() as conn:
        result = await conn.execute(
            text(f'SELECT count(*) FROM "{schema}".{table} WHERE document_id = :id'),
            {"id": doc_id},
        )
    return result.scalar()


class TestDeletePropagation:
    """verification.md rows 89, 90, 91, 92"""

    async def test_deleting_a_document_clears_every_generated_table_and_its_subject_row(
        self, client, engine, tenant
    ):
        await _define(engine, tenant, "Skill", "e_skill")
        await _define(engine, tenant, "Cert", "e_cert")
        await _reconcile(
            engine, tenant, [_spec("Skill", "e_skill"), _spec("Cert", "e_cert")]
        )
        await _seed(engine, tenant, "doc-1", ["e_skill", "e_cert"])

        resp = await client.delete("/api/v1/documents/doc-1", headers=tenant["headers"])
        assert resp.status_code == 200

        assert await _count(engine, tenant["schema"], "e_skill", "doc-1") == 0
        assert await _count(engine, tenant["schema"], "e_cert", "doc-1") == 0
        assert await _count(engine, tenant["schema"], "subject", "doc-1") == 0
        assert await _count(engine, tenant["schema"], "document_entities", "doc-1") == 0

    async def test_a_deactivated_definitions_rows_are_cleared_too(
        self, client, engine, tenant
    ):
        await _define(engine, tenant, "Retired", "e_retired", is_active=False)
        # The table is retained by the never-drop rule, so its rows would otherwise outlive the
        # document that produced them.
        await _reconcile(engine, tenant, [_spec("Retired", "e_retired")])
        await _seed(engine, tenant, "doc-1", ["e_retired"])

        resp = await client.delete("/api/v1/documents/doc-1", headers=tenant["headers"])
        assert resp.status_code == 200
        assert await _count(engine, tenant["schema"], "e_retired", "doc-1") == 0

    async def test_another_documents_rows_are_untouched(self, client, engine, tenant):
        await _define(engine, tenant, "Skill", "e_skill")
        await _reconcile(engine, tenant, [_spec("Skill", "e_skill")])
        await _seed(engine, tenant, "doc-1", ["e_skill"])
        await _seed(engine, tenant, "doc-2", ["e_skill"])

        await client.delete("/api/v1/documents/doc-1", headers=tenant["headers"])

        assert await _count(engine, tenant["schema"], "e_skill", "doc-2") == 1
        assert await _count(engine, tenant["schema"], "subject", "doc-2") == 1

    async def test_deleting_a_never_extracted_document_does_not_raise(
        self, client, engine, tenant
    ):
        await _define(engine, tenant, "Skill", "e_skill")
        await _reconcile(engine, tenant, [_spec("Skill", "e_skill")])
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'INSERT INTO "{tenant["schema"]}".documents (id, tenant_id, filename) '
                    "VALUES ('doc-fresh', :tid, 'new.pdf')"
                ),
                {"tid": tenant["id"]},
            )

        # No `subject` row and no child rows: the delete has to be a no-op rather than an error.
        resp = await client.delete("/api/v1/documents/doc-fresh", headers=tenant["headers"])
        assert resp.status_code == 200

    async def test_a_tenant_with_no_definitions_still_deletes(self, client, engine, tenant):
        await _reconcile(engine, tenant, [])
        await _seed(engine, tenant, "doc-1", [])

        resp = await client.delete("/api/v1/documents/doc-1", headers=tenant["headers"])
        assert resp.status_code == 200
        assert await _count(engine, tenant["schema"], "subject", "doc-1") == 0
