import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.retrieval.retriever import DenseRetriever
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.document_tools import lookup_document, search_documents
from src.shared.retrieval.tools.entity_tools import search_entities

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, query_vector: list[float]):
        self.query_vector = query_vector

    async def embed(self, query: str) -> list[float]:
        return self.query_vector


async def _create_chunks_table(session, schema: str) -> None:
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await session.execute(
        text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding vector(1536),
                page_number INTEGER,
                char_start INTEGER,
                char_end INTEGER,
                purpose VARCHAR(20) NOT NULL DEFAULT 'query',
                chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
            )
        """)
    )


async def _insert_chunk(session, schema: str, doc_id: str, idx: int, text_val: str, vec: list[float], purpose: str = "query") -> None:
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"
    await session.execute(
        text(f"""
            INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
            VALUES (:id, :doc_id, :idx, :txt, '{emb_str}'::vector, :purpose)
        """),
        {"id": str(uuid.uuid4()), "doc_id": doc_id, "idx": idx, "txt": text_val, "purpose": purpose},
    )


async def _insert_document(session, schema: str, tenant_id: str, doc_id: str) -> None:
    await session.execute(
        text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
        {"id": doc_id, "tid": tenant_id},
    )


@pytest_asyncio.fixture
async def seeded_schema(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _create_chunks_table(session, schema)
        await session.commit()
    yield tenant_id, schema, session_factory


async def _create_second_schema(engine, tenant_id: str) -> tuple[str, "async_sessionmaker"]:
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'uploaded', purpose VARCHAR(20) NOT NULL DEFAULT 'query'
            )
        """))
    async with session_factory() as session:
        await _create_chunks_table(session, schema)
        await session.commit()
    return schema, session_factory


class TestLookupDocumentRestriction:
    """Covers verification.md row 11."""

    async def test_lookup_document_restricts_to_document_id(self, seeded_schema):
        tenant_id, schema, session_factory = seeded_schema
        doc_a, doc_b = f"doc-{uuid.uuid4()}", f"doc-{uuid.uuid4()}"
        vec = _fake_vector([0.9, 0.1, 0.0])

        async with session_factory() as session:
            await _insert_document(session, schema, tenant_id, doc_a)
            await _insert_document(session, schema, tenant_id, doc_b)
            await _insert_chunk(session, schema, doc_a, 0, "matching chunk in document a", vec)
            await _insert_chunk(session, schema, doc_b, 0, "matching chunk in document b", vec)
            await session.commit()

        async with session_factory() as session:
            context = ToolContext(
                tenant_id=tenant_id, schema=schema, session=session,
                retriever=DenseRetriever(FakeEmbeddingService(vec)),
            )
            result = await lookup_document.call({"query": "matching chunk", "document_id": doc_a}, context)

        assert result.error is None
        assert result.results
        assert all(r.document_id == doc_a for r in result.results)


class TestTwoSchemaIsolation:
    """Covers verification.md row 8."""

    async def test_tool_queries_context_schema_only(self, seeded_schema, engine):
        tenant_id_a, schema_a, session_factory = seeded_schema
        schema_b, _ = await _create_second_schema(engine, "isolation-tenant-b")
        vec = _fake_vector([0.5, 0.5, 0.0])

        doc_a = f"doc-{uuid.uuid4()}"
        doc_b = f"doc-{uuid.uuid4()}"
        async with session_factory() as session:
            await _insert_document(session, schema_a, tenant_id_a, doc_a)
            await _insert_chunk(session, schema_a, doc_a, 0, "shared matching phrase alpha", vec)
            await session.commit()
        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema_b}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, 'isolation-tenant-b', 'b.pdf', 'processed', 'query')"),
                {"id": doc_b},
            )
            await _insert_chunk(session, schema_b, doc_b, 0, "shared matching phrase alpha", vec)
            await session.commit()

        async with session_factory() as session:
            context = ToolContext(
                tenant_id=tenant_id_a, schema=schema_a, session=session,
                retriever=DenseRetriever(FakeEmbeddingService(vec)),
            )
            result = await search_documents.call({"query": "shared matching phrase alpha"}, context)

        assert result.error is None
        assert all(r.document_id != doc_b for r in result.results)

        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_b} CASCADE"))


class TestPurposeExclusion:
    """Covers verification.md row 9."""

    async def test_training_purpose_chunks_excluded(self, seeded_schema):
        tenant_id, schema, session_factory = seeded_schema
        doc_id = f"doc-{uuid.uuid4()}"
        vec = _fake_vector([0.3, 0.3, 0.3])

        async with session_factory() as session:
            await _insert_document(session, schema, tenant_id, doc_id)
            await _insert_chunk(session, schema, doc_id, 0, "training-only content", vec, purpose="training")
            await _insert_chunk(session, schema, doc_id, 1, "query-visible content", vec, purpose="query")
            await session.commit()

        async with session_factory() as session:
            context = ToolContext(
                tenant_id=tenant_id, schema=schema, session=session,
                retriever=DenseRetriever(FakeEmbeddingService(vec)),
            )
            result = await search_documents.call({"query": "content"}, context)

        assert result.error is None
        assert all(r.chunk_index != 0 for r in result.results)


class TestSearchEntitiesReturnsRows:
    """Covers verification.md row 14."""

    async def test_search_entities_returns_structured_rows(self, seeded_schema):
        tenant_id, schema, session_factory = seeded_schema

        async def stub_sql_search(query, session, schema, conversation_context):
            result = await session.execute(text(f"SELECT 1 AS count"))
            rows = result.fetchall()
            columns = result.keys()
            return [dict(zip(columns, row)) for row in rows]

        async with session_factory() as session:
            context = ToolContext(
                tenant_id=tenant_id, schema=schema, session=session,
                sql_search=stub_sql_search,
            )
            result = await search_entities.call({"query": "how many entities"}, context)

        assert result.error is None
        assert result.results == [{"count": 1}]
