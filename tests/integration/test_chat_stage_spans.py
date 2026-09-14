"""One chat question produces one span per stage it executed.

Verification row 1.

This is the requirement that makes an ADR-007 P95 breach diagnosable rather than merely
visible. The foundation supplied the request-duration histogram, so today a ten-second
answer is one number: it cannot say whether the time went to retrieval, to a repair loop
that ran three times, or to a provider that was slow once.

The graph is driven directly rather than through the HTTP surface. The stages are graph
nodes, not routes, so a request-level test would assert on the wrapper and prove nothing
about which nodes ran — and the spans are attached where the nodes are registered.
"""

import pytest

from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services import entity_resolver
from src.chat_api.services.entity_resolver import ResolutionResult
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.observability import domain_metrics as dm
from src.shared.retrieval.orchestrator import PlanEntry, RetrievalPlan

pytestmark = [pytest.mark.verification]

QUESTION = "how many candidates know python"


class _SentinelSession:
    """Never dereferenced — every call that would touch the database is patched out."""


def _orchestrator():
    """A bare orchestrator with only what the stages under test dereference.

    `__new__` rather than the constructor: building a real one opens an OpenAI client and
    a database engine, neither of which this test needs and neither of which is available
    in a unit environment.
    """
    from src.chat_api.services.guardrails import GuardrailService

    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.llm_client = object()
    orchestrator.llm_model = "gpt-4o"
    orchestrator.guardrails = GuardrailService()
    return orchestrator


@pytest.fixture
def nodes():
    return build_nodes(_orchestrator())


def _state():
    return {
        "message": QUESTION,
        "tenant_id": "t1",
        "schema": "tenant_t1",
        "session": _SentinelSession(),
        "conversation_id": "conv-1",
        "retrieval_plan": RetrievalPlan(
            entries=[PlanEntry(capability_name="semantic_retrieval", arguments={"query": QUESTION})]
        ),
    }


async def _run_stages(nodes, monkeypatch):
    """Execute the stages a question actually reaches, in graph order."""

    async def _read_state(session, schema, conversation_id):
        return conv_state.ConversationState(conversation_id=conversation_id)

    async def _resolve(message, session, schema, tenant_id):
        return ResolutionResult(outcome=entity_resolver.UNRESOLVED, mentions_checked=1)

    monkeypatch.setattr(conv_state, "read_state", _read_state)
    monkeypatch.setattr(entity_resolver, "resolve_entity", _resolve)

    state = _state()
    for stage in ("guardrail", "entity_resolution"):
        state.update(await nodes[stage](state) or {})
    return state


class TestASpanPerStage:
    """Row 1."""

    async def test_each_executed_stage_produces_exactly_one_span(
        self, nodes, monkeypatch, captured_spans
    ):
        await _run_stages(nodes, monkeypatch)

        names = [s.name for s in captured_spans.get_finished_spans() if s.name.startswith("chat.")]

        assert names == ["chat.guardrail", "chat.entity_resolution"], (
            "one span per executed stage, in the order the graph ran them — not one per "
            "node in the registry, and not one per service call inside a node"
        )

    async def test_every_stage_span_carries_a_duration_and_an_outcome(
        self, nodes, monkeypatch, captured_spans
    ):
        await _run_stages(nodes, monkeypatch)

        stage_spans = [s for s in captured_spans.get_finished_spans() if s.name.startswith("chat.")]
        assert stage_spans

        for span in stage_spans:
            attributes = dict(span.attributes)
            assert "duration_ms" in attributes, f"{span.name} has no duration"
            assert attributes.get("outcome"), f"{span.name} has no outcome"

    async def test_a_stage_that_did_not_run_produces_no_span(
        self, nodes, monkeypatch, captured_spans
    ):
        """A declined question never reaches generation, and the absence of the span is
        the signal — a span emitted for every registered node would make 'which stages
        ran' unanswerable."""
        await _run_stages(nodes, monkeypatch)

        names = {s.name for s in captured_spans.get_finished_spans()}
        assert "chat.generation" not in names

    async def test_the_stage_duration_metric_is_recorded_alongside_the_span(
        self, nodes, monkeypatch, captured_spans
    ):
        from prometheus_client import REGISTRY

        def _observations(stage):
            value = REGISTRY.get_sample_value(
                "ner_chat_stage_duration_seconds_count", {"stage": stage}
            )
            return float(value or 0.0)

        before = _observations("guardrail")
        await _run_stages(nodes, monkeypatch)

        assert _observations("guardrail") == before + 1, (
            "the span answers 'what happened in this request'; the histogram answers "
            "'what happens in general' — a P95 needs the second"
        )

    def test_every_node_name_is_a_declared_stage_value(self):
        """A node added later without widening the enumeration lands on `other`, which is
        a silent loss of a dashboard series — so the two are pinned together here."""
        registered = set(build_nodes(_orchestrator()).keys())

        assert registered <= dm.CHAT_STAGES, (
            f"undeclared stages: {sorted(registered - dm.CHAT_STAGES)}"
        )


class TestTheStageLayerDoesNotDuplicateTheServiceLayer:
    """Design Decision 3. The node wrapper is deliberately thin: the interior detail —
    the attempt loop, the fallback branch, the classifier exception — is measured in the
    service functions, because the node layer cannot see any of it."""

    def test_the_node_wrapper_records_only_an_outcome_and_a_duration(self):
        import inspect

        from src.chat_api.graph import nodes as nodes_module

        source = inspect.getsource(nodes_module._traced)

        assert "record_chat_stage" in source
        assert "_node_outcome" in source
        assert "record_sql_attempt" not in source
        assert "record_retrieval" not in source

    def test_the_node_outcome_is_derived_from_fields_the_node_already_sets(self):
        from src.chat_api.graph.nodes import _node_outcome

        assert _node_outcome("guardrail", {"blocked_reason": "pii"}) == "blocked"
        assert _node_outcome("guardrail", {"blocked_reason": None}) == "admitted"
        assert _node_outcome("entity_resolution", {"entity_resolution_outcome": "unique"}) == "unique"
        assert _node_outcome("source_assembly", {"sources": []}) == "empty"
        assert _node_outcome("a_node_added_later", {"anything": 1}) == "completed"
