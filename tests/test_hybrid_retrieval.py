import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import DenseRetriever, SparseRetriever, HybridRetriever
from src.chat_api.services.rag_orchestrator import RAGOrchestrator

pytestmark = [pytest.mark.verification]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, query_vector: list[float]):
        self.query_vector = query_vector

    async def embed(self, query: str) -> list[float]:
        return self.query_vector


async def _create_hybrid_chunks_table(session, schema: str) -> None:
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
                purpose VARCHAR(20),
                chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED
            )
        """)
    )


async def _insert_chunk(session, schema: str, doc_id: str, idx: int, chunk_text_val: str, vec: list[float]) -> str:
    chunk_id = str(uuid.uuid4())
    emb_str = "[" + ",".join(str(v) for v in vec) + "]"
    await session.execute(
        text(f"""
            INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding, purpose)
            VALUES (:id, :doc_id, :idx, :txt, '{emb_str}'::vector, 'query')
        """),
        {"id": chunk_id, "doc_id": doc_id, "idx": idx, "txt": chunk_text_val},
    )
    return chunk_id


@pytest_asyncio.fixture
async def hybrid_schema(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _create_hybrid_chunks_table(session, schema)
        await session.commit()
    yield tenant_id, schema, session_factory


@pytest.mark.integration
class TestSparseRetriever:
    """Covers scenarios 3-4: full-text search over chunk_tsv."""

    @pytest.mark.asyncio
    async def test_sparse_retriever_returns_exact_term_match(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "contains identifier ZX9981 in this chunk", _fake_vector([0.0, 0.0, 1.0]))
            await _insert_chunk(session, schema, doc_id, 1, "unrelated chunk about weather patterns", _fake_vector([0.0, 1.0, 0.0]))
            await session.commit()

        retriever = SparseRetriever()
        async with session_factory() as session:
            results = await retriever.retrieve("ZX9981", session, schema, top_k=5)

        assert len(results) == 1
        assert results[0].chunk_index == 0
        assert isinstance(results[0], RetrievalResult)

    @pytest.mark.asyncio
    async def test_sparse_retriever_returns_empty_list_no_lexical_overlap(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk about apples and oranges", _fake_vector([0.0, 0.0, 1.0]))
            await session.commit()

        retriever = SparseRetriever()
        async with session_factory() as session:
            results = await retriever.retrieve("quantum thermodynamics zephyr", session, schema, top_k=5)

        assert results == []


@pytest.mark.integration
class TestMetadataFilter:
    """Covers scenario 7 and Hallucination Risk 6."""

    @pytest.mark.asyncio
    async def test_metadata_filter_scopes_to_one_document(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_a = f"doc-{uuid.uuid4()}"
        doc_b = f"doc-{uuid.uuid4()}"
        vec = _fake_vector([0.9, 0.1, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose)
                    VALUES (:a, :tid, 'a.pdf', 'processed', 'query'), (:b, :tid, 'b.pdf', 'processed', 'query')
                """),
                {"a": doc_a, "b": doc_b, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_a, 0, "matching chunk in document a", vec)
            await _insert_chunk(session, schema, doc_b, 0, "matching chunk in document b", vec)
            await session.commit()

        retriever = DenseRetriever(FakeEmbeddingService(vec))
        async with session_factory() as session:
            results = await retriever.retrieve("matching chunk", session, schema, top_k=5, metadata_filter={"document_id": doc_a})

        assert len(results) == 1
        assert results[0].document_id == doc_a

    @pytest.mark.asyncio
    async def test_dense_retriever_metadata_filter_none_matches_no_argument(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"
        vec = _fake_vector([0.9, 0.1, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "some chunk text", vec)
            await session.commit()

        retriever = DenseRetriever(FakeEmbeddingService(vec))
        async with session_factory() as session:
            no_arg_results = await retriever.retrieve("some chunk text", session, schema, top_k=5)
        async with session_factory() as session:
            none_filter_results = await retriever.retrieve("some chunk text", session, schema, top_k=5, metadata_filter=None)

        assert len(no_arg_results) == len(none_filter_results) == 1
        assert no_arg_results[0].model_dump() == none_filter_results[0].model_dump()

    def test_metadata_filter_uses_bound_parameters(self):
        source = open("src/shared/retrieval/retriever.py").read()
        assert ":mf_document_id" in source
        assert 'metadata_filter["document_id"]}"' not in source


@pytest.mark.integration
class TestHybridRetrieverFusion:
    """Covers scenarios 5-6 and 10."""

    @pytest.mark.asyncio
    async def test_hybrid_ranks_dual_match_at_top_capped_at_top_k(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"
        strong_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            # Dual match: high semantic similarity AND exact lexical term.
            await _insert_chunk(session, schema, doc_id, 0, "invoice number QX4471 total due", strong_vec)
            # Distractors that only weakly match either signal.
            await _insert_chunk(session, schema, doc_id, 1, "an unrelated paragraph about gardening", _fake_vector([0.0, 1.0, 0.0]))
            await _insert_chunk(session, schema, doc_id, 2, "another unrelated paragraph about cooking", _fake_vector([0.0, 0.0, 1.0]))
            await session.commit()

        retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(strong_vec)), SparseRetriever())
        async with session_factory() as session:
            results = await retriever.retrieve("QX4471", session, schema, top_k=2)

        assert len(results) <= 2
        assert results[0].chunk_index == 0

    @pytest.mark.asyncio
    async def test_hybrid_includes_dense_only_match_when_sparse_empty(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"
        vec = _fake_vector([0.9, 0.1, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            # No lexical overlap with the query terms at all.
            await _insert_chunk(session, schema, doc_id, 0, "zzzznonmatchingwordforftsxx", vec)
            await session.commit()

        retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(vec)), SparseRetriever())
        async with session_factory() as session:
            results = await retriever.retrieve("completely different query terms", session, schema, top_k=5)

        assert len(results) == 1
        assert results[0].chunk_index == 0

    @pytest.mark.asyncio
    async def test_hybrid_candidate_count_bounded_by_cap(self):
        captured = {}

        class SpyRetriever:
            async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
                captured["top_k"] = top_k
                return []

        retriever = HybridRetriever(SpyRetriever(), SpyRetriever())
        await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=20)

        assert captured["top_k"] == HybridRetriever.CANDIDATE_CAP
        assert HybridRetriever.CANDIDATE_CAP == 50


@pytest.mark.integration
class TestOrchestratorLexicalRetrieval:
    """Covers scenario 15 at the retrieval layer: an exact-term query with low
    semantic similarity must still surface the matching chunk via _vector_source."""

    @pytest.mark.asyncio
    async def test_vector_source_surfaces_low_similarity_lexical_match(self, hybrid_schema):
        tenant_id, schema, session_factory = hybrid_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])
        low_similarity_vec = _fake_vector([0.0, 0.0, -1.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "reference code PL77320 appears here", low_similarity_vec)
            await session.commit()

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        orchestrator.retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())

        async with session_factory() as session:
            results = await orchestrator._vector_source("PL77320", session, schema)

        assert any(r.document_id == doc_id and r.chunk_index == 0 for r in results)
