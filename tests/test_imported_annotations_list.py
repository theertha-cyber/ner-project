"""Tests for imported annotations list and detail endpoints."""
import os
import uuid
import json

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.annotation_service.main import app
from src.annotation_service.api.v1.import_ import parse_jsonl, parse_conll, strip_bio_prefix


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
            {"id": tid, "name": "List Test", "slug": f"lst-test-{tid[:8]}"},
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
async def seeded_rows(seeded_entity_types):
    """Seed a few imported_annotations rows for list tests."""
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.imported_annotations (id, tokens, tags, source_file, row_index, reviewed)
                VALUES (:id1, :t1, :tag1, 'batch1.txt', 0, FALSE),
                       (:id2, :t2, :tag2, 'batch1.txt', 1, FALSE),
                       (:id3, :t3, :tag3, 'batch2.jsonl', 0, TRUE)
            """),
            {
                "id1": str(uuid.uuid4()),
                "t1": ["John", "lives", "in", "NYC"],
                "tag1": ["B-PER", "O", "O", "B-LOC"],
                "id2": str(uuid.uuid4()),
                "t2": ["Google", "hires"],
                "tag2": ["B-ORG", "O"],
                "id3": str(uuid.uuid4()),
                "t3": ["Alice"],
                "tag3": ["B-PER"],
            },
        )
    await engine.dispose()
    return seeded_entity_types


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_visible_to_annotator(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.get("/api/v1/imported-annotations", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_list_visible_to_tenant_admin(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="tenant_admin")
    resp = await client.get("/api/v1/imported-annotations", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_list_hidden_for_business_user(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="business_user")
    resp = await client.get("/api/v1/imported-annotations", headers=auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_pagination(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]
    token = make_token(tid, role="annotator")

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        for i in range(5):
            await conn.execute(
                text(f"""
                    INSERT INTO {schema}.imported_annotations (id, tokens, tags, source_file, row_index)
                    VALUES (:id, :tokens, :tags, 'pagination_test.txt', :idx)
                """),
                {"id": str(uuid.uuid4()), "tokens": ["word"], "tags": ["O"], "idx": i},
            )
    await engine.dispose()

    resp = await client.get("/api/v1/imported-annotations?page=1&per_page=2", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["per_page"] == 2


@pytest.mark.asyncio
async def test_filter_by_source_file(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.get("/api/v1/imported-annotations?source_file=batch1.txt", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["source_file"] == "batch1.txt" for item in data["items"])


@pytest.mark.asyncio
async def test_filter_by_entity_type(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.get("/api/v1/imported-annotations?entity_type=ORG", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "ORG" in item["entity_types"]


@pytest.mark.asyncio
async def test_filter_by_reviewed_state(seeded_rows, client):
    tid = seeded_rows["tid"]
    token = make_token(tid, role="annotator")
    resp = await client.get("/api/v1/imported-annotations?reviewed=false", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["reviewed"] is False for item in data["items"])
