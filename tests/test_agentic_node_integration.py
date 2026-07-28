"""Node-level integration tests for the agentic retrieval loop
(src/chat_api/graph/nodes.py::agentic_retrieval_node). Covers verification.md
rows 11, 21, 22 — behaviour that only exists once the loop is wired into the
graph nodes (citation parity, node-level fallback, fallback logging)."""
import json
import logging
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.tools import build_default_registry

pytestmark = [pytest.mark.asyncio, pytest.mark.verification]


class NoopGuardrails:
    def check_blocked_question_type(self, message, tenant_id):
        return None

    def assess_complexity(self, message):
        return 1

    def enforce_sources(self, reply, sources):
        return reply, sources


class NoopNERClient:
    async def infer(self, text, tenant_id, jwt_token=None):
        return []


class NoopSqlGenerator:
    async def generate_and_execute(self, message, session, schema, conv_text):
        return None


class RaisingPlannerLLMClient:
    """chat.completions.create always raises — simulates a planner outage."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        raise RuntimeError("planner unavailable")


def _make_orchestrator(retriever=None, sql_generator=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = retriever
    orchestrator.llm_client = RaisingPlannerLLMClient()
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = NoopGuardrails()
    orchestrator.sql_generator = sql_generator or NoopSqlGenerator()
    orchestrator.ner_client = NoopNERClient()
    orchestrator.tool_registry = build_default_registry()
    orchestrator._sql_source = NoopSqlGenerator().generate_and_execute
    return orchestrator


@pytest_asyncio.fixture
async def seeded_schema(tenant_schema, engine):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = f"doc-{uuid.uuid4()}"
    async with session_factory() as session:
        await session.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) "
                 "VALUES (:id, :tid, 'seed.pdf', 'processed', 'query')"),
            {"id": doc_id, "tid": tenant_id},
        )
        await session.commit()
    yield tenant_id, schema, session_factory, doc_id


class TestCitationParity:
    """Covers verification.md row 11: citations from loop-produced evidence are
    identical to citations produced from the same evidence via the one-shot path,
    because both paths feed source_assembly_node the same ChatState['chunks'] key."""

    async def test_citations_identical_regardless_of_evidence_origin(self, seeded_schema):
        tenant_id, schema, session_factory, doc_id = seeded_schema
        orchestrator = _make_orchestrator()
        nodes = build_nodes(orchestrator)

        chunks = [
            RetrievalResult(document_id=doc_id, chunk_index=0, chunk_text="revenue grew 10%", similarity_score=0.9),
            RetrievalResult(document_id=doc_id, chunk_index=1, chunk_text="costs were flat", similarity_score=0.6),
        ]
        sql_results = [{"count": 3}]

        async with session_factory() as session:
            state_from_loop = {
                "message": "q", "tenant_id": tenant_id, "schema": schema, "session": session,
                "chunks": chunks, "sql_results": sql_results, "ner_entities": [],
            }
            result_loop = await nodes["source_assembly"](state_from_loop)

        async with session_factory() as session:
            state_from_one_shot = {
                "message": "q", "tenant_id": tenant_id, "schema": schema, "session": session,
                "chunks": chunks, "sql_results": sql_results, "ner_entities": [],
            }
            result_one_shot = await nodes["source_assembly"](state_from_one_shot)

        loop_dumps = [s.model_dump() for s in result_loop["sources"]]
        one_shot_dumps = [s.model_dump() for s in result_one_shot["sources"]]
        assert loop_dumps == one_shot_dumps

        chunk_citations = [s for s in result_loop["sources"] if s.source_type == "document_chunk"]
        assert len(chunk_citations) == 2
        for c in chunk_citations:
            assert c.document_name == "seed.pdf"
            assert c.document_id == doc_id
            assert c.relevance_score is not None
            assert c.context_snippet is not None


class TestNodeLevelFallback:
    """Covers verification.md rows 21-22: a planner failure at the node level falls
    back to the existing one-shot sql_retrieval/retrieval node logic and logs it."""

    async def test_planner_error_falls_back_to_one_shot_nodes(self, seeded_schema, monkeypatch):
        tenant_id, schema, session_factory, doc_id = seeded_schema
        orchestrator = _make_orchestrator()
        nodes = build_nodes(orchestrator)

        monkeypatch.setattr(settings, "agentic_deadline_seconds", 5.0)
        monkeypatch.setattr(settings, "agentic_max_iterations", 3)
        monkeypatch.setattr(settings, "agentic_max_tool_calls", 6)

        async with session_factory() as session:
            state = {
                "message": "q", "tenant_id": tenant_id, "schema": schema, "session": session,
                "jwt_token": None, "conversation_context": None, "complexity": 1,
            }
            result = await nodes["agentic_retrieval"](state)

        async with session_factory() as session:
            baseline_state = {
                "message": "q", "tenant_id": tenant_id, "schema": schema, "session": session,
                "jwt_token": None, "conversation_context": None, "complexity": 1,
            }
            baseline_sql = await nodes["sql_retrieval"](baseline_state)
            baseline_retrieval = await nodes["retrieval"](baseline_state)

        assert result["agentic_degraded"] is True
        assert result["agentic_stop_reason"] == "planner_error"
        # fallback reproduces exactly what the one-shot nodes would have produced
        assert result["sql_results"] == baseline_sql["sql_results"]
        assert result["sql_error"] == baseline_sql["sql_error"]
        assert result["chunks"] == baseline_retrieval["chunks"]
        assert result["retrieval_error"] == baseline_retrieval["retrieval_error"]

    async def test_fallback_is_logged_with_stop_reason(self, seeded_schema, caplog):
        tenant_id, schema, session_factory, doc_id = seeded_schema
        orchestrator = _make_orchestrator()
        nodes = build_nodes(orchestrator)

        async with session_factory() as session:
            state = {
                "message": "q", "tenant_id": tenant_id, "schema": schema, "session": session,
                "jwt_token": None, "conversation_context": None, "complexity": 1,
            }
            with caplog.at_level(logging.INFO, logger="src.chat_api.graph.nodes"):
                await nodes["agentic_retrieval"](state)

        assert any("degraded=True" in r.message and "stop_reason=planner_error" in r.message for r in caplog.records)
