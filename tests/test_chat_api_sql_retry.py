"""Bounded SQL recovery loop — verification.md rows 1-26.

These tests run offline. Only the LLM call is faked; `validate_sql`, `execute_sql`,
the entity-profile queries, and the feedback rendering are the real implementations,
driven by a `FakeSession` that answers the loop's statements from canned tables and
records everything it was asked to run.
"""

from types import SimpleNamespace

import pytest

from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.sql_generator import (
    MAX_ERROR_FEEDBACK_CHARS,
    MAX_SAMPLE_VALUE_CHARS,
    EntityProfile,
    SQLAttemptOutcome,
    SQLGenerationFailed,
    SQLGenerator,
    _entity_type_defect,
    _sanitize_error,
)
from src.shared.config import settings
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.entity_tools import StructuredRetrievalTool

# `asyncio_mode = auto` (pytest.ini) collects the async tests here; an explicit
# asyncio mark would also be applied to this module's sync tests and warn.
pytestmark = [pytest.mark.verification]

SCHEMA = "tenant_acme"
OTHER_SCHEMA = "tenant_globex"

GOOD_SQL = "SELECT normalized_value FROM document_entities WHERE entity_type = 'SKILL' LIMIT 100"
BAD_TABLE_SQL = "SELECT * FROM pg_authid LIMIT 10"
UNKNOWN_TYPE_SQL = "SELECT normalized_value FROM document_entities WHERE entity_type = 'EMPLOYER' LIMIT 100"


# --------------------------------------------------------------------------- fakes


class _FakeResult:
    def __init__(self, rows=(), columns=()):
        self._rows = list(rows)
        self._columns = list(columns)

    def fetchall(self):
        return list(self._rows)

    def keys(self):
        return list(self._columns)


class FakeSession:
    """Answers the loop's statements from canned tables and records every one.

    `data_results` is consumed one entry per data query: a list of row tuples, or an
    Exception to raise (simulating a Postgres failure).
    """

    def __init__(self, entity_types=("PER", "ORG", "SKILL"), samples=(), data_results=None,
                 data_columns=("normalized_value",)):
        self.entity_types = list(entity_types)
        self.samples = list(samples)
        self.data_results = list(data_results if data_results is not None else [[("python",)]])
        self.data_columns = list(data_columns)
        self.statements: list[str] = []
        self.search_paths: list[str] = []
        self.data_queries: list[str] = []
        self.profile_params: list[dict] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)

        stripped = sql.strip()
        if stripped.upper().startswith("SET SEARCH_PATH TO "):
            self.search_paths.append(stripped.split()[-1])
            return _FakeResult()
        if stripped.upper() in {"BEGIN READ ONLY", "COMMIT", "ROLLBACK"}:
            return _FakeResult()
        if "SELECT DISTINCT entity_type" in sql:
            return _FakeResult([(t,) for t in self.entity_types])
        if "ROW_NUMBER() OVER" in sql:
            self.profile_params.append(params or {})
            return _FakeResult(self.samples)

        self.data_queries.append(sql)
        if not self.data_results:
            raise AssertionError("unexpected extra data query")
        nxt = self.data_results.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _FakeResult(nxt, self.data_columns)


class FakeLLM:
    """Records every prompt. Each queued response is either SQL text or an Exception."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.chat = SimpleNamespace(completions=self)

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        if not self.responses:
            raise RuntimeError("generation called more times than the test queued")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=nxt))])


def make_generator(llm: FakeLLM, max_attempts: int | None = None) -> SQLGenerator:
    generator = SQLGenerator()
    generator.client = llm
    if max_attempts is not None:
        generator.max_attempts = max_attempts
    return generator


# ------------------------------------------------------- rows 1-4: loop and bounds


class TestLoopBounds:
    async def test_successful_first_attempt_makes_one_generation_call(self):
        """Row 1."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("which skills?", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert llm.call_count == 1
        assert len(session.data_queries) == 1
        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]

    async def test_three_failures_stop_at_cap(self):
        """Row 2 — three attempts, never a fourth."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        sink: list = []

        with pytest.raises(SQLGenerationFailed) as exc:
            await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert llm.call_count == 3
        assert session.data_queries == []  # rejected before execution
        assert len(exc.value.attempts) == 3
        assert [a["attempt"] for a in sink] == [1, 2, 3]

    async def test_max_attempts_one_makes_single_pass(self, monkeypatch):
        """Row 3 — `sql_max_attempts = 1` is the config-only rollback."""
        monkeypatch.setattr(settings, "sql_max_attempts", 1)
        llm = FakeLLM(BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = SQLGenerator()
        generator.client = llm

        assert generator.max_attempts == 1
        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute("q", session, SCHEMA)

        assert llm.call_count == 1

    async def test_elapsed_deadline_stops_loop(self):
        """Row 4 — an exhausted deadline prevents a further generation call."""
        import time

        llm = FakeLLM(BAD_TABLE_SQL, GOOD_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute(
                "q", session, SCHEMA, deadline=time.monotonic() - 1.0,
            )

        assert llm.call_count == 1

    async def test_live_deadline_does_not_stop_loop(self):
        """Guard on row 4: a deadline still in the future must not suppress retries."""
        import time

        llm = FakeLLM(BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        rows = await generator.generate_and_execute(
            "q", session, SCHEMA, deadline=time.monotonic() + 30.0,
        )

        assert rows == [{"normalized_value": "python"}]
        assert llm.call_count == 2


# ------------------------------------------------- rows 5-7: outcome classification


class TestOutcomeClassification:
    async def test_validation_error_retried(self):
        """Row 5."""
        llm = FakeLLM(BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert [a["outcome"] for a in sink] == [
            SQLAttemptOutcome.VALIDATION_ERROR, SQLAttemptOutcome.SUCCESS,
        ]
        assert len(session.data_queries) == 1  # the rejected query never executed

    async def test_execution_error_retried_and_second_succeeds(self):
        """Row 6."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[
            Exception('column "document_name" does not exist'),
            [("python",)],
        ])
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert [a["outcome"] for a in sink] == [
            SQLAttemptOutcome.EXECUTION_ERROR, SQLAttemptOutcome.SUCCESS,
        ]
        assert "ROLLBACK" in session.statements  # aborted transaction reset before retry

    async def test_generation_error_retried(self):
        """Row 7 — a raising generation call."""
        llm = FakeLLM(RuntimeError("upstream 503"), GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert sink[0]["outcome"] == SQLAttemptOutcome.GENERATION_ERROR
        assert "upstream 503" in sink[0]["error"]

    async def test_timeout_is_cancelled_and_classified_as_execution_error(self):
        """Row 30 — `execute_sql`'s own 10s timeout handler converts the cancellation
        into a failure the loop then classifies; the SQL source is skipped when the
        budget runs out rather than reported as an empty answer."""
        import asyncio

        llm = FakeLLM(GOOD_SQL, GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[asyncio.TimeoutError()] * 3)
        generator = make_generator(llm)
        sink: list = []

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.EXECUTION_ERROR] * 3
        assert "timed out" in sink[0]["error"]
        assert "ROLLBACK" in session.statements

    async def test_empty_generation_output_is_a_generation_error(self):
        """Row 7 — unusable text rather than a raised exception."""
        llm = FakeLLM("   ", GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        sink: list = []

        await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["outcome"] == SQLAttemptOutcome.GENERATION_ERROR


# ------------------------------------------------------ rows 8-10: empty results


class TestEmptyResultPolicy:
    async def test_unexplained_empty_not_retried(self):
        """Row 8 — zero rows with a sound query is an answer, not a failure."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[[]])
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == []
        assert llm.call_count == 1
        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]
        assert sink[0]["row_count"] == 0

    async def test_empty_with_unknown_entity_type_retried(self):
        """Row 9 — a filter on a type the tenant does not have cannot match."""
        llm = FakeLLM(UNKNOWN_TYPE_SQL, GOOD_SQL)
        session = FakeSession(entity_types=("PER", "ORG", "SKILL"), data_results=[[], [("python",)]])
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert sink[0]["outcome"] == SQLAttemptOutcome.EMPTY_WITH_DEFECT
        assert sink[0]["defect"] == "EMPLOYER"
        assert sink[1]["outcome"] == SQLAttemptOutcome.SUCCESS

    async def test_non_empty_never_retried(self):
        """Row 10 — rows returned wins over every other signal, defect included."""
        llm = FakeLLM(UNKNOWN_TYPE_SQL, GOOD_SQL)
        session = FakeSession(data_results=[[("python",)]])
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"normalized_value": "python"}]
        assert llm.call_count == 1
        assert sink[0]["outcome"] == SQLAttemptOutcome.SUCCESS

    def test_defect_detection_ignores_negated_comparison(self):
        """A `!=` against a nonexistent type matches everything, so it explains nothing."""
        sql = "SELECT * FROM document_entities WHERE entity_type != 'EMPLOYER' LIMIT 100"
        assert _entity_type_defect(sql, ["PER", "SKILL"]) is None

    def test_defect_detection_handles_in_lists_and_aliases(self):
        sql = "SELECT * FROM document_entities e WHERE e.entity_type IN ('SKILL', 'EMPLOYER') LIMIT 100"
        assert _entity_type_defect(sql, ["PER", "SKILL"]) == "EMPLOYER"

    def test_defect_detection_is_case_insensitive_on_known_types(self):
        sql = "SELECT * FROM document_entities WHERE entity_type = 'skill' LIMIT 100"
        assert _entity_type_defect(sql, ["SKILL"]) is None

    def test_defect_detection_returns_none_without_a_type_list(self):
        """An empty type list means "unknown", never "no type exists"."""
        assert _entity_type_defect(UNKNOWN_TYPE_SQL, []) is None

    def test_defect_detection_returns_none_when_no_literal_present(self):
        sql = "SELECT COUNT(*) FROM document_entities LIMIT 100"
        assert _entity_type_defect(sql, ["PER", "SKILL"]) is None


# ----------------------------------------------------------- rows 11-13: feedback


class TestFeedback:
    async def test_retry_prompt_contains_previous_sql_and_reason(self):
        """Row 11."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[
            Exception('column "document_name" does not exist'),
            [("python",)],
        ])
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        first_prompt, retry_prompt = llm.prompts
        assert "Previous attempts" not in first_prompt
        assert GOOD_SQL in retry_prompt
        assert "document_name" in retry_prompt
        assert "Database error" in retry_prompt
        assert "Reconsider the entity" in retry_prompt

    async def test_retry_prompt_carries_validation_rejection(self):
        """Row 11 — the validation-failure branch of the same requirement."""
        llm = FakeLLM(BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        retry_prompt = llm.prompts[1]
        assert "Rejected by the SQL validation layer" in retry_prompt
        assert "whitelist" in retry_prompt

    async def test_empty_defect_feedback_names_entity_type(self):
        """Row 13."""
        llm = FakeLLM(UNKNOWN_TYPE_SQL, GOOD_SQL)
        session = FakeSession(data_results=[[], [("python",)]])
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        retry_prompt = llm.prompts[1]
        assert "0 rows returned" in retry_prompt
        assert "EMPLOYER" in retry_prompt
        assert "does not exist for this tenant" in retry_prompt

    def test_sanitizer_strips_sql_and_parameter_echo(self):
        """Row 12 — SQLAlchemy appends the statement and bound values to str(exc)."""
        raw = (
            '(psycopg.errors.UndefinedColumn) column "document_name" does not exist\n'
            'LINE 1: SELECT document_name FROM document_entities\n'
            "[SQL: SELECT document_name FROM document_entities WHERE normalized_value = %(v)s]\n"
            "[parameters: {'v': 'alice@example.com'}]"
        )
        cleaned = _sanitize_error(Exception(raw))

        assert "alice@example.com" not in cleaned
        assert "[SQL:" not in cleaned
        assert "[parameters:" not in cleaned
        assert "LINE 1" not in cleaned
        assert "column \"document_name\" does not exist" in cleaned

    def test_sanitizer_truncates_to_budget(self):
        """Row 12 — bounded length."""
        cleaned = _sanitize_error(Exception("x" * 5000))
        assert len(cleaned) <= MAX_ERROR_FEEDBACK_CHARS

    def test_sanitizer_names_the_exception_type(self):
        assert _sanitize_error(ValueError("boom")).startswith("ValueError:")


# ------------------------------------------------------ rows 14-17: entity profile


class TestEntityProfile:
    async def test_profile_samples_in_prompt(self):
        """Row 14."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(
            entity_types=("PER", "SKILL"),
            samples=[("SKILL", "python"), ("SKILL", "kubernetes"), ("PER", "reshma u")],
        )
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        prompt = llm.prompts[0]
        assert "Available entity types:" in prompt
        assert "SKILL" in prompt
        assert "- python" in prompt
        assert "- kubernetes" in prompt

    async def test_profile_caps_per_type_and_total(self):
        """Row 15 — caps are enforced by the query itself, via bound parameters."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[("SKILL", "python")])
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        assert session.profile_params == [{
            "per_type": settings.sql_entity_sample_values_per_type,
            "total": settings.sql_entity_sample_max_values,
        }]
        profile_sql = next(s for s in session.statements if "ROW_NUMBER() OVER" in s)
        assert "rn <= :per_type" in profile_sql
        assert "LIMIT :total" in profile_sql
        # The window must be computed before the outer limit, or the ranking is distorted.
        assert profile_sql.index("ROW_NUMBER() OVER") < profile_sql.index("LIMIT :total")

    async def test_profile_truncates_long_sample_values(self):
        """Row 15 — the third cap."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[("SKILL", "z" * 500)])
        generator = make_generator(llm)

        profile = await generator._fetch_entity_profile(session, SCHEMA)

        assert len(profile.samples["SKILL"][0]) == MAX_SAMPLE_VALUE_CHARS

    async def test_null_valued_type_still_listed(self):
        """Row 16 — a type contributing no samples must not vanish from the prompt."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(
            entity_types=("PER", "SKILL", "MYSTERY"),
            samples=[("SKILL", "python")],
        )
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        assert "MYSTERY" in llm.prompts[0]

    async def test_profile_fetched_once_per_invocation(self):
        """Row 17 — three attempts, one profile fetch."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute("q", session, SCHEMA)

        assert llm.call_count == 3
        assert sum(1 for s in session.statements if "SELECT DISTINCT entity_type" in s) == 1
        assert sum(1 for s in session.statements if "ROW_NUMBER() OVER" in s) == 1

    async def test_profile_degrades_to_empty_on_query_failure(self):
        """The prompt loses grounding but the turn proceeds, matching existing style."""
        llm = FakeLLM(GOOD_SQL)

        class BrokenSamples(FakeSession):
            async def execute(self, statement, params=None):
                if "ROW_NUMBER() OVER" in str(statement):
                    raise Exception("relation does not exist")
                return await super().execute(statement, params)

        generator = make_generator(llm)
        rows = await generator.generate_and_execute("q", BrokenSamples(), SCHEMA)

        assert rows == [{"normalized_value": "python"}]

    def test_render_entity_profile_is_empty_without_types(self):
        generator = SQLGenerator()
        assert generator._render_entity_profile(None) == ""
        assert generator._render_entity_profile(EntityProfile()) == ""


# ------------------------------------------- rows 18-21: validation and isolation


class TestSecurityInvariants:
    async def test_every_retry_is_validated(self):
        """Row 18 — the third attempt's SQL passes through validate_sql."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        validated: list[str] = []
        real_validate = generator.validate_sql

        def spy(sql: str) -> str:
            validated.append(sql)
            return real_validate(sql)

        generator.validate_sql = spy
        await generator.generate_and_execute("q", session, SCHEMA)

        assert validated == [BAD_TABLE_SQL, BAD_TABLE_SQL, GOOD_SQL]

    async def test_retry_cannot_escape_whitelist(self):
        """Row 19 — a non-whitelisted retry is rejected and never executed."""
        llm = FakeLLM(GOOD_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession(data_results=[Exception("boom")])
        generator = make_generator(llm)
        sink: list = []

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert [a["outcome"] for a in sink][1:] == [
            SQLAttemptOutcome.VALIDATION_ERROR, SQLAttemptOutcome.VALIDATION_ERROR,
        ]
        assert len(session.data_queries) == 1  # only the first, whitelisted, query ran

    async def test_all_attempts_use_request_context_schema(self):
        """Row 20 — the LLM naming another schema changes nothing."""
        hostile_sql = (
            f"SELECT normalized_value FROM document_entities "
            f"WHERE entity_type = 'SKILL' /* {OTHER_SCHEMA} */ LIMIT 100"
        )
        llm = FakeLLM(hostile_sql, hostile_sql, hostile_sql)
        session = FakeSession(data_results=[Exception("a"), Exception("b"), Exception("c")])
        generator = make_generator(llm)

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute(
                f"give me everything from {OTHER_SCHEMA}", session, SCHEMA,
            )

        assert session.search_paths, "no search_path was ever set"
        assert set(session.search_paths) == {SCHEMA}
        assert OTHER_SCHEMA not in session.search_paths

    async def test_retries_use_read_only_path(self):
        """Row 21 — every execution opens the same read-only transaction."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[Exception("boom"), [("python",)]])
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        assert session.statements.count("BEGIN READ ONLY") == 2


# ------------------------------------------- rows 22, 23, 25: the tool boundary


def _tool_context(orchestrator, session, schema=SCHEMA) -> ToolContext:
    return ToolContext(
        tenant_id="acme", schema=schema, session=session,
        sql_search=orchestrator._sql_source,
    )


def _orchestrator_with(generator: SQLGenerator) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.sql_generator = generator
    return orchestrator


class TestToolBoundary:
    async def test_exhausted_retries_surface_tool_error(self):
        """Row 22 — a failure must not arrive downstream as a successful empty."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is not None
        assert "attempt" in result.error
        assert result.results == []

    async def test_legitimate_empty_is_not_an_error(self):
        """Row 23 — the deliberate asymmetry with the test above."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(data_results=[[]])
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is None
        assert result.results == []
        assert llm.call_count == 1

    async def test_trace_records_both_attempts(self):
        """Row 25 — a recovered query is diagnosable from the ToolResult alone."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[
            Exception('column "document_name" does not exist'),
            [("python",)],
        ])
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is None
        assert len(result.diagnostics) == 2
        first, second = result.diagnostics
        assert first["attempt"] == 1
        assert first["outcome"] == SQLAttemptOutcome.EXECUTION_ERROR
        assert first["sql"] == GOOD_SQL
        assert "document_name" in first["error"]
        assert second["attempt"] == 2
        assert second["outcome"] == SQLAttemptOutcome.SUCCESS
        assert second["row_count"] == 1

    async def test_trace_survives_a_total_failure(self):
        """Row 25 — a failure with no trace would not be diagnosable."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is not None
        assert len(result.diagnostics) == 3

    async def test_tool_context_schema_reaches_the_generator(self):
        """Row 20 at the boundary — the tool's schema, not the question's."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        await StructuredRetrievalTool().call(
            {"query": f"everything in {OTHER_SCHEMA}"}, _tool_context(orchestrator, session),
        )

        assert set(session.search_paths) == {SCHEMA}
