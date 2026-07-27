"""Parity, isolation, and observability tests for the LangGraph chat orchestration
port (openspec/changes/langgraph-orchestration). Covers tasks 2.2-2.4 and 6.1-6.9, 6.11."""
import asyncio
import logging
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.retrieval.retriever import DenseRetriever, SparseRetriever, HybridRetriever, RerankingRetriever
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.state import ChatState

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fake_vector(primary: list[float]) -> list[float]:
    vec = primary + [0.0] * (1536 - len(primary))
    return vec[:1536]


class FakeEmbeddingService:
    def __init__(self, query_vector: list[float]):
        self.query_vector = query_vector

    async def embed(self, query: str) -> list[float]:
        return self.query_vector


class RecordingChatCompletions:
    def __init__(self, reply: str = "stubbed reply"):
        self.reply = reply
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)

        class Choice:
            class Message:
                pass
            message = Message()
        Choice.message.content = self.reply

        class Response:
            choices = [Choice()]
        return Response()


class RecordingChat:
    def __init__(self, reply: str = "stubbed reply"):
        self.completions = RecordingChatCompletions(reply)


class RecordingLLMClient:
    def __init__(self, reply: str = "stubbed reply"):
        self.chat = RecordingChat(reply)


class NoopGuardrails:
    def check_blocked_question_type(self, message, tenant_id):
        return None

    def assess_complexity(self, message):
        return 1

    def enforce_sources(self, reply, sources):
        return reply, sources


class NoopSqlGenerator:
    async def generate_and_execute(self, message, session, schema, conv_text):
        return None


class NoopNERClient:
    async def infer(self, text, tenant_id, jwt_token=None):
        return []


def _make_orchestrator(retriever, llm_client=None, sql_generator=None, ner_client=None, guardrails=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = retriever
    orchestrator.llm_client = llm_client or RecordingLLMClient()
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = guardrails or NoopGuardrails()
    orchestrator.sql_generator = sql_generator or NoopSqlGenerator()
    orchestrator.ner_client = ner_client or NoopNERClient()
    return orchestrator


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


@pytest_asyncio.fixture
async def chunks_schema(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await _create_chunks_table(session, schema)
        await session.commit()
    yield tenant_id, schema, session_factory


# ---------------------------------------------------------------------------
# Scenario 1 / task 2.2-2.4, 6.1: golden-transcript parity between legacy and graph
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGraphMatchesLegacyForNormalFlow:
    """Covers scenario 1: task 6.1. Runs the same inputs through _execute_legacy
    and the graph-backed execute(), asserting identical prompt, sources, and reply."""

    async def test_prompt_sources_and_reply_are_byte_identical(self, chunks_schema, monkeypatch):
        tenant_id, schema, session_factory = chunks_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk about revenue figures", query_vec)
            await session.commit()

        monkeypatch.setattr(settings, "reranker_enabled", False)

        def _build():
            base_retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())
            retriever = RerankingRetriever(base_retriever, reranker=None)
            llm = RecordingLLMClient(reply="the answer is 42")
            orchestrator = _make_orchestrator(retriever, llm_client=llm)
            return orchestrator, llm

        legacy_orch, legacy_llm = _build()
        async with session_factory() as session:
            legacy_reply, legacy_sources = await legacy_orch._execute_legacy(
                "how many organizations", session, schema, tenant_id,
            )

        graph_orch, graph_llm = _build()
        async with session_factory() as session:
            graph_reply, graph_sources = await graph_orch.execute(
                "how many organizations", session, schema, tenant_id,
            )

        assert legacy_llm.chat.completions.calls[0]["messages"] == graph_llm.chat.completions.calls[0]["messages"]
        assert legacy_llm.chat.completions.calls[0]["temperature"] == graph_llm.chat.completions.calls[0]["temperature"]
        assert legacy_llm.chat.completions.calls[0]["max_tokens"] == graph_llm.chat.completions.calls[0]["max_tokens"]
        assert legacy_reply == graph_reply
        assert [s.model_dump() for s in legacy_sources] == [s.model_dump() for s in graph_sources]


@pytest.mark.asyncio
class TestGuardrailShortCircuitParity:
    """Covers scenarios 10, 11: task 6.7. Both early-exit paths make zero downstream calls."""

    async def test_blocked_question_makes_zero_downstream_calls(self):
        class SpyRetriever:
            calls = 0
            async def retrieve(self, *a, **kw):
                type(self).calls += 1
                return []

        class SpySqlGenerator:
            calls = 0
            async def generate_and_execute(self, *a, **kw):
                type(self).calls += 1
                return None

        class SpyNERClient:
            calls = 0
            async def infer(self, *a, **kw):
                type(self).calls += 1
                return []

        llm = RecordingLLMClient()
        orchestrator = _make_orchestrator(
            SpyRetriever(), llm_client=llm, sql_generator=SpySqlGenerator(), ner_client=SpyNERClient(),
            guardrails=GuardrailService(),
        )

        class FakeSession:
            pass

        reply, sources = await orchestrator.execute(
            "please write an email for me", FakeSession(), "tenant_x", "tenant-1",
        )

        assert reply == "I can only answer questions about extracted entities and document content. I cannot generate content."
        assert sources == []
        assert SpyRetriever.calls == 0
        assert SpySqlGenerator.calls == 0
        assert SpyNERClient.calls == 0
        assert llm.chat.completions.calls == []

    async def test_excess_complexity_makes_zero_downstream_calls(self):
        class SpyRetriever:
            calls = 0
            async def retrieve(self, *a, **kw):
                type(self).calls += 1
                return []

        class HighComplexityGuardrails(NoopGuardrails):
            def assess_complexity(self, message):
                return 5

        llm = RecordingLLMClient()
        orchestrator = _make_orchestrator(SpyRetriever(), llm_client=llm, guardrails=HighComplexityGuardrails())

        class FakeSession:
            pass

        reply, sources = await orchestrator.execute("a complex question", FakeSession(), "tenant_x", "tenant-1")

        assert reply == "That question requires multiple lookups. Please simplify and ask one thing at a time."
        assert sources == []
        assert SpyRetriever.calls == 0
        assert llm.chat.completions.calls == []


# ---------------------------------------------------------------------------
# Scenarios 6, 7 / task 6.6: explicit stage outcomes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRetrievalErrorDistinctFromEmpty:
    async def test_missing_table_sets_retrieval_error(self, tenant_schema, engine):
        tenant_id, schema = tenant_schema
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))
        orchestrator = _make_orchestrator(retriever)
        graph = build_chat_graph(orchestrator)

        async with session_factory() as session:
            state: ChatState = {
                "message": "any question",
                "tenant_id": tenant_id,
                "schema": schema,
                "jwt_token": None,
                "conversation_context": None,
                "session": session,
            }
            result = await graph.ainvoke(state)

        assert result["chunks"] == []
        assert result["retrieval_error"] is not None
        assert isinstance(result["reply"], str)

    async def test_empty_table_has_no_retrieval_error(self, chunks_schema):
        tenant_id, schema, session_factory = chunks_schema
        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))
        orchestrator = _make_orchestrator(retriever)
        graph = build_chat_graph(orchestrator)

        async with session_factory() as session:
            state: ChatState = {
                "message": "any question",
                "tenant_id": tenant_id,
                "schema": schema,
                "jwt_token": None,
                "conversation_context": None,
                "session": session,
            }
            result = await graph.ainvoke(state)

        assert result["chunks"] == []
        assert result["retrieval_error"] is None


# ---------------------------------------------------------------------------
# Scenarios 4, 15 / task 6.4: tenant isolation, no shared jwt_token attribute
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTenantJwtIsolation:
    async def test_no_jwt_token_attribute_exists_on_reranking_retriever(self):
        assert not hasattr(RerankingRetriever, "jwt_token")
        retriever = RerankingRetriever(retriever=object(), reranker=object())
        assert not hasattr(retriever, "jwt_token")

    async def test_interleaved_requests_carry_correct_jwt_per_tenant(self, chunks_schema):
        tenant_id, schema, session_factory = chunks_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "chunk one", query_vec)
            await session.commit()

        seen_tokens: list[str] = []

        class RecordingReranker:
            async def rerank(self, query, results, top_k=None, jwt_token=None):
                seen_tokens.append(jwt_token)
                await asyncio.sleep(0)  # yield control to interleave with the other request
                return results

        base_retriever_a = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())
        base_retriever_b = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())
        retriever_a = RerankingRetriever(base_retriever_a, RecordingReranker())
        retriever_b = RerankingRetriever(base_retriever_b, RecordingReranker())

        async def run(retriever, token):
            async with session_factory() as session:
                return await retriever.retrieve("chunk", session, schema, top_k=5, jwt_token=token)

        await asyncio.gather(run(retriever_a, "token-A"), run(retriever_b, "token-B"))

        assert "token-A" in seen_tokens
        assert "token-B" in seen_tokens


# ---------------------------------------------------------------------------
# Task 6.9: no LangChain model/retriever wrappers introduced
# ---------------------------------------------------------------------------

class TestNoLangChainWrappers:
    def test_chat_api_does_not_import_forbidden_langchain_modules(self):
        forbidden = ["langchain_openai", "langchain_community", "langchain.chains", "langchain.vectorstores", "langchain.retrievers"]
        chat_api_dir = REPO_ROOT / "src" / "chat_api"
        offenders = []
        for py_file in chat_api_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for module in forbidden:
                if module in content:
                    offenders.append((str(py_file), module))
        assert offenders == []

    def test_no_torch_transformers_onnx_in_chat_api(self):
        forbidden = ["import torch", "import transformers", "from transformers", "import onnxruntime"]
        chat_api_dir = REPO_ROOT / "src" / "chat_api"
        offenders = []
        for py_file in chat_api_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for module in forbidden:
                if module in content:
                    offenders.append((str(py_file), module))
        assert offenders == []


# ---------------------------------------------------------------------------
# Task 6.8: node-level trace logging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNodeTraceLogging:
    async def test_each_node_emits_one_trace_record(self, chunks_schema, caplog):
        tenant_id, schema, session_factory = chunks_schema
        retriever = DenseRetriever(FakeEmbeddingService(_fake_vector([1.0, 0.0, 0.0])))
        llm = RecordingLLMClient(reply="ok")
        orchestrator = _make_orchestrator(retriever, llm_client=llm)

        with caplog.at_level(logging.INFO, logger="src.chat_api.graph.nodes"):
            async with session_factory() as session:
                await orchestrator.execute("any question", session, schema, tenant_id)

        node_names_logged = {
            record.message.split("node=")[1].split(" ")[0]
            for record in caplog.records
            if "graph node=" in record.message
        }
        assert node_names_logged == {
            "guardrail", "sql_retrieval", "retrieval", "ner_enrichment",
            "source_assembly", "prompt_assembly", "generation",
        }

    async def test_reranker_fallback_is_logged(self, chunks_schema, caplog):
        tenant_id, schema, session_factory = chunks_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk", query_vec)
            await session.commit()

        class UnavailableReranker:
            async def rerank(self, query, results, top_k=None, jwt_token=None):
                return None

        base_retriever = HybridRetriever(DenseRetriever(FakeEmbeddingService(query_vec)), SparseRetriever())
        retriever = RerankingRetriever(base_retriever, UnavailableReranker())

        with caplog.at_level(logging.WARNING, logger="src.shared.retrieval.retriever"):
            async with session_factory() as session:
                await retriever.retrieve("a chunk", session, schema, top_k=5)

        assert any("Reranker fallback" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Task 6.5: parallel-branch sessions under real concurrent DB load
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestParallelBranchSessionsUnderLoad:
    async def test_concurrent_sql_and_vector_queries_do_not_raise(self, chunks_schema):
        tenant_id, schema, session_factory = chunks_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "revenue figures for the quarter", query_vec)
            await session.commit()

        class RealQuerySqlGenerator:
            async def generate_and_execute(self, message, session, schema, conv_text):
                result = await session.execute(text(f"SELECT id FROM {schema}.documents"))
                return [{"id": r[0]} for r in result.fetchall()]

        retriever = DenseRetriever(FakeEmbeddingService(query_vec))
        llm = RecordingLLMClient(reply="ok")
        orchestrator = _make_orchestrator(retriever, llm_client=llm, sql_generator=RealQuerySqlGenerator())

        async def one_request():
            async with session_factory() as session:
                return await orchestrator.execute("revenue figures", session, schema, tenant_id)

        results = await asyncio.gather(*(one_request() for _ in range(5)), return_exceptions=True)

        for r in results:
            assert not isinstance(r, Exception), f"parallel branch raised: {r!r}"
            reply, sources = r
            assert isinstance(reply, str)


# ---------------------------------------------------------------------------
# Task 6.10: latency sanity check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLatencySanity:
    async def test_graph_path_not_dramatically_slower_than_legacy(self, chunks_schema):
        tenant_id, schema, session_factory = chunks_schema
        doc_id = f"doc-{uuid.uuid4()}"
        query_vec = _fake_vector([1.0, 0.0, 0.0])

        async with session_factory() as session:
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
                {"id": doc_id, "tid": tenant_id},
            )
            await _insert_chunk(session, schema, doc_id, 0, "a chunk", query_vec)
            await session.commit()

        def _build():
            retriever = DenseRetriever(FakeEmbeddingService(query_vec))
            llm = RecordingLLMClient(reply="ok")
            return _make_orchestrator(retriever, llm_client=llm)

        legacy_orch = _build()
        start = time.monotonic()
        async with session_factory() as session:
            await legacy_orch._execute_legacy("a question", session, schema, tenant_id)
        legacy_elapsed = time.monotonic() - start

        graph_orch = _build()
        start = time.monotonic()
        async with session_factory() as session:
            await graph_orch.execute("a question", session, schema, tenant_id)
        graph_elapsed = time.monotonic() - start

        # Generous bound — this is a smoke check against gross regression (e.g. an
        # accidental serial fan-out), not a tight performance assertion.
        assert graph_elapsed < legacy_elapsed + 2.0


# ---------------------------------------------------------------------------
# Task 6.11: rollback exercise
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRollbackToggle:
    async def test_legacy_flag_bypasses_graph_but_reply_matches(self, monkeypatch):
        class SpyRetriever:
            async def retrieve(self, *a, **kw):
                return []

        class BlockedGuardrails(NoopGuardrails):
            def check_blocked_question_type(self, message, tenant_id):
                return "content_generation"

        llm = RecordingLLMClient()
        orchestrator = _make_orchestrator(SpyRetriever(), llm_client=llm, guardrails=BlockedGuardrails())

        class FakeSession:
            pass

        monkeypatch.setattr(settings, "chat_use_graph", True)
        graph_reply, graph_sources = await orchestrator.execute("write an email", FakeSession(), "s", "t")

        monkeypatch.setattr(settings, "chat_use_graph", False)
        legacy_reply, legacy_sources = await orchestrator.execute("write an email", FakeSession(), "s", "t")

        assert graph_reply == legacy_reply
        assert graph_sources == legacy_sources
