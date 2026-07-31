import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.retrieval.retriever import DenseRetriever, SparseRetriever, HybridRetriever, RerankingRetriever
from src.shared.retrieval.tools import build_default_registry
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


class FakeChatCompletions:
    async def create(self, **kwargs):
        class Choice:
            class Message:
                content = "Here is your answer with a citation."
            message = Message()
        class Response:
            choices = [Choice()]
        return Response()


class FakeChat:
    completions = FakeChatCompletions()


class FakeLLMClient:
    chat = FakeChat()


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


def _make_orchestrator(retriever) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = retriever
    orchestrator.llm_client = FakeLLMClient()
    orchestrator.llm_model = "fake-model"

    class NoopGuardrails:
        def check_blocked_question_type(self, message, tenant_id):
            return None

        async def classify_domain(self, message, conversation_context, llm_client, llm_model):
            return True

        def enforce_sources(self, reply, sources):
            return reply, sources

    class NoopSqlGenerator:
        async def generate_and_execute(self, message, session, schema, conv_text):
            return None

    orchestrator.guardrails = NoopGuardrails()
    orchestrator.sql_generator = NoopSqlGenerator()
    orchestrator.tool_registry = build_default_registry()
    return orchestrator


@pytest_asyncio.fixture
async def reranking_schema(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _create_chunks_table(session, schema)
        await session.commit()
    yield tenant_id, schema, session_factory


@pytest.mark.integration
class TestRelevantChunkPromotedIntoContext:
    """Covers scenario 14: task 5.3."""

    @pytest.mark.asyncio
    async def test_reranking_promotes_chunk_outside_embedding_top_3(self, reranking_schema, monkeypatch):
        tenant_id, schema, session_factory = reranking_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            # Three high-similarity distractors, plus the answer chunk with low embedding similarity.
            await _insert_chunk(session, schema, doc_id, 0, "distractor chunk one", query_vec)
            await _insert_chunk(session, schema, doc_id, 1, "distractor chunk two", query_vec)
            await _insert_chunk(session, schema, doc_id, 2, "distractor chunk three", query_vec)
            await _insert_chunk(session, schema, doc_id, 3, "the chunk that actually answers the question", _fake_vector([0.0, 0.0, -1.0]))
            await session.commit()

        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 20)

        base_retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())

        class PromoteAnswerReranker:
            async def rerank(self, query, results, top_k=None, jwt_token=None):
                reordered = sorted(results, key=lambda r: 0 if "answers the question" in r.chunk_text else 1)
                return reordered[:top_k] if top_k is not None else reordered

        retriever = RerankingRetriever(base_retriever, PromoteAnswerReranker())
        orchestrator = _make_orchestrator(retriever)

        async with session_factory() as session:
            reply, sources = await orchestrator.execute(
                "which chunk answers the question", session, schema, tenant_id,
            )

        assert any(
            getattr(s, "context_snippet", None) == "the chunk that actually answers the question"
            for s in sources
        )


@pytest.mark.integration
class TestChatSurvivesRerankerOutage:
    """Covers scenario 15: task 5.4."""

    @pytest.mark.asyncio
    async def test_chat_returns_200_with_sources_when_reranker_unavailable(self, reranking_schema, monkeypatch):
        tenant_id, schema, session_factory = reranking_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk matching the question", query_vec)
            await session.commit()

        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 20)

        base_retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())

        class UnavailableReranker:
            async def rerank(self, query, results, top_k=None, jwt_token=None):
                return None

        retriever = RerankingRetriever(base_retriever, UnavailableReranker())
        orchestrator = _make_orchestrator(retriever)

        async with session_factory() as session:
            reply, sources = await orchestrator.execute("a question matching the chunk", session, schema, tenant_id)

        assert isinstance(reply, str)
        assert any(getattr(s, "source_type", None) == "document_chunk" for s in sources)


@pytest.mark.integration
class TestSqlSourceUnaffectedByReranking:
    """Covers scenario 16: task 5.5."""

    @pytest.mark.asyncio
    async def test_sql_source_identical_with_reranking_on_and_off(self, reranking_schema, monkeypatch):
        tenant_id, schema, session_factory = reranking_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk about entities", query_vec)
            await session.commit()

        sql_rows = [{"entity_type": "ORG", "count": 5}]

        class StubSqlGenerator:
            async def generate_and_execute(self, message, session, schema, conv_text):
                return sql_rows

        async def run_with_reranking(enabled: bool):
            monkeypatch.setattr(settings, "reranker_enabled", enabled)
            monkeypatch.setattr(settings, "rerank_candidate_count", 20)
            base_retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())

            class PassthroughReranker:
                async def rerank(self, query, results, top_k=None, jwt_token=None):
                    return list(reversed(results))

            retriever = RerankingRetriever(base_retriever, PassthroughReranker())
            orchestrator = _make_orchestrator(retriever)
            orchestrator.sql_generator = StubSqlGenerator()

            async with session_factory() as session:
                return await orchestrator.execute("how many organizations", session, schema, tenant_id)

        _, sources_on = await run_with_reranking(True)
        _, sources_off = await run_with_reranking(False)

        sql_on = next(s for s in sources_on if getattr(s, "source_type", None) == "sql")
        sql_off = next(s for s in sources_off if getattr(s, "source_type", None) == "sql")

        assert sql_on.entity_value == sql_off.entity_value
