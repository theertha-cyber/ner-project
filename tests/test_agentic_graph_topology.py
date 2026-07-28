"""Flag, topology, and non-substitution tests for the agentic retrieval loop.
Covers verification.md rows 3, 25, 26, 29-38 (chat-orchestration-graph and chat-api
capabilities of the agentic-retrieval-loop change)."""
import ast
import importlib
import pkgutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.shared.config import settings
import src.chat_api.graph.nodes as nodes_module
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.tools import build_default_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = ("langchain", "langgraph.prebuilt")


class NoopGuardrails:
    def __init__(self, complexity=1, blocked_reason=None):
        self._complexity = complexity
        self._blocked_reason = blocked_reason

    def check_blocked_question_type(self, message, tenant_id):
        return self._blocked_reason

    def assess_complexity(self, message):
        return self._complexity

    def enforce_sources(self, reply, sources):
        return reply, sources


class NoopSqlGenerator:
    async def generate_and_execute(self, message, session, schema, conv_text):
        return None


class NoopNERClient:
    async def infer(self, text, tenant_id, jwt_token=None):
        return []


class CountingLLMClient:
    def __init__(self):
        self.call_count = 0
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.call_count += 1

        class Message:
            content = "reply"
            tool_calls = None
        return SimpleNamespace(choices=[SimpleNamespace(message=Message())])


def _make_orchestrator(guardrails=None, llm_client=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = None
    orchestrator.llm_client = llm_client or CountingLLMClient()
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = guardrails or NoopGuardrails()
    orchestrator.sql_generator = NoopSqlGenerator()
    orchestrator.ner_client = NoopNERClient()
    orchestrator.tool_registry = build_default_registry()
    return orchestrator


# --- row 3, 33: no agent framework introduced ---

class TestNoAgentFrameworkImports:
    def test_no_langchain_or_prebuilt_imports_in_chat_api(self):
        offenders = []
        for path in (REPO_ROOT / "src" / "chat_api").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if any(name == root or name.startswith(root + ".") for root in FORBIDDEN_IMPORT_ROOTS):
                        offenders.append((str(path), name))
        assert offenders == []


# --- row 32: graph acyclic with flag enabled ---

class TestGraphAcyclicWithFlagOn:
    def test_compiled_graph_has_no_cycle(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)

        graph = compiled.get_graph()
        edges = [(e.source, e.target) for e in graph.edges]
        adjacency: dict[str, list[str]] = {}
        for src, dst in edges:
            adjacency.setdefault(src, []).append(dst)

        visiting, visited = set(), set()

        def has_cycle(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for nxt in adjacency.get(node, []):
                if has_cycle(nxt):
                    return True
            visiting.discard(node)
            visited.add(node)
            return False

        assert not any(has_cycle(n) for n in adjacency)
        assert "agentic_retrieval" in graph.nodes


# --- row 31: flag-off topology identical to pre-change ---

class TestFlagOffTopologyUnchanged(object):
    def test_flag_off_graph_has_original_nodes_only(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", False)
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        nodes = set(compiled.get_graph().nodes.keys())

        expected = {
            "__start__", "__end__", "guardrail", "sql_retrieval", "retrieval",
            "ner_enrichment", "source_assembly", "prompt_assembly", "generation",
        }
        assert nodes == expected
        assert "agentic_retrieval" not in nodes


# --- row 25: flag off makes no planner call ---

class TestFlagOffMakesNoPlannerCall:
    @pytest.mark.asyncio
    async def test_no_planner_call_with_flag_off(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", False)
        llm = CountingLLMClient()
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        state = {"message": "hello", "tenant_id": "t1"}
        result = await nodes["guardrail"](state)

        assert "reply" not in result
        assert llm.call_count == 0


# --- row 26: agentic flag inert on the legacy (non-graph) path ---

class TestLegacyPathInertness:
    @pytest.mark.asyncio
    async def test_legacy_execute_ignores_agentic_flag(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_use_graph", False)
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)

        llm = CountingLLMClient()
        orchestrator = _make_orchestrator(llm_client=llm)

        called = {"legacy": False}

        async def fake_legacy(*args, **kwargs):
            called["legacy"] = True
            return "reply", []

        orchestrator._execute_legacy = fake_legacy

        reply, sources = await orchestrator.execute("hi", session=object(), schema="s", tenant_id="t1")

        assert called["legacy"] is True
        assert reply == "reply"
        assert llm.call_count == 0


# --- row 35: planner uses the orchestrator's existing client ---

class TestPlannerUsesExistingClient:
    @pytest.mark.asyncio
    async def test_agentic_node_passes_orchestrator_llm_client(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)
        llm = CountingLLMClient()
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        import src.chat_api.graph.nodes as nodes_mod

        captured = {}
        original = nodes_mod.run_agentic_loop

        async def spy(message, conversation_context, llm_client, llm_model, *args, **kwargs):
            captured["llm_client"] = llm_client
            return await original(message, conversation_context, llm_client, llm_model, *args, **kwargs)

        monkeypatch.setattr(nodes_mod, "run_agentic_loop", spy)

        state = {
            "message": "q", "tenant_id": "t1", "schema": "tenant_t1",
            "jwt_token": None, "conversation_context": None, "complexity": 1,
        }
        await nodes["agentic_retrieval"](state)

        assert captured["llm_client"] is llm


# --- rows 29, 30: early exits unaffected ---

class TestEarlyExitsUnaffected:
    @pytest.mark.asyncio
    async def test_blocked_question_short_circuits(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(blocked_reason="content_generation"))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "write me an essay", "tenant_id": "t1"})

        assert result["blocked_reason"] == "content_generation"
        assert result["sources"] == []
        assert "That question requires" not in result["reply"]

    @pytest.mark.asyncio
    async def test_complexity_decline_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", False)
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(complexity=5))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "complex question", "tenant_id": "t1"})

        assert "simplify" in result["reply"].lower()
        assert result["sources"] == []


# --- rows 36-38: complexity guardrail is flag-aware ---

class TestComplexityGuardrailFlagAware:
    @pytest.mark.asyncio
    async def test_complex_question_declined_flag_off(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", False)
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(complexity=4))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "q", "tenant_id": "t1"})

        assert "simplify" in result["reply"].lower()
        assert result["complexity"] == 4

    @pytest.mark.asyncio
    async def test_complex_question_proceeds_flag_on(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(complexity=4))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "q", "tenant_id": "t1"})

        assert "reply" not in result
        assert result["complexity"] == 4
        assert result["blocked_reason"] is None

    @pytest.mark.asyncio
    async def test_blocked_type_still_declined_flag_on(self, monkeypatch):
        monkeypatch.setattr(settings, "chat_agentic_retrieval", True)
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(blocked_reason="pii"))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "what's their ssn number", "tenant_id": "t1"})

        assert result["blocked_reason"] == "pii"
        assert result["sources"] == []
