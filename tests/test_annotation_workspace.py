import io
import os
import uuid
import json

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
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
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.suggested_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.annotation_tasks (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                annotator_user_id VARCHAR,
                assignee VARCHAR,
                status VARCHAR(20) DEFAULT 'unannotated',
                reviewer VARCHAR,
                dataset_version INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ
            )
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
            {"id": tid, "name": "Annotation Test", "slug": f"ann-test-{tid[:8]}"},
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
                INSERT INTO public.entity_definitions (id, tenant_id, name, examples, base_label_mapping)
                VALUES (:id1, :tid, 'PER', '["John Doe", "Alice"]', '{"PER": ["John Doe", "Alice"]}'),
                       (:id2, :tid, 'ORG', '["Acme Corp"]', '{"ORG": ["Acme Corp"]}'),
                       (:id3, :tid, 'EMAIL', '["test@example.com"]', '{"EMAIL": ["test@example.com"]}')
            """),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "id3": str(uuid.uuid4()), "tid": tid},
        )
    await engine.dispose()
    return seeded_tenant


@pytest.fixture
async def seeded_document(seeded_entity_types):
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]
    doc_id = str(uuid.uuid4())
    text_content = "John Doe works at Acme Corp and can be reached at test@example.com"

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status) VALUES (:id, :tid, 'test.txt', 'text/plain', 100, 'processed')"),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)'),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id, "txt": text_content, "length": len(text_content)},
        )
    await engine.dispose()
    return {"tid": tid, "schema": schema, "doc_id": doc_id, "text": text_content}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_7_1_span_create_returns_201(seeded_document, client):
    tid = seeded_document["tid"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/spans",
        json={"entity_type": "PER", "char_start": 0, "char_end": 8, "text": "John Doe"},
        headers=auth_header(token),
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["entity_type"] == "PER"
    assert data["char_start"] == 0
    assert data["char_end"] == 8
    assert data["text"] == "John Doe"
    assert data["confidence"] == 1.0


@pytest.mark.asyncio
async def test_7_2_span_list_returns_spans(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id1, :doc_id, 'PER', 0, 8, 'John Doe', 1.0), (:id2, :doc_id, 'ORG', 18, 27, 'Acme Corp', 1.0)"),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/spans",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_7_3_span_update_modifies_fields(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    span_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, :doc_id, 'PER', 0, 8, 'John Doe', 1.0)"),
            {"id": span_id, "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.patch(
        f"/api/v1/documents/{doc_id}/spans/{span_id}",
        json={"entity_type": "ORG"},
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json()["entity_type"] == "ORG"


@pytest.mark.asyncio
async def test_7_4_span_delete_returns_204(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    span_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, :doc_id, 'PER', 0, 8, 'John Doe', 1.0)"),
            {"id": span_id, "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.delete(
        f"/api/v1/documents/{doc_id}/spans/{span_id}",
        headers=auth_header(token),
    )

    assert resp.status_code == 204

    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine2.connect() as conn:
        row = (await conn.execute(text(f"SELECT COUNT(*) FROM {schema}.spans WHERE id = :id"), {"id": span_id})).scalar()
    await engine2.dispose()
    assert row == 0


@pytest.mark.asyncio
async def test_7_5_span_invalid_type_returns_422(seeded_document, client):
    tid = seeded_document["tid"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/spans",
        json={"entity_type": "INVALID", "char_start": 0, "char_end": 5, "text": "hello"},
        headers=auth_header(token),
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_7_6_prelabel_generates_suggestions(seeded_document, client):
    tid = seeded_document["tid"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    spans_by_type = {s["entity_type"]: s for s in data}
    assert "PER" in spans_by_type
    assert "ORG" in spans_by_type
    assert spans_by_type["PER"]["text"] == "John Doe"
    assert spans_by_type["PER"]["char_start"] == 0
    assert spans_by_type["PER"]["char_end"] == 8
    assert spans_by_type["PER"]["confidence"] == 0.85
    assert spans_by_type["ORG"]["text"] == "Acme Corp"
    assert spans_by_type["ORG"]["char_start"] == 18
    assert spans_by_type["ORG"]["char_end"] == 27
    assert spans_by_type["ORG"]["confidence"] == 0.85


@pytest.mark.asyncio
async def test_prelabel_case_insensitive(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    schema = seeded_tenant["schema"]
    doc_id = str(uuid.uuid4())
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO public.entity_definitions (id, tenant_id, name, examples, base_label_mapping)
                VALUES (:id1, :tid, 'PER', '["John Doe", "Alice"]', '{"PER": ["John Doe", "Alice"]}'),
                       (:id2, :tid, 'ORG', '["Acme Corp"]', '{"ORG": ["Acme Corp"]}')
            """),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "tid": tid},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status) VALUES (:id, :tid, 'test.txt', 'text/plain', 100, 'processed')"),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)'),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id, "txt": "JOHN DOE works at ACME CORP", "length": 28},
        )
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    spans_by_type = {s["entity_type"]: s for s in data}
    assert "PER" in spans_by_type
    assert "ORG" in spans_by_type
    assert spans_by_type["PER"]["text"] == "JOHN DOE"
    assert spans_by_type["ORG"]["text"] == "ACME CORP"


@pytest.mark.asyncio
async def test_prelabel_longest_match_wins(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    schema = seeded_tenant["schema"]
    doc_id = str(uuid.uuid4())
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO public.entity_definitions (id, tenant_id, name, examples, base_label_mapping)
                VALUES (:id1, :tid, 'organization', '["Apple Inc", "Apple"]', '{"ORG": ["Apple Inc", "Apple"]}')
            """),
            {"id1": str(uuid.uuid4()), "tid": tid},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status) VALUES (:id, :tid, 'test.txt', 'text/plain', 100, 'processed')"),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)'),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id, "txt": "Apple Inc is based here", "length": 22},
        )
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["text"] == "Apple Inc"
    assert data[0]["char_start"] == 0
    assert data[0]["char_end"] == 9


@pytest.mark.asyncio
async def test_prelabel_empty_examples_skipped(seeded_tenant, client):
    tid = seeded_tenant["tid"]
    schema = seeded_tenant["schema"]
    doc_id = str(uuid.uuid4())
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO public.entity_definitions (id, tenant_id, name, examples, base_label_mapping)
                VALUES (:id1, :tid, 'PER', '[]', '{"PER": ["John Doe"]}'),
                       (:id2, :tid, 'ORG', NULL, '{"ORG": ["Acme Corp"]}')
            """),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "tid": tid},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status) VALUES (:id, :tid, 'test.txt', 'text/plain', 100, 'processed')"),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)'),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id, "txt": "John Doe works at Acme Corp", "length": 27},
        )
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_7_7_prelabel_replaces_existing(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.suggested_spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, :doc_id, 'PER', 0, 3, 'Joh', 0.5)"),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    for s in data:
        assert not (s["char_start"] == 0 and s["char_end"] == 3 and s["text"] == "Joh"), "old suggestion should be gone"

    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine2.connect() as conn:
        count = (await conn.execute(text(f"SELECT COUNT(*) FROM {schema}.suggested_spans WHERE document_id = :doc_id"), {"doc_id": doc_id})).scalar()
        old_exists = (await conn.execute(text(f"SELECT COUNT(*) FROM {schema}.suggested_spans WHERE document_id = :doc_id AND char_start = 0 AND char_end = 3"), {"doc_id": doc_id})).scalar()
    await engine2.dispose()
    assert count == len(data)
    assert old_exists == 0, "old suggestion should be deleted from database"


@pytest.mark.asyncio
async def test_7_8_prelabel_list_suggestions(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.suggested_spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, :doc_id, 'PER', 0, 8, 'John Doe', 0.85)"),
            {"id": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/spans?type=suggested",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["entity_type"] == "PER"


@pytest.mark.asyncio
async def test_7_9_prelabel_promote_suggestion(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    suggest_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.suggested_spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, :doc_id, 'PER', 0, 8, 'John Doe', 0.85)"),
            {"id": suggest_id, "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/spans/promote/{suggest_id}",
        headers=auth_header(token),
    )

    assert resp.status_code == 201
    assert resp.json()["entity_type"] == "PER"

    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine2.connect() as conn:
        suggested_count = (await conn.execute(text(f"SELECT COUNT(*) FROM {schema}.suggested_spans WHERE id = :id"), {"id": suggest_id})).scalar()
        spans_count = (await conn.execute(text(f"SELECT COUNT(*) FROM {schema}.spans WHERE document_id = :doc_id"), {"doc_id": doc_id})).scalar()
    await engine2.dispose()
    assert suggested_count == 0
    assert spans_count >= 1


@pytest.mark.asyncio
async def test_7_10_task_create_returns_201(seeded_document, client):
    tid = seeded_document["tid"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    resp = await client.post(
        "/api/v1/annotation-tasks",
        json={"document_id": doc_id, "annotator_user_id": "user-456"},
        headers=auth_header(token),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "unannotated"
    assert data["document_id"] == doc_id
    assert data["annotator_user_id"] == "user-456"


@pytest.mark.asyncio
async def test_7_11_task_conflict_returns_409(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, :doc_id, :uid, 'unannotated')"),
            {"id": str(uuid.uuid4()), "doc_id": doc_id, "uid": "user-456"},
        )
    await engine.dispose()

    resp = await client.post(
        "/api/v1/annotation-tasks",
        json={"document_id": doc_id, "annotator_user_id": "user-789"},
        headers=auth_header(token),
    )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_7_12_task_list_with_filter(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id1, :doc_id, :uid1, 'completed'), (:id2, :doc_id, :uid2, 'unannotated')"),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "doc_id": doc_id, "uid1": "user-1", "uid2": "user-2"},
        )
    await engine.dispose()

    resp = await client.get(
        "/api/v1/annotation-tasks?status=completed",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    for t in data:
        assert t["status"] == "completed"


@pytest.mark.asyncio
async def test_7_13_task_update_status(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    task_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, :doc_id, :uid, 'unannotated')"),
            {"id": task_id, "doc_id": doc_id, "uid": "user-456"},
        )
    await engine.dispose()

    resp = await client.patch(
        f"/api/v1/annotation-tasks/{task_id}",
        json={"status": "in-progress"},
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "in-progress"


@pytest.mark.asyncio
async def test_7_14_task_complete_with_spans(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    task_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, :doc_id, :uid, 'in-progress')"),
            {"id": task_id, "doc_id": doc_id, "uid": "user-456"},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:sid, :doc_id, 'PER', 0, 8, 'John Doe', 1.0)"),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.patch(
        f"/api/v1/annotation-tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_7_15_task_complete_no_spans_422(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)
    task_id = str(uuid.uuid4())

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, :doc_id, :uid, 'in-progress')"),
            {"id": task_id, "doc_id": doc_id, "uid": "user-456"},
        )
    await engine.dispose()

    resp = await client.patch(
        f"/api/v1/annotation-tasks/{task_id}",
        json={"status": "completed"},
        headers=auth_header(token),
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_7_16_export_all_documents(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:sid, :doc_id, 'PER', 0, 8, 'John Doe', 1.0)"),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.get(
        "/api/v1/annotation-export",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
    first = json.loads(lines[0])
    assert "tokens" in first
    assert "tags" in first
    assert len(first["tokens"]) == len(first["tags"])


@pytest.mark.asyncio
async def test_7_17_export_with_type_filter(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:sid1, :doc_id, 'PER', 0, 8, 'John Doe', 1.0), (:sid2, :doc_id, 'EMAIL', 42, 58, 'test@example.com', 1.0)"),
            {"sid1": str(uuid.uuid4()), "sid2": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    resp = await client.get(
        "/api/v1/annotation-export?entity_types=PER",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    first = json.loads(lines[0])
    assert "PER" in first["tags"] or "B-PER" in first["tags"] or "I-PER" in first["tags"]


@pytest.mark.asyncio
async def test_7_18_export_with_document_filter(seeded_document, client):
    tid = seeded_document["tid"]
    schema = seeded_document["schema"]
    doc_id = seeded_document["doc_id"]
    token = make_token(tid)

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :did2, 0, \'Other document text\', 0, 18, 1)'),
            {"sid": str(uuid.uuid4()), "did2": str(uuid.uuid4())},
        )
    await engine.dispose()

    resp = await client.get(
        f"/api/v1/annotation-export?document_ids={doc_id}",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
