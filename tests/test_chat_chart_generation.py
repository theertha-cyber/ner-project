"""Covers verification.md rows 1-4, 8, 13-14, 18-19, 21-23: which turns are offered
the render_chart tool, the two-stage generation path, and when a chart is dropped."""

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.chart_tool import ChartFrame, RENDER_CHART_TOOL_NAME
from src.chat_api.services.guardrails import FALLBACK_REPLY, INCOMPLETE_RETRIEVAL_REPLY
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.tools import build_default_registry

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

ROWS = [
    {"quarter": "Q1", "amount": 120000},
    {"quarter": "Q2", "amount": 95000},
    {"quarter": "Q3", "amount": 143000},
    {"quarter": "Q4", "amount": 160000},
]
CHART_ARGS = {
    "chart_type": "bar",
    "title": "Billed per quarter",
    "categories": ["Q1", "Q2", "Q3", "Q4"],
    "series": [{"name": "amount", "data": [120000, 95000, 143000, 160000]}],
}


def _tool_call(arguments=None, name=RENDER_CHART_TOOL_NAME):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments or CHART_ARGS)),
    )


def _text(content, tool_calls=None):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        model_dump=lambda **_kw: {"role": "assistant", "content": content},
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ScriptedLLMClient:
    """Returns each scripted response in turn and records every call kwargs, so a test
    can assert both what was offered to the model and how often it was asked."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._responses.pop(0) if self._responses else _text("reply")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def tool_offering_calls(self):
        return [c for c in self.calls if "tools" in c]


class NoopGuardrails:
    def enforce_sources(self, reply, sources, retrieval_status=None):
        return reply, sources


class ReplacingGuardrails:
    def __init__(self, replacement):
        self._replacement = replacement

    def enforce_sources(self, reply, sources, retrieval_status=None):
        return self._replacement, []


def _generation_node(llm_client, guardrails=None):
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = None
    orchestrator.llm_client = llm_client
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = guardrails or NoopGuardrails()
    orchestrator.tool_registry = build_default_registry()
    return build_nodes(orchestrator)["generation"]


def _state(**overrides):
    state = {
        "prompt_messages": [{"role": "user", "content": "how much did we bill per quarter?"}],
        "sources": [SimpleNamespace(model_dump=lambda: {"source_type": "sql"})],
        "sql_results": list(ROWS),
    }
    state.update(overrides)
    return state


class TestEligibilityGating:
    async def test_1_turn_with_structured_rows_is_offered_the_tool(self):
        """Row 1."""
        client = ScriptedLLMClient(_text("no chart"), _text("reply"))
        await _generation_node(client)(_state())

        assert len(client.tool_offering_calls) == 1
        offered = client.tool_offering_calls[0]["tools"]
        assert [t["function"]["name"] for t in offered] == [RENDER_CHART_TOOL_NAME]
        assert client.tool_offering_calls[0]["tool_choice"] == "auto"

    async def test_2_turn_without_structured_rows_is_never_offered_the_tool(self):
        """Row 2: document-only turn makes exactly one call and carries no chart."""
        client = ScriptedLLMClient(_text("reply"))
        result = await _generation_node(client)(_state(sql_results=None))

        assert client.tool_offering_calls == []
        assert len(client.calls) == 1
        assert result["chart"] is None

    async def test_3_clarification_turn_is_never_offered_the_tool(self):
        """Row 3."""
        client = ScriptedLLMClient(_text("reply"))
        result = await _generation_node(client)(
            _state(pending_clarification={"candidates": ["a", "b"]})
        )

        assert client.tool_offering_calls == []
        assert result["chart"] is None

    async def test_empty_row_set_is_not_eligible(self):
        client = ScriptedLLMClient(_text("reply"))
        await _generation_node(client)(_state(sql_results=[]))
        assert client.tool_offering_calls == []


class TestTwoStageGeneration:
    async def test_8_and_18_decline_leaves_the_reply_path_unchanged(self):
        """Rows 8 and 18: when the model declines, stage B is the call it always was."""
        declining = ScriptedLLMClient(_text("no chart"), _text("the answer"))
        charted_result = await _generation_node(declining)(_state())

        single_stage = ScriptedLLMClient(_text("the answer"))
        baseline = await _generation_node(single_stage)(_state(sql_results=None))

        assert charted_result["reply"] == baseline["reply"] == "the answer"
        assert charted_result["chart"] is None
        stage_b = declining.calls[-1]
        baseline_call = single_stage.calls[-1]
        assert stage_b["messages"] == baseline_call["messages"]
        assert stage_b["temperature"] == baseline_call["temperature"]
        assert stage_b["max_tokens"] == baseline_call["max_tokens"]
        assert "tools" not in stage_b

    async def test_19_charted_turn_passes_the_tool_exchange_to_stage_b(self):
        """Row 19."""
        client = ScriptedLLMClient(
            _text(None, tool_calls=[_tool_call()]),
            _text("Here is how billing moved across the quarters."),
        )
        result = await _generation_node(client)(_state())

        stage_b_messages = client.calls[-1]["messages"]
        assert stage_b_messages[-1]["role"] == "tool"
        assert stage_b_messages[-1]["tool_call_id"] == "call_1"
        assert stage_b_messages[-2]["role"] == "assistant"
        assert result["chart"]["title"] == "Billed per quarter"
        assert result["reply"] == "Here is how billing moved across the quarters."

    async def test_21_decision_stage_failure_degrades_to_a_text_answer(self, caplog):
        """Row 21."""
        client = ScriptedLLMClient(RuntimeError("upstream 500"), _text("the answer"))
        with caplog.at_level(logging.WARNING):
            result = await _generation_node(client)(_state())

        assert result["reply"] == "the answer"
        assert result["chart"] is None
        assert "chart decision call failed" in caplog.text

    async def test_malformed_tool_call_degrades_to_a_text_answer(self):
        bad = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name=RENDER_CHART_TOOL_NAME, arguments="{not json"),
        )
        client = ScriptedLLMClient(_text(None, tool_calls=[bad]), _text("the answer"))
        result = await _generation_node(client)(_state())

        assert result["reply"] == "the answer"
        assert result["chart"] is None

    async def test_ungrounded_chart_is_dropped_but_the_answer_survives(self):
        invented = dict(CHART_ARGS, series=[{"name": "amount", "data": [1, 2, 3, 999999]}])
        client = ScriptedLLMClient(
            _text(None, tool_calls=[_tool_call(invented)]), _text("the answer")
        )
        result = await _generation_node(client)(_state())

        assert result["chart"] is None
        assert result["reply"] == "the answer"
        assert result["sources"]


class TestChartInState:
    async def test_22_ordinary_turn_carries_no_chart(self):
        """Row 22."""
        client = ScriptedLLMClient(_text("no chart"), _text("reply"))
        assert (await _generation_node(client)(_state()))["chart"] is None

    async def test_23_validated_chart_is_carried(self):
        """Row 23."""
        client = ScriptedLLMClient(_text(None, tool_calls=[_tool_call()]), _text("reply"))
        chart = (await _generation_node(client)(_state()))["chart"]

        assert chart["chart_type"] == "bar"
        assert chart["categories"] == ["Q1", "Q2", "Q3", "Q4"]
        assert chart["series"][0]["data"] == [120000, 95000, 143000, 160000]


class TestSuppressionOnFallback:
    async def test_13_empty_sources_fallback_carries_no_chart(self):
        """Row 13."""
        client = ScriptedLLMClient(_text(None, tool_calls=[_tool_call()]), _text("reply"))
        node = _generation_node(client, guardrails=ReplacingGuardrails(FALLBACK_REPLY))
        result = await node(_state())

        assert result["reply"] == FALLBACK_REPLY
        assert result["chart"] is None

    async def test_14_retrieval_failure_fallback_carries_no_chart(self):
        """Row 14."""
        client = ScriptedLLMClient(_text(None, tool_calls=[_tool_call()]), _text("reply"))
        node = _generation_node(client, guardrails=ReplacingGuardrails(INCOMPLETE_RETRIEVAL_REPLY))
        result = await node(_state())

        assert result["reply"] == INCOMPLETE_RETRIEVAL_REPLY
        assert result["chart"] is None


class StreamingClient(ScriptedLLMClient):
    """Answers the decision call from the script, then streams the narrative."""

    def __init__(self, decision):
        super().__init__()
        self._decision = decision

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if "tools" in kwargs:
            return self._decision

        async def chunks():
            for piece in ("Here ", "is ", "the ", "trend."):
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=piece))]
                )

        return chunks()


async def _drain(sink):
    items = []
    while not sink.empty():
        items.append(sink.get_nowait())
    return items


class TestStreamingSink:
    async def test_chart_reaches_the_sink_before_any_delta(self):
        """The ordering the SSE contract depends on (rows 20, 27)."""
        sink: asyncio.Queue = asyncio.Queue()
        client = StreamingClient(_text(None, tool_calls=[_tool_call()]))
        await _generation_node(client)(_state(token_sink=sink))

        drained = await _drain(sink)
        assert isinstance(drained[0], ChartFrame)
        assert drained[0].payload["title"] == "Billed per quarter"
        assert all(isinstance(item, str) for item in drained[1:])
        assert "".join(drained[1:]) == "Here is the trend."

    async def test_no_chart_frame_when_the_model_declines(self):
        sink: asyncio.Queue = asyncio.Queue()
        client = StreamingClient(_text("no chart"))
        await _generation_node(client)(_state(token_sink=sink))

        drained = await _drain(sink)
        assert not any(isinstance(item, ChartFrame) for item in drained)
