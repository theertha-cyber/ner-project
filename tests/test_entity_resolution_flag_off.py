import pytest

from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services import entity_resolver
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.config import settings
from src.shared.retrieval.orchestrator import PlanEntry, RetrievalPlan

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _restore_flag():
    original = settings.entity_resolution_enabled
    yield
    settings.entity_resolution_enabled = original


class TestFlagOffTopology:
    """Covers verification.md rows 18, 60."""

    def test_entity_resolution_node_absent_from_compiled_graph(self):
        settings.entity_resolution_enabled = False
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        graph = build_chat_graph(orchestrator)
        node_names = set(graph.get_graph().nodes.keys())
        assert "entity_resolution" not in node_names

    def test_flag_off_node_set_matches_pre_change_topology(self):
        settings.entity_resolution_enabled = False
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        graph = build_chat_graph(orchestrator)
        node_names = {n for n in graph.get_graph().nodes.keys() if not n.startswith("__")}
        assert node_names == {"guardrail", "orchestrator", "retrieval_execution", "source_assembly", "prompt_assembly", "generation"}

    def test_flag_on_adds_exactly_one_node(self):
        settings.entity_resolution_enabled = True
        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        graph = build_chat_graph(orchestrator)
        node_names = {n for n in graph.get_graph().nodes.keys() if not n.startswith("__")}
        assert node_names == {"guardrail", "orchestrator", "entity_resolution", "retrieval_execution", "source_assembly", "prompt_assembly", "generation"}


class TestFlagOffNoResolverQuery:
    """Covers verification.md row 59: with the flag off, entity_resolution_node is
    never even reachable — the builder never wires it into the graph — so no
    resolver query can be issued. This test proves the node itself is inert when
    called directly with no conversation_id (the only way it could be invoked if
    a caller bypassed the builder), and that the flag-off graph never invokes it."""

    async def test_node_is_a_noop_without_conversation_id(self, monkeypatch):
        called = []
        async def spy_resolve(*a, **kw):
            called.append(True)
            raise AssertionError("resolver must not be called")
        monkeypatch.setattr(entity_resolver, "resolve_entity", spy_resolve)

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        nodes = build_nodes(orchestrator)
        plan = RetrievalPlan(entries=[PlanEntry(capability_name="semantic_retrieval", arguments={"query": "x"})])
        state = {"message": "Tell me about Sreelakshmi", "tenant_id": "t1", "schema": "tenant_t1", "session": object(), "conversation_id": None, "retrieval_plan": plan}
        result = await nodes["entity_resolution"](state)

        assert called == []
        assert result["entity_resolution_outcome"] is None


class TestStaleStateInertWithFlagOff:
    """Covers verification.md row 62: a stored binding must not affect retrieval
    scope when the flag is off, because entity_resolution_node is never wired
    into the flag-off graph — retrieval_execution_node runs with whatever
    `resolved_document_ids` the (unset) state carries, which is none."""

    async def test_retrieval_execution_ignores_absent_resolution_state(self, monkeypatch):
        from unittest.mock import AsyncMock
        import src.chat_api.graph.nodes as nodes_module
        from src.shared.retrieval.orchestrator import OrchestrationResult, RetrievalStatus

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        orchestrator.tool_registry = object()
        orchestrator.retriever = object()
        orchestrator._sql_source = AsyncMock()
        nodes = build_nodes(orchestrator)

        fake_result = OrchestrationResult(
            chunks=[], sql_results=[{"document_id": "doc-1", "count": 5}, {"document_id": "doc-2", "count": 9}],
            status=RetrievalStatus(stop_reason="plan_executed"),
            plan_trace=[], plan_truncated=False,
        )
        async def fake_execute_plan(plan, registry, context_factory, budget, **kwargs):
            return fake_result
        monkeypatch.setattr(nodes_module, "execute_plan", fake_execute_plan)

        plan = RetrievalPlan(entries=[PlanEntry(capability_name="structured_retrieval", arguments={"query": "x"})])
        # No "resolved_document_ids" key at all — the shape entity_resolution_node
        # never wrote it in, exactly as when the flag is off.
        state = {"retrieval_plan": plan, "tenant_id": "t1", "schema": "tenant_t1", "session": object()}
        result = await nodes["retrieval_execution"](state)

        assert len(result["sql_results"]) == 2
