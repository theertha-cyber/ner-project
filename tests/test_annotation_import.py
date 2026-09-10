"""Tests for annotation file import (JSONL and CoNLL) and export merge."""
import io
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

# ── Fixtures (mirror test_annotation_workspace) ──────────────────────────


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid, role="tenant_admin"):
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
                reviewed BOOLEAN NOT NULL DEFAULT FALSE,
                pending_mapping BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.annotation_imports (
                source_file VARCHAR PRIMARY KEY,
                row_count INTEGER NOT NULL DEFAULT 0,
                type_map JSONB,
                training_eligible_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
                qa_examples JSONB,
                validation_rule VARCHAR(500),
                target_table VARCHAR(255),
                base_label_mapping JSON,
                value_kind VARCHAR(32),
                value_unit VARCHAR(32),
                cardinality VARCHAR(16) NOT NULL DEFAULT 'multi',
                sql_identifier VARCHAR(63),
                version INTEGER DEFAULT 1,
                required_flag BOOLEAN DEFAULT false,
                is_active BOOLEAN DEFAULT true,
                provenance VARCHAR(16) NOT NULL DEFAULT 'manual',
                provenance_ref VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        for ddl in _create_tables_sql(tenant_schema):
            await conn.execute(text(ddl))

    async with engine.connect() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) VALUES (:id, :name, :slug, 'active', 10, 1000, 5, 10)"),
            {"id": tid, "name": "Import Test", "slug": f"imp-test-{tid[:8]}"},
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
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# ── 4.1 Unit tests: JSONL parser ────────────────────────────────────────


class TestParseJsonl:

    def test_valid_jsonl(self):
        content = (
            '{"tokens": ["John", "lives", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-LOC"]}\n'
            '{"tokens": ["Google", "is", "hiring"], "tags": ["B-ORG", "O", "O"]}\n'
        )
        result = parse_jsonl(content)
        assert len(result) == 2
        assert result[0]["tokens"] == ["John", "lives", "in", "NYC"]
        assert result[0]["tags"] == ["B-PER", "O", "O", "B-LOC"]
        assert result[1]["tokens"] == ["Google", "is", "hiring"]

    def test_malformed_json_raises(self):
        content = "{invalid json here}\n"
        with pytest.raises(HTTPException) as exc:
            parse_jsonl(content)
        assert exc.value.status_code == 422

    def test_empty_file_raises(self):
        with pytest.raises(HTTPException) as exc:
            parse_jsonl("")
        assert exc.value.status_code == 422

    def test_token_tag_length_mismatch_raises(self):
        content = '{"tokens": ["a", "b"], "tags": ["O"]}\n'
        with pytest.raises(HTTPException) as exc:
            parse_jsonl(content)
        assert exc.value.status_code == 422

    def test_skips_blank_lines(self):
        content = (
            '\n'
            '{"tokens": ["x"], "tags": ["O"]}\n'
            '\n'
        )
        result = parse_jsonl(content)
        assert len(result) == 1

    def test_non_dict_json_raises(self):
        content = '["tokens", "tags"]\n'
        with pytest.raises(HTTPException) as exc:
            parse_jsonl(content)
        assert exc.value.status_code == 422

    def test_missing_tokens_or_tags_raises(self):
        content = '{"tokens": ["a"]}\n'
        with pytest.raises(HTTPException) as exc:
            parse_jsonl(content)
        assert exc.value.status_code == 422


# ── 4.2 Unit tests: CoNLL parser ────────────────────────────────────────


class TestParseConll:

    def test_valid_conll(self):
        content = "John\tB-PER\nlives\tO\nin\tO\nNYC\tB-LOC\n\nGoogle\tB-ORG\nhires\tO\n"
        result = parse_conll(content)
        assert len(result) == 2
        assert result[0]["tokens"] == ["John", "lives", "in", "NYC"]
        assert result[0]["tags"] == ["B-PER", "O", "O", "B-LOC"]

    def test_trailing_newlines(self):
        content = "John\tB-PER\n\n\n"
        result = parse_conll(content)
        assert len(result) == 1

    def test_rejects_space_separator(self):
        content = "John B-PER\n"
        with pytest.raises(HTTPException) as exc:
            parse_conll(content)
        assert exc.value.status_code == 422

    def test_unicode_tokens(self):
        content = "José\tB-PER\nvive\tO\nen\tO\nMéxico\tB-LOC\n"
        result = parse_conll(content)
        assert len(result) == 1
        assert result[0]["tokens"] == ["José", "vive", "en", "México"]

    def test_empty_content_raises(self):
        with pytest.raises(HTTPException) as exc:
            parse_conll("")
        assert exc.value.status_code == 422

    def test_only_blank_lines_raises(self):
        with pytest.raises(HTTPException) as exc:
            parse_conll("\n\n\n")
        assert exc.value.status_code == 422


# ── 4.3 Unit tests: strip_bio_prefix ─────────────────────────────────────


class TestStripBioPrefix:

    def test_b_prefix(self):
        assert strip_bio_prefix("B-PER") == "PER"

    def test_i_prefix(self):
        assert strip_bio_prefix("I-ORG") == "ORG"

    def test_o_tag(self):
        assert strip_bio_prefix("O") == "O"

    def test_no_prefix(self):
        assert strip_bio_prefix("PER") == "PER"


# ── 4.4 Integration test: upload valid JSONL ─────────────────────────────


@pytest.mark.asyncio
async def test_import_jsonl_201(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = (
        '{"tokens": ["John", "lives", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-LOC"]}\n'
        '{"tokens": ["Google", "is", "hiring"], "tags": ["B-ORG", "O", "O"]}\n'
    )

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["imported_count"] == 2
    assert data["skipped_count"] == 0
    assert data["warnings"] == []
    assert "entity_type_counts" in data
    assert data["entity_type_counts"].get("PER") == 1
    assert data["entity_type_counts"].get("ORG") == 1


# ── 4.3 Integration test: partial import skips unknown entity type rows ───


@pytest.mark.asyncio
async def test_import_partial_skip_unknown(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = (
        '{"tokens": ["John", "lives"], "tags": ["B-PER", "O"]}\n'
        '{"tokens": ["bad"], "tags": ["B-PRODUCT"]}\n'
        '{"tokens": ["Google", "inc"], "tags": ["B-ORG", "O"]}\n'
    )

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    # Every row is stored; the PRODUCT row is held pending a type mapping, not dropped.
    assert data["imported_count"] == 2
    assert data["pending_count"] == 1
    assert data["unmapped_types"] == [{"type": "PRODUCT", "row_count": 1}]
    assert "entity_type_counts" in data


# ── Backward-compatible: existing caller reads imported_count ────────────────


@pytest.mark.asyncio
async def test_import_backward_compatible_imported_count(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = '{"tokens": ["John", "lives"], "tags": ["B-PER", "O"]}\n'

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["imported_count"] == 1


# ── All rows unknown returns imported_count: 0 ──────────────────────────────


@pytest.mark.asyncio
async def test_import_all_rows_unknown(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = (
        '{"tokens": ["bad"], "tags": ["B-PRODUCT"]}\n'
        '{"tokens": ["worse"], "tags": ["B-FOO"]}\n'
    )

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["imported_count"] == 0
    assert data["pending_count"] == 2
    assert sorted(u["type"] for u in data["unmapped_types"]) == ["FOO", "PRODUCT"]


# ── Entity type breakdown in response ─────────────────────────────────────


@pytest.mark.asyncio
async def test_import_entity_type_breakdown(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = (
        '{"tokens": ["John", "works", "at", "Google", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-ORG", "O", "B-LOC"]}\n'
    )

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["entity_type_counts"] == {"PER": 1, "ORG": 1, "LOC": 1}


# ── 4.7 Integration test: file exceeding 50MB returns 413 ────────────────


@pytest.mark.asyncio
async def test_import_file_too_large_413(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    large_content = "x" * (51 * 1024 * 1024)

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("large.jsonl", large_content, "application/jsonl")},
        headers=auth_header(token),
    )

    assert resp.status_code == 413, f"Expected 413, got {resp.status_code}: {resp.text}"


# ── Unsupported MIME type returns 415 ──────────────────────────────────────


@pytest.mark.asyncio
async def test_import_unsupported_mime_415(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = "some binary content"

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.pdf", content, "application/pdf")},
        headers=auth_header(token),
    )

    assert resp.status_code == 415, f"Expected 415, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "UNSUPPORTED_MEDIA_TYPE" in data["detail"]["code"]


# ── 4.8 Integration test: upload CoNLL file ──────────────────────────────


@pytest.mark.asyncio
async def test_import_conll_201(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = "John\tB-PER\nlives\tO\nin\tO\nNYC\tB-LOC\n"

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.txt", content, "text/plain")},
        headers=auth_header(token),
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["imported_count"] == 1
    assert data["skipped_count"] == 0
    assert data["warnings"] == []
    assert "entity_type_counts" in data


# ── 4.5 Integration test: export merge ───────────────────────────────────


@pytest.mark.asyncio
async def test_export_merge_includes_imported(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]
    token = make_token(tid)

    # Seed a document with a span
    doc_id = str(uuid.uuid4())
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status) VALUES (:id, :tid, 'doc.txt', 'text/plain', 10, 'processed')"),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) VALUES (:sid, :doc_id, 0, \'Hello world\', 0, 11, 1)'),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id},
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:sid, :doc_id, 'PER', 0, 5, 'Hello', 1.0)"),
            {"sid": str(uuid.uuid4()), "doc_id": doc_id},
        )
    await engine.dispose()

    # Import annotations via API
    import_content = '{"tokens": ["foo", "bar"], "tags": ["B-ORG", "O"]}\n'
    import_resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("extra.jsonl", import_content, "application/jsonl")},
        headers=auth_header(token),
    )
    assert import_resp.status_code == 201

    # Export: should contain both sources
    export_resp = await client.get(
        "/api/v1/annotation-export",
        headers=auth_header(token),
    )
    assert export_resp.status_code == 200
    lines = export_resp.text.strip().split("\n")
    assert len(lines) == 2, f"Expected 2 lines (1 doc + 1 imported), got {len(lines)}"

    first = json.loads(lines[0])
    assert "tokens" in first
    assert first["tokens"] == ["Hello", "world"]

    second = json.loads(lines[1])
    assert second["tokens"] == ["foo", "bar"]


# ── 4.6 Integration test: export entity type filter applies to imported ──


@pytest.mark.asyncio
async def test_export_filter_applies_to_imported(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)
    content = (
        '{"tokens": ["x", "y"], "tags": ["B-PER", "B-ORG"]}\n'
    )

    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("test.jsonl", content, "application/jsonl")},
        headers=auth_header(token),
    )
    assert resp.status_code == 201

    export_resp = await client.get(
        "/api/v1/annotation-export?entity_types=PER",
        headers=auth_header(token),
    )
    assert export_resp.status_code == 200
    lines = export_resp.text.strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["tags"] == ["B-PER", "O"]


# ── 4.5 Edge case: empty export when nothing exists ──────────────────────


@pytest.mark.asyncio
async def test_export_empty(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    token = make_token(tid)

    resp = await client.get(
        "/api/v1/annotation-export",
        headers=auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.text.strip() == ""


# ── import-annotation-training-eligibility: RBAC, type mapping, eligibility ──


@pytest.mark.asyncio
async def test_import_requires_tenant_admin(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("t.jsonl", '{"tokens": ["a"], "tags": ["B-PER"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid, "annotator")),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_known_file_is_training_eligible(seeded_entity_types, client):
    tid, schema = seeded_entity_types["tid"], seeded_entity_types["schema"]
    resp = await client.post(
        "/api/v1/annotation-import",
        files={"file": ("known.jsonl", '{"tokens": ["a", "b"], "tags": ["B-PER", "O"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid)),
    )
    assert resp.json()["unmapped_types"] == []
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        eligible = (
            await conn.execute(
                text(f"SELECT training_eligible_at FROM {schema}.annotation_imports WHERE source_file = 'known.jsonl'")
            )
        ).scalar()
    await engine.dispose()
    assert eligible is not None


@pytest.mark.asyncio
async def test_type_map_to_existing_rewrites_and_makes_eligible(seeded_entity_types, client):
    tid, schema = seeded_entity_types["tid"], seeded_entity_types["schema"]
    await client.post(
        "/api/v1/annotation-import",
        files={"file": ("m.jsonl", '{"tokens": ["x", "y"], "tags": ["B-JOB_TITLE", "I-JOB_TITLE"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid)),
    )
    resp = await client.post(
        "/api/v1/annotation-imports/m.jsonl/type-map",
        json={"JOB_TITLE": {"to": "LOC"}},
        headers=auth_header(make_token(tid)),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["training_eligible"] is True

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(f"SELECT tags, pending_mapping FROM {schema}.imported_annotations WHERE source_file = 'm.jsonl'")
            )
        ).fetchone()
    await engine.dispose()
    assert list(row[0]) == ["B-LOC", "I-LOC"]
    assert row[1] is False


@pytest.mark.asyncio
async def test_type_map_create_new_uses_imported_provenance(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    await client.post(
        "/api/v1/annotation-import",
        files={"file": ("c.jsonl", '{"tokens": ["z"], "tags": ["B-contract_id"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid)),
    )
    resp = await client.post(
        "/api/v1/annotation-imports/c.jsonl/type-map",
        json={"contract_id": {"create": True}},
        headers=auth_header(make_token(tid)),
    )
    assert resp.status_code == 201, resp.text
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        prov = (
            await conn.execute(
                text("SELECT provenance, provenance_ref FROM public.entity_definitions WHERE tenant_id = :t AND name = 'contract_id'"),
                {"t": tid},
            )
        ).fetchone()
    await engine.dispose()
    assert prov[0] == "imported"
    assert prov[1] == "c.jsonl"


@pytest.mark.asyncio
async def test_type_map_requires_tenant_admin(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    await client.post(
        "/api/v1/annotation-import",
        files={"file": ("r.jsonl", '{"tokens": ["z"], "tags": ["B-FOO"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid)),
    )
    resp = await client.post(
        "/api/v1/annotation-imports/r.jsonl/type-map",
        json={"FOO": {"to": "LOC"}},
        headers=auth_header(make_token(tid, "annotator")),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_excludes_pending_file(seeded_entity_types, client):
    tid = seeded_entity_types["tid"]
    await client.post(
        "/api/v1/annotation-import",
        files={"file": ("p.jsonl", '{"tokens": ["z"], "tags": ["B-UNMAPPED"]}\n', "application/jsonl")},
        headers=auth_header(make_token(tid)),
    )
    export_resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))
    assert export_resp.text.strip() == ""
