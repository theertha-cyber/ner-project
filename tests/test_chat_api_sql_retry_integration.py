"""Bounded SQL recovery through the retrieval and answer-generation stages —
verification.md rows 24, 26, 27, 28, 31, 32.

Runs offline. The real `execute_plan`, `StructuredRetrievalTool`, `SQLGenerator`,
`GuardrailService`, `ContextAssembler`, and the real `source_assembly` /
`prompt_assembly` / `generation` graph nodes all execute; only the LLM calls and the
database session are faked. `source_assembly` issues no query when its sources carry
no `document_id`, which is the case for a SQL-only turn.
"""

import json
from contextlib import asynccontextmanager

import pytest

from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.guardrails import FALLBACK_REPLY, GuardrailService
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.orchestrator import (
    OUTCOME_EMPTY,
    STRUCTURED_CAPABILITY_NAME,
    OrchestrationBudget,
    PlanEntry,
    RetrievalPlan,
    execute_plan,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext

from tests.test_chat_api_sql_retry import (
    GOOD_SQL,
    SCHEMA,
    FakeLLM,
    FakeSession,
    make_generator,
)

pytestmark = [pytest.mark.verification]

DROP_SQL = "DROP TABLE document_entities"
TENANT_ID = "acme"


class _AnswerLLM:
    """Answer-generation stand-in for `orchestrator.llm_client`."""

    def __init__(self, reply="Alice and Bob know Python."):
        self.reply = reply
        self.messages: list[list[dict]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    async def create(self, **kwargs):
        self.messages.append(kwargs["messages"])
        return type("_R", (), {"choices": [
            type("_C", (), {"message": type("_M", (), {"content": self.reply})()})()
        ]})()


def _orchestrator(generator, answer_llm=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.sql_generator = generator
    orchestrator.guardrails = GuardrailService()
    orchestrator.llm_client = answer_llm or _AnswerLLM()
    orchestrator.llm_model = "fake-model"
    orchestrator.retriever = None
    orchestrator.tool_registry = build_default_registry()
    return orchestrator


async def _run_structured_plan(orchestrator, session, schema=SCHEMA):
    """Executes a structured-only plan through the real orchestrator machinery."""
    @asynccontextmanager
    async def context_factory():
        yield ToolContext(
            tenant_id=TENANT_ID, schema=schema, session=session,
            sql_search=orchestrator._sql_source,
        )

    plan = RetrievalPlan(entries=[
        PlanEntry(capability_name=STRUCTURED_CAPABILITY_NAME, arguments={"query": "who knows python?"}),
    ])
    # No `recovery_query`: these tests exercise the structured path in isolation, and
    # the semantic recovery has no retriever to run against here.
    return await execute_plan(
        plan, orchestrator.tool_registry, context_factory,
        OrchestrationBudget(max_invocations=3, deadline=float("inf")),
    )


async def _answer_from(orchestrator, sql_results):
    """Drives the unchanged source -> prompt -> generation stages."""
    nodes = build_nodes(orchestrator)
    state = {
        "message": "who knows python?", "tenant_id": TENANT_ID, "schema": SCHEMA,
        "session": None, "sql_results": sql_results, "chunks": [],
        "conversation_context": None,
    }
    # Prompt assembly runs first now, and source assembly derives citations from what
    # it admitted (design Decision 7).
    state.update(await nodes["prompt_assembly"](state))
    state.update(await nodes["source_assembly"](state))
    state.update(await nodes["generation"](state))
    return state


class TestFailureReachesTheControlledFallback:
    async def test_exhausted_retries_produce_no_fabricated_answer(self):
        """Row 24 — an honest refusal, not a confident empty answer."""
        llm = FakeLLM(DROP_SQL, DROP_SQL, DROP_SQL)
        session = FakeSession()
        orchestrator = _orchestrator(make_generator(llm), _AnswerLLM("Nobody knows Python."))

        result = await _run_structured_plan(orchestrator, session)
        assert result.status.has_failure()
        assert result.status.failed_capability_names() == [STRUCTURED_CAPABILITY_NAME]
        assert result.sql_results == []

        state = await _answer_from(orchestrator, result.sql_results)
        assert state["reply"] == FALLBACK_REPLY
        assert state["sources"] == []

    async def test_drop_table_is_rejected_retried_and_reported(self):
        """Row 28 — rejected before execution, retried within budget, reported."""
        llm = FakeLLM(DROP_SQL, DROP_SQL, DROP_SQL)
        session = FakeSession()
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)

        assert llm.call_count == 3
        assert session.data_queries == []  # never executed
        assert result.status.has_failure()
        trace = result.plan_trace[0]
        assert trace.error is not None
        assert [d["outcome"] for d in trace.diagnostics] == ["validation_error"] * 3

    async def test_legitimate_empty_reports_empty_not_failed(self):
        """Row 24's counterpart — an empty answer must not look like a failure."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(data_results=[[]])
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)

        assert not result.status.has_failure()
        assert [e.outcome for e in result.status.entries] == [OUTCOME_EMPTY]
        assert result.status.entries[0].error is None
        assert result.sql_results == []


class TestRecoveredQueryReachesAnswerGeneration:
    async def test_recovered_turn_matches_a_first_attempt_success(self):
        """Row 31 — recovery is invisible to the answer stage."""
        recovered = _orchestrator(make_generator(FakeLLM(GOOD_SQL, GOOD_SQL)))
        recovered_session = FakeSession(data_results=[
            Exception('column "document_name" does not exist'), [("python",)],
        ])
        recovered_result = await _run_structured_plan(recovered, recovered_session)
        recovered_state = await _answer_from(recovered, recovered_result.sql_results)

        direct = _orchestrator(make_generator(FakeLLM(GOOD_SQL)))
        direct_result = await _run_structured_plan(direct, FakeSession())
        direct_state = await _answer_from(direct, direct_result.sql_results)

        assert recovered_result.sql_results == direct_result.sql_results
        assert recovered_state["reply"] == direct_state["reply"] != FALLBACK_REPLY
        assert len(recovered_state["sources"]) == len(direct_state["sources"]) == 1
        assert recovered_state["sources"][0].source_type == "sql"
        assert recovered_state["sources"][0].entity_value == direct_state["sources"][0].entity_value
        # The answer model receives the same context either way.
        assert recovered.llm_client.messages[-1] == direct.llm_client.messages[-1]

    async def test_existing_successful_query_still_costs_one_generation_call(self):
        """Row 27 — the happy path is unchanged in shape and in cost."""
        llm = FakeLLM(GOOD_SQL)
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, FakeSession())
        state = await _answer_from(orchestrator, result.sql_results)

        assert llm.call_count == 1
        assert not result.status.has_failure()
        assert state["reply"] != FALLBACK_REPLY
        assert [d["outcome"] for d in result.plan_trace[0].diagnostics] == ["success"]


class TestWrongRelationDefectThroughTheStack:
    async def test_wrong_relation_defect_consumes_retry_budget(self):
        """verification.md row 53 — the defect is retryable, so the loop spends a second
        generation on it instead of terminating as a zero-row success."""
        wrong_relation_sql = (
            "SELECT document_id, value FROM e_skill "
            "WHERE normalized_value = 'oracle' LIMIT 100"
        )
        llm = FakeLLM(wrong_relation_sql, GOOD_SQL)
        session = FakeSession(
            value_types={"oracle": ["EMPLOYER"]},
            data_results=[[], [("python",)]],
        )
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)

        assert llm.call_count == 2
        assert not result.status.has_failure()
        outcomes = [d["outcome"] for d in result.plan_trace[0].diagnostics]
        assert outcomes == ["empty_with_defect", "success"]
        assert "e_employer" in llm.prompts[1]
        assert "entity_type" not in llm.prompts[1]

    async def test_attempt_trace_reaches_retrieval_status(self):
        """verification.md row 61 — a failed structured invocation carries its
        per-attempt outcomes on the turn's status, not only in the plan trace."""
        llm = FakeLLM(DROP_SQL, DROP_SQL, DROP_SQL)
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, FakeSession())

        entry = result.status.entries_for(STRUCTURED_CAPABILITY_NAME)[0]
        assert entry.outcome == "failed"
        assert [d["outcome"] for d in entry.diagnostics] == ["validation_error"] * 3
        assert entry.error


class TestDiagnosticsStayInternal:
    async def test_response_payload_carries_no_sql_or_diagnostics(self):
        """Row 26 — the trace is internal state, never part of the answer."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[Exception("boom"), [("python",)]])
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)
        state = await _answer_from(orchestrator, result.sql_results)

        # The trace exists internally...
        assert len(result.plan_trace[0].diagnostics) == 2
        # ...and none of it reaches what the caller is handed.
        payload = json.dumps(
            {"reply": state["reply"], "sources": [s.model_dump() for s in state["sources"]]},
            default=str,
        )
        assert GOOD_SQL not in payload
        assert "SELECT" not in payload
        for key in ("outcome", "attempt", "max_attempts", "diagnostics"):
            assert key not in payload

    async def test_grounding_queries_use_the_tool_context_schema(self):
        """Row 32 — bounded sampling stays inside the authenticated tenant."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[("SKILL", "python")])
        orchestrator = _orchestrator(make_generator(llm))

        await _run_structured_plan(orchestrator, session, schema=SCHEMA)

        sample_index = next(
            i for i, s in enumerate(session.statements) if "ROW_NUMBER() OVER" in s
        )
        preceding_search_path = [
            s for s in session.statements[:sample_index]
            if s.strip().upper().startswith("SET SEARCH_PATH TO ")
        ][-1]
        assert preceding_search_path.strip().split()[-1] == SCHEMA
        assert set(session.search_paths) == {SCHEMA}
        assert "value in the data: python" in llm.prompts[0]


class TestRelationalSurfaceEndToEnd:
    """verification.md rows 35, 37, 39 — the relational statement takes the same read-only,
    validated, time-bounded path the EAV statement took, and every way it can fail still
    reports the structured source as unavailable rather than as an empty answer."""

    async def test_valid_relational_select_reaches_answer_generation(self):
        """Row 35 — one generation call, executed read-only, cited in the answer."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(data_results=[[("python",)]])
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)

        assert not result.status.has_failure()
        assert result.sql_results == [{"value": "python"}]
        assert session.statements.count("BEGIN READ ONLY") == 1
        assert "COMMIT" in session.statements

        state = await _answer_from(orchestrator, result.sql_results)
        assert state["reply"] != FALLBACK_REPLY

    async def test_relation_outside_the_surface_is_rejected(self):
        """Row 37 — another tenant's relation, or one no definition claims, is refused by
        the validation layer before the database is asked."""
        off_surface = "SELECT document_id, value FROM e_contract LIMIT 100"
        llm = FakeLLM(off_surface, off_surface, off_surface)
        session = FakeSession()
        orchestrator = _orchestrator(make_generator(llm))

        result = await _run_structured_plan(orchestrator, session)

        assert session.data_queries == []
        assert result.status.has_failure()
        assert [d["outcome"] for d in result.plan_trace[0].diagnostics] == [
            "validation_error"
        ] * 3

    async def test_timeout_cancels_and_the_source_is_skipped(self):
        """Row 39 — the 10s bound is unchanged, and an exhausted budget skips the source
        instead of reporting that nothing was found."""
        import asyncio

        llm = FakeLLM(GOOD_SQL, GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[asyncio.TimeoutError()] * 3)
        orchestrator = _orchestrator(make_generator(llm), _AnswerLLM("Alice knows Python."))

        result = await _run_structured_plan(orchestrator, session)

        assert result.status.has_failure()
        assert result.sql_results == []
        assert "ROLLBACK" in session.statements

        state = await _answer_from(orchestrator, result.sql_results)
        assert state["reply"] == FALLBACK_REPLY

    async def test_unprojected_tenant_reports_the_source_unavailable(self):
        """Rows 31, 32 end-to-end: the coverage probe's failure is a failed capability, and
        the turn falls back rather than asserting that no records exist."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=True, data_results=[])
        orchestrator = _orchestrator(make_generator(llm), _AnswerLLM("Nobody knows Python."))

        result = await _run_structured_plan(orchestrator, session)

        assert result.status.has_failure()
        assert result.status.failed_capability_names() == [STRUCTURED_CAPABILITY_NAME]
        assert session.data_queries == []

        state = await _answer_from(orchestrator, result.sql_results)
        assert state["reply"] == FALLBACK_REPLY
