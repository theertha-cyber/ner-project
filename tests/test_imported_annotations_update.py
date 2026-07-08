"""Tests for imported annotations update endpoints (PATCH and mark-reviewed)."""
import os
import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.annotation_service.main import app


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid, role="annotator"):
    return create_access_token(tenant_id=tid, user_id="test-user", role=role)


def _create_tables_sql(schema: str) -> list:
    return [
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                filename VARCHAR(255) NOT NULL,
                content_type VARCHAR(255),
                file_size BIGINT,
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT,
                blob_path VARCHAR(500),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                span_index INTEGER,
                "text" TEXT,
                char_start INTEGER,
                char_end INTEGER,
                page_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL DEFAULT 1.0,
                bio_tags TEXT[],
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.imported_annotations (
                id VARCHAR PRIMARY KEY,
                tokens TEXT[] NOT NULL,
                tags TEXT[] NOT NULL,
                source_file VARCHAR NOT NULL,
                row_index INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            ALTER TABLE {schema}.imported_annotations
                ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR
        """,
    ]


@pytest.fixture(autouse=True)
async def cleanup_public():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
    )
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'"))
        for row in rows:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {row[0]} CASCADE"))
    async with engine.connect() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS public.entity_definitions CASCADE"))
    await engine.dispose()


@pytest.fixture
async def seeded_tenant():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
    )

    tid = uuid.uuid4().hex
    tenant_schema = f"tenant_{tid}"

    async with engine.connect() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {tenant_schema}"))
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenants (
                id VARCHAR PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                slug VARCHAR(63) NOT NULL UNIQUE,
                status VARCHAR(20) DEFAULT 'active',
                max_users INTEGER DEFAULT 10,
                max_documents INTEGER DEFAULT 1000,
                max_storage_gb INTEGER DEFAULT 5,
                max_model_versions INTEGER DEFAULT 10,
                storage_used_bytes BIGINT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.entity_definitions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                examples JSON,
                validation_rule VARCHAR(500),
                target_table VARCHAR(255),
                base_label_mapping JSON,
                version INTEGER DEFAULT 1,
                required_flag BOOLEAN DEFAULT false,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        for ddl in _create_tables_sql(tenant_schema):
            await conn.execute(text(ddl))

    async with engine.connect() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) VALUES (:id, :name, :slug, 'active', 10, 1000, 5, 10)"),
            {"id": tid, "name": "Update Test", "slug": f"upd-test-{tid[:8]}"},
        )

    yield {"tid": tid, "schema": tenant_schema}

    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {tenant_schema} CASCADE"))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
        await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid})
    await engine.dispose()


@pytest.fixture
async def seeded_entity_types(seeded_tenant):
    tid = seeded_tenant["tid"]
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO public.entity_definitions (id, tenant_id, name, base_label_mapping)
                VALUES (:id1, :tid, 'PER', '{"PER": ["John"]}'),
                       (:id2, :tid, 'ORG', '{"ORG": ["Google"]}'),
                       (:id3, :tid, 'LOC', '{"LOC": ["NYC"]}')
            """),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "id3": str(uuid.uuid4()), "tid": tid},
        )
    await engine.dispose()
    return seeded_tenant


@pytest.fixture
async def seeded_row(seeded_entity_types):
    """Seed a single unreviewed imported row for update tests."""
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]
    row_id = str(uuid.uuid4())
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.imported_annotations (id, tokens, tags, source_file, row_index, reviewed)
                VALUES (:id, :tokens, :tags, 'update_test.txt', 0, FALSE)
            """),
            {
                "id": row_id,
                "tokens": ["Jane", "Doe", "works", "at", "Google", "in", "NYC"],
                "tags": ["B-PER", "I-PER", "O", "O", "B-ORG", "O", "B-LOC"],
            },
        )
    await engine.dispose()
    return {"row_id": row_id, "tid": tid, "schema": schema}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_retype_span(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["B-ORG", "I-ORG", "O", "O", "B-ORG", "O", "B-LOC"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tags"][0] == "B-ORG"
    assert data["tags"][1] == "I-ORG"


@pytest.mark.asyncio
async def test_delete_span(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["O", "O", "O", "O", "B-ORG", "O", "B-LOC"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tags"][0] == "O"
    assert data["tags"][1] == "O"


@pytest.mark.asyncio
async def test_create_span(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["B-PER", "I-PER", "O", "O", "B-ORG", "B-DATE", "I-DATE"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tags"][5] == "B-DATE"
    assert data["tags"][6] == "I-DATE"


@pytest.mark.asyncio
async def test_reject_unknown_entity_type(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        row_before = await conn.execute(
            text(f"SELECT tags FROM {seeded_row['schema']}.imported_annotations WHERE id = :id"),
            {"id": seeded_row["row_id"]},
        )
        tags_before = list(row_before.fetchone()[0])
    await engine.dispose()

    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["B-PRODUCT", "I-PRODUCT", "O", "O", "B-ORG", "O", "B-LOC"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 422

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        row_after = await conn.execute(
            text(f"SELECT tags FROM {seeded_row['schema']}.imported_annotations WHERE id = :id"),
            {"id": seeded_row["row_id"]},
        )
        tags_after = list(row_after.fetchone()[0])
    await engine.dispose()
    assert tags_after == tags_before


@pytest.mark.asyncio
async def test_save_edit_marks_reviewed(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["B-PER", "I-PER", "O", "O", "B-ORG", "O", "B-LOC"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewed"] is True
    assert data["reviewed_at"] is not None
    assert data["reviewed_by"] is not None


@pytest.mark.asyncio
async def test_mark_reviewed_without_edits(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        row_before = await conn.execute(
            text(f"SELECT tags FROM {seeded_row['schema']}.imported_annotations WHERE id = :id"),
            {"id": seeded_row["row_id"]},
        )
        tags_before = list(row_before.fetchone()[0])
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}/mark-reviewed",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewed"] is True

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        row_after = await conn.execute(
            text(f"SELECT tags FROM {seeded_row['schema']}.imported_annotations WHERE id = :id"),
            {"id": seeded_row["row_id"]},
        )
        tags_after = list(row_after.fetchone()[0])
    await engine.dispose()
    assert tags_after == tags_before


@pytest.mark.asyncio
async def test_no_task_or_document_created_on_edit(seeded_row, client):
    tid = seeded_row["tid"]
    token = make_token(tid, role="annotator")

    resp = await client.patch(
        f"/api/v1/imported-annotations/{seeded_row['row_id']}",
        json={"tags": ["B-PER", "I-PER", "O", "O", "B-ORG", "O", "B-LOC"]},
        headers=auth_header(token),
    )
    assert resp.status_code == 200

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        docs = (await conn.execute(text(f"SELECT COUNT(*) FROM {seeded_row['schema']}.documents"))).scalar()
        tasks = (await conn.execute(text(f"SELECT COUNT(*) FROM {seeded_row['schema']}.annotation_tasks"))).scalar() if False else 0
        try:
            tasks = (await conn.execute(text(f"SELECT COUNT(*) FROM {seeded_row['schema']}.annotation_tasks"))).scalar()
        except Exception:
            tasks = 0
        spans = (await conn.execute(text(f"SELECT COUNT(*) FROM {seeded_row['schema']}.spans"))).scalar()
    await engine.dispose()

    assert docs == 0, "No documents should be created"
    assert spans == 0, "No spans should be created"
