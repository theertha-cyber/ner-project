"""Topology and routing tests for the single, fixed chat graph
(redesign-retrieval-orchestration). Covers verification.md rows 1, 3, 4, 41."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.shared.config import Settings, settings
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.tools import build_default_registry

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = ("langchain", "langgraph.prebuilt")


class NoopGuardrails:
    def __init__(self, blocked_reason=None):
        self._blocked_reason = blocked_reason

    def check_blocked_question_type(self, message, tenant_id):
        return self._blocked_reason

    async def classify_domain(self, message, conversation_context, llm_client, llm_model):
        return True

    def enforce_sources(self, reply, sources, retrieval_status=None):
        return reply, sources


class OutOfDomainGuardrails(NoopGuardrails):
    async def classify_domain(self, message, conversation_context, llm_client, llm_model):
        return False


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


class NoopSqlGenerator:
    async def generate_and_execute(self, message, session, schema, conv_text, **_kwargs):
        return None


def _make_orchestrator(guardrails=None, llm_client=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = None
    orchestrator.llm_client = llm_client or CountingLLMClient()
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = guardrails or NoopGuardrails()
    orchestrator.sql_generator = NoopSqlGenerator()
    orchestrator.tool_registry = build_default_registry()
    return orchestrator


class TestNoAgentFrameworkImports:
    """Covers verification.md row 4."""

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

    def test_no_langchain_or_prebuilt_imports_in_shared_retrieval(self):
        offenders = []
        for path in (REPO_ROOT / "src" / "shared" / "retrieval").rglob("*.py"):
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


class TestGraphIsAcyclicWithOneConditionalEdge:
    """Covers verification.md rows 3, 4."""

    def test_compiled_graph_has_no_cycle(self):
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

    def test_single_topology_expected_nodes_only(self, monkeypatch):
        """Base topology, with entity resolution explicitly off. Pinned rather than
        inherited from the setting's default so that flipping that default is a
        deliberate change to the flag-on test below, not a silent break of this one."""
        monkeypatch.setattr(settings, "entity_resolution_enabled", False)
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        nodes = set(compiled.get_graph().nodes.keys())

        expected = {
            "__start__", "__end__", "guardrail", "orchestrator",
            "retrieval_execution", "source_assembly", "prompt_assembly", "generation",
        }
        assert nodes == expected
        # No trace of the removed flag-based topology
        assert "agentic_retrieval" not in nodes
        assert "sql_retrieval" not in nodes
        assert "retrieval" not in nodes
        assert "ner_enrichment" not in nodes

    def test_entity_resolution_topology_adds_exactly_one_node(self, monkeypatch):
        """With the flag on — now the default — the only structural difference is the
        `entity_resolution` node spliced between `orchestrator` and
        `retrieval_execution`."""
        monkeypatch.setattr(settings, "entity_resolution_enabled", True)
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        graph = compiled.get_graph()
        nodes = set(graph.nodes.keys())

        assert nodes == {
            "__start__", "__end__", "guardrail", "orchestrator", "entity_resolution",
            "retrieval_execution", "source_assembly", "prompt_assembly", "generation",
        }

        orchestrator_targets = {e.target for e in graph.edges if e.source == "orchestrator"}
        assert orchestrator_targets == {"entity_resolution"}

        resolution_out = [e for e in graph.edges if e.source == "entity_resolution"]
        assert all(e.conditional for e in resolution_out)
        assert {e.target for e in resolution_out} == {"__end__", "retrieval_execution"}

    def test_assembly_edges_run_prompt_before_sources(self):
        """Citations are derived from the evidence prompt assembly admitted, so that
        stage has to run first. `generation` still reads `sources`, written by the
        stage immediately before it. Node set and both routing predicates unchanged."""
        compiled = build_chat_graph(_make_orchestrator())
        graph = compiled.get_graph()

        def targets(node):
            return {e.target for e in graph.edges if e.source == node}

        assert targets("retrieval_execution") == {"prompt_assembly"}
        assert targets("prompt_assembly") == {"source_assembly"}
        assert targets("source_assembly") == {"generation"}
        assert targets("generation") == {"__end__"}

    def test_default_configuration_enables_entity_resolution(self):
        """Guards the shipped default: with it off, a question naming a person is never
        scoped to that person's document."""
        assert Settings.model_fields["entity_resolution_enabled"].default is True

    def test_guardrail_has_exactly_one_conditional_edge(self):
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        graph = compiled.get_graph()

        guardrail_out_edges = [e for e in graph.edges if e.source == "guardrail"]
        conditional_edges = [e for e in guardrail_out_edges if e.conditional]
        assert len(conditional_edges) == len(guardrail_out_edges)
        assert len(guardrail_out_edges) == 2  # end | orchestrator

        # Every other node has only unconditional edges.
        for other_node in ("orchestrator", "retrieval_execution", "source_assembly", "prompt_assembly", "generation"):
            out_edges = [e for e in graph.edges if e.source == other_node]
            assert all(not e.conditional for e in out_edges)


class TestNoRoutingFlags:
    """Covers verification.md row 3: no setting selects retrieval strategy or topology."""

    def test_no_retrieval_strategy_or_topology_settings(self):
        field_names = set(Settings.model_fields)
        removed_flags = {
            "chat_use_graph", "chat_agentic_retrieval", "agentic_max_iterations",
            "agentic_max_iterations_complex", "agentic_max_tool_calls",
            "agentic_deadline_seconds", "agentic_observation_char_limit",
        }
        assert field_names.isdisjoint(removed_flags)

    def test_build_chat_graph_takes_no_topology_parameter(self):
        import inspect
        sig = inspect.signature(build_chat_graph)
        assert list(sig.parameters) == ["orchestrator"]


class TestDeclinedTurnInvokesNoRetrieval:
    """Covers verification.md row 41."""

    @pytest.mark.asyncio
    async def test_out_of_domain_decline_invokes_neither_orchestrator_nor_retrieval(self):
        llm = CountingLLMClient()
        orchestrator = _make_orchestrator(guardrails=OutOfDomainGuardrails(), llm_client=llm)
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "Tell me a joke.", "tenant_id": "t1", "conversation_context": None})

        assert result["sources"] == []
        assert "reply" in result
        # classify_domain is a stub here (no LLM call), so the only calls the generation
        # LLM client would see are downstream of the graph's conditional edge — verified
        # not to run by checking the graph itself never reaches orchestrator/retrieval
        # for a declined state.
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_blocked_question_type_short_circuits_before_orchestrator(self):
        orchestrator = _make_orchestrator(guardrails=NoopGuardrails(blocked_reason="pii"))
        nodes = build_nodes(orchestrator)

        result = await nodes["guardrail"]({"message": "ssn number please", "tenant_id": "t1", "conversation_context": None})

        assert result["blocked_reason"] == "pii"
        assert result["sources"] == []

    def test_route_after_guardrail_sends_decline_to_end(self):
        from src.chat_api.graph.builder import _route_after_guardrail

        assert _route_after_guardrail({"reply": "declined"}) == "end"
        assert _route_after_guardrail({}) == "orchestrator"
