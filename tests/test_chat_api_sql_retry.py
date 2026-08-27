"""Bounded SQL recovery loop over the relational surface — verification.md rows 1-15,
26-33, 47-65.

These tests run offline. Only the LLM call is faked; `validate_sql`, `execute_sql`, the surface
resolution, the grounding queries, the coverage probe and the feedback rendering are the real
implementations, driven by a `FakeSession` that answers the loop's statements from canned tables
and records everything it was asked to run.
"""

from types import SimpleNamespace

import pytest

from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.sql_generator import (
    MAX_ERROR_FEEDBACK_CHARS,
    MAX_SAMPLE_VALUE_CHARS,
    SQLAttemptOutcome,
    SQLGenerationFailed,
    SQLGenerator,
    SurfaceGrounding,
    _sanitize_error,
    relation_by_entity_type,
)
from src.shared.config import settings
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.entity_tools import StructuredRetrievalTool

# `asyncio_mode = auto` (pytest.ini) collects the async tests here; an explicit
# asyncio mark would also be applied to this module's sync tests and warn.
pytestmark = [pytest.mark.verification]

SCHEMA = "tenant_acme"
OTHER_SCHEMA = "tenant_globex"

GOOD_SQL = "SELECT document_id, value FROM e_skill LIMIT 100"
BAD_TABLE_SQL = "SELECT * FROM pg_authid LIMIT 10"
OFF_SURFACE_SQL = "SELECT document_id, value FROM e_unknown LIMIT 100"
BAD_COLUMN_SQL = "SELECT s.salary FROM subject s LIMIT 100"
WRONG_RELATION_SQL = (
    "SELECT document_id, value FROM e_skill WHERE normalized_value = 'oracle' LIMIT 100"
)


def definition_row(name, identifier, tenant_id="acme", **kwargs):
    """A `public.entity_definitions` row as the resolver reads it — by column name."""
    return SimpleNamespace(
        tenant_id=tenant_id,
        name=name,
        sql_identifier=identifier,
        cardinality=kwargs.get("cardinality", "multi"),
        value_kind=kwargs.get("value_kind"),
        value_unit=kwargs.get("value_unit"),
        description=kwargs.get("description"),
        examples=kwargs.get("examples"),
        is_active=kwargs.get("is_active", True),
        base_label_mapping=kwargs.get("base_label_mapping"),
    )


# The tenant every test here queries unless it says otherwise: one multi-valued definition, one
# single-valued one, and one more multi to route a misfiled value to.
DEFINITIONS = (
    definition_row("Skill", "e_skill", description="a technology or professional capability"),
    definition_row("Employer", "e_employer"),
    definition_row("Email", "e_email", cardinality="single"),
)

SURFACE = build_query_surface([
    EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
    EntityDefinitionSpec(name="Employer", sql_identifier="e_employer"),
    EntityDefinitionSpec(name="Email", sql_identifier="e_email", cardinality="single"),
])


# --------------------------------------------------------------------------- fakes


class _FakeResult:
    def __init__(self, rows=(), columns=()):
        self._rows = list(rows)
        self._columns = list(columns)

    def fetchall(self):
        return list(self._rows)

    def keys(self):
        return list(self._columns)

    def first(self):
        return self._rows[0] if self._rows else None


class _CountResult:
    def __init__(self, total):
        self._total = total

    def first(self):
        return None if self._total is None else (self._total,)


class FakeSession:
    """Answers the loop's statements from canned tables and records every one.

    `data_results` is consumed one entry per data query: a list of row tuples, or an
    Exception to raise (simulating a Postgres failure).
    """

    def __init__(self, samples=(), data_results=None,
                 data_columns=("value",), value_types=None, matched_total=None,
                 entity_definitions=DEFINITIONS, filenames=(),
                 projected=True, extracted=True, subject_exists=True):
        # Rows as `public.entity_definitions` returns them, for the query-surface resolver.
        self.entity_definitions = list(entity_definitions)
        self.definition_queries: list[str] = []
        self.samples = list(samples)
        self.data_results = list(data_results if data_results is not None else [[("python",)]])
        self.data_columns = list(data_columns)
        # normalized_value -> the entity types it actually occurs under, for the
        # wrong-relation defect probe.
        self.value_types = dict(value_types or {})
        # Filenames the tenant's documents carry, for the filename defect probe.
        self.filenames = list(filenames)
        # What the coverage probe reports: whether the relational surface and the EAV store
        # hold rows for the question's extent.
        self.projected = projected
        self.extracted = extracted
        # Whether `subject` is in `pg_tables` at all. A tenant that has not extracted since the
        # projection shipped has no generated tables, not empty ones.
        self.subject_exists = subject_exists
        # What COUNT(*) over the unlimited statement returns, when asked.
        self.matched_total = matched_total
        self.statements: list[str] = []
        self.search_paths: list[str] = []
        self.data_queries: list[str] = []
        self.sample_params: list[dict] = []
        self.value_type_probes: list[str] = []
        self.count_queries: list[str] = []
        self.coverage_queries: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)

        stripped = sql.strip()
        if stripped.upper().startswith("SET SEARCH_PATH TO "):
            self.search_paths.append(stripped.split()[-1])
            return _FakeResult()
        if stripped.upper() in {"BEGIN READ ONLY", "COMMIT", "ROLLBACK"}:
            return _FakeResult()
        if "FROM pg_tables" in sql:
            return _FakeResult([(1,)] if self.subject_exists else [])
        if "AS projected" in sql:
            self.coverage_queries.append(sql)
            # `false AS projected` is what the probe renders when the table is absent.
            projected = self.projected and self.subject_exists
            return _FakeResult([(projected, self.extracted)])
        if "normalized_value = :value" in sql:
            value = (params or {}).get("value")
            self.value_type_probes.append(value)
            return _FakeResult([(t,) for t in self.value_types.get(value, [])])
        if "FROM documents WHERE filename ILIKE" in sql:
            pattern = (params or {}).get("pattern", "").strip("%").lower()
            hits = [(1,) for f in self.filenames if pattern in f.lower()]
            return _FakeResult(hits[:1])
        if "FROM public.entity_definitions" in sql:
            # The query surface: the prompt's relations, `validate_sql`'s per-tenant whitelist
            # and the execution role's grants all resolve from this one query. A tenant with no
            # definitions still has `subject`, which is what an empty result yields.
            self.definition_queries.append(sql)
            return _FakeResult(self.entity_definitions)
        if "ROW_NUMBER() OVER" in sql:
            self.sample_params.append(params or {})
            return _FakeResult(self.samples)
        if sql.strip().upper().startswith("SELECT COUNT(*) FROM ("):
            self.count_queries.append(sql)
            return _CountResult(self.matched_total)

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

        assert rows == [{"value": "python"}]
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

        assert rows == [{"value": "python"}]
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

        assert rows == [{"value": "python"}]
        assert [a["outcome"] for a in sink] == [
            SQLAttemptOutcome.VALIDATION_ERROR, SQLAttemptOutcome.SUCCESS,
        ]
        assert len(session.data_queries) == 1  # the rejected query never executed

    async def test_relation_off_the_surface_is_a_validation_error(self):
        """Row 26 — the relation check now covers the class `entity_type` detection used to."""
        llm = FakeLLM(OFF_SURFACE_SQL, GOOD_SQL)
        session = FakeSession()
        sink: list = []

        rows = await make_generator(llm).generate_and_execute(
            "q", session, SCHEMA, attempt_sink=sink,
        )

        assert rows == [{"value": "python"}]
        assert sink[0]["outcome"] == SQLAttemptOutcome.VALIDATION_ERROR
        assert "e_unknown" in sink[0]["error"]
        assert len(session.data_queries) == 1

    async def test_undeclared_column_is_a_validation_error(self):
        """Row 48 — caught before execution, so the retry gets a usable reason."""
        llm = FakeLLM(BAD_COLUMN_SQL, GOOD_SQL)
        session = FakeSession()
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["outcome"] == SQLAttemptOutcome.VALIDATION_ERROR
        assert "salary" in sink[0]["error"]

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

        assert rows == [{"value": "python"}]
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

        assert rows == [{"value": "python"}]
        assert sink[0]["outcome"] == SQLAttemptOutcome.GENERATION_ERROR
        assert "upstream 503" in sink[0]["error"]

    async def test_timeout_is_cancelled_and_classified_as_execution_error(self):
        """Row 39 — `execute_sql`'s own 10s timeout handler converts the cancellation
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


# ------------------------------------------- wrong-relation defect (rows 27, 52, 53, 58)


class TestWrongRelationDefect:
    """Both the relation and the value are real, and the query still cannot match, because
    the extractor filed that value elsewhere. The most common way a well-formed query comes
    back empty on this data — and the reason the retry budget is funded."""

    async def test_value_held_by_another_relation_is_a_defect(self):
        """Row 27."""
        llm = FakeLLM(WRONG_RELATION_SQL, GOOD_SQL)
        session = FakeSession(
            value_types={"oracle": ["EMPLOYER"]},
            data_results=[[], [("python",)]],
        )
        sink: list = []

        rows = await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["outcome"] == SQLAttemptOutcome.EMPTY_WITH_DEFECT
        assert sink[0]["defect"] == "wrong_relation:oracle|e_employer"
        assert rows == [{"value": "python"}]

    async def test_defect_feedback_names_the_relation_and_never_entity_type(self):
        """Rows 52, 58 — the feedback has to name the relation that would work, and must not
        send the model back to a query model the prompt no longer teaches."""
        from src.chat_api.services.sql_generator import SQLAttempt, _render_attempt_feedback

        feedback = _render_attempt_feedback([
            SQLAttempt(
                attempt=1, max_attempts=3, outcome=SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                sql=WRONG_RELATION_SQL, row_count=0,
                defect="wrong_relation:oracle|e_employer",
            )
        ], SURFACE)

        assert "'oracle' does exist" in feedback
        assert "e_employer" in feedback
        assert WRONG_RELATION_SQL in feedback
        assert "entity_type" not in feedback

    async def test_value_in_a_subject_column_is_named_with_its_column(self):
        """A `single` definition's values live in a `subject` column, and naming the table
        alone would send the retry to a relation with no such value in it."""
        llm = FakeLLM(WRONG_RELATION_SQL, GOOD_SQL)
        session = FakeSession(
            value_types={"oracle": ["EMAIL"]},
            data_results=[[], [("python",)]],
        )
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["defect"] == "wrong_relation:oracle|subject.email"

    async def test_absent_value_zero_rows_is_success(self):
        """Row 53 — a value that occurs nowhere at all is genuinely absent. That is a real
        answer and must not consume a retry."""
        llm = FakeLLM(WRONG_RELATION_SQL, GOOD_SQL)
        session = FakeSession(value_types={}, data_results=[[]])
        sink: list = []

        rows = await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == []
        assert llm.call_count == 1
        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]

    async def test_unresolved_surface_does_not_produce_defect(self):
        """An unresolved surface is "we don't know", which is not evidence of a defect any
        more than it is evidence of absence. The probe has no relation to route a value to,
        so it asks the oracle nothing and reports nothing."""
        generator = SQLGenerator()
        session = FakeSession(value_types={"oracle": ["EMPLOYER"]})

        defect = await generator._wrong_relation_defect(
            WRONG_RELATION_SQL, session, SCHEMA, build_query_surface([]),
        )

        assert defect is None
        assert session.value_type_probes == []
        assert relation_by_entity_type(build_query_surface([])) == {}

    async def test_a_value_under_an_unclaimed_entity_type_is_not_a_defect(self):
        """The value exists in the EAV store but projects nowhere, so there is no relation to
        send the retry to — and a genuinely unanswerable filter is still a real empty answer."""
        generator = SQLGenerator()
        session = FakeSession(value_types={"oracle": ["MYSTERY"]})

        defect = await generator._wrong_relation_defect(
            WRONG_RELATION_SQL, session, SCHEMA, SURFACE,
        )

        assert defect is None

    async def test_value_in_the_queried_relation_is_not_a_defect(self):
        llm = FakeLLM(WRONG_RELATION_SQL)
        session = FakeSession(
            value_types={"oracle": ["SKILL", "EMPLOYER"]}, data_results=[[]],
        )
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]

    async def test_all_attempts_failed_raises_not_empty(self):
        """Row 59 — exhausted attempts propagate as a failure carrying the trace, never as
        an empty successful result."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()

        with pytest.raises(SQLGenerationFailed) as exc:
            await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert len(exc.value.attempts) == 3
        assert all(a.outcome == SQLAttemptOutcome.VALIDATION_ERROR for a in exc.value.attempts)

    async def test_deadline_abandon_distinguishable_from_exhaustion(self):
        """A loop cut short by the deadline reports the attempts it actually made, not a
        full set of failures."""
        import time

        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()

        with pytest.raises(SQLGenerationFailed) as exc:
            await make_generator(llm).generate_and_execute(
                "q", session, SCHEMA, deadline=time.monotonic() - 1,
            )

        assert len(exc.value.attempts) == 1
        assert llm.call_count == 1


# ------------------------------------------------------ filename defect (row 30)


class TestFilenameDefect:
    FILENAME_SQL = (
        "SELECT s.document_id, s.filename FROM subject s "
        "WHERE s.filename ILIKE '%hannah%' LIMIT 100"
    )

    async def test_filename_no_document_carries_is_a_defect(self):
        """Row 30 — the alias-agnostic regex catches `subject.filename` unchanged."""
        llm = FakeLLM(self.FILENAME_SQL, GOOD_SQL)
        session = FakeSession(
            filenames=["Resume 4.pdf"], data_results=[[], [("python",)]],
        )
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["outcome"] == SQLAttemptOutcome.EMPTY_WITH_DEFECT
        assert sink[0]["defect"] == "filename:hannah"

    async def test_filename_that_matches_is_not_a_defect(self):
        llm = FakeLLM(self.FILENAME_SQL)
        session = FakeSession(filenames=["Resume - Hannah.pdf"], data_results=[[]])
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]

    async def test_filename_feedback_is_relational(self):
        from src.chat_api.services.sql_generator import SQLAttempt, _render_attempt_feedback

        feedback = _render_attempt_feedback([
            SQLAttempt(
                attempt=1, max_attempts=3, outcome=SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                sql=self.FILENAME_SQL, row_count=0, defect="filename:hannah",
            )
        ], SURFACE)

        assert "no document in this tenant has that in its filename" in feedback
        assert "entity_type" not in feedback
        assert "document_entities" not in feedback


# --------------------------------------------- result completeness (rows 56-58)


class TestResultCompleteness:
    async def test_truncated_result_reports_returned_and_matched(self):
        """`DEFAULT_LIMIT = 100` silently truncated a 142-row result while the prompt told
        the model to treat the block as exhaustive."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(
            data_results=[[(f"v{i}",) for i in range(101)]], matched_total=142,
        )
        completeness: dict = {}

        rows = await make_generator(llm).generate_and_execute(
            "q", session, SCHEMA, completeness_sink=completeness,
        )

        assert len(rows) == 100
        assert completeness == {"returned": 100, "matched": 142, "truncated": True}
        assert session.count_queries

    async def test_complete_result_not_marked_truncated(self):
        """And no second query is issued for it."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(data_results=[[(f"v{i}",) for i in range(12)]])
        completeness: dict = {}

        rows = await make_generator(llm).generate_and_execute(
            "q", session, SCHEMA, completeness_sink=completeness,
        )

        assert len(rows) == 12
        assert completeness == {"returned": 12, "matched": 12, "truncated": False}
        assert session.count_queries == []

    async def test_unavailable_count_reports_matched_unknown(self):
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(
            data_results=[[(f"v{i}",) for i in range(101)]], matched_total=None,
        )
        completeness: dict = {}

        await make_generator(llm).generate_and_execute(
            "q", session, SCHEMA, completeness_sink=completeness,
        )

        assert completeness["truncated"] is True
        assert completeness["matched"] is None

    async def test_completeness_reporting_does_not_alter_rows_or_limit(self):
        """The rows handed back and the statement's own limit are unchanged by the
        reporting."""
        llm = FakeLLM(GOOD_SQL)
        with_sink = FakeSession(data_results=[[("python",), ("go",)]])
        without_sink = FakeSession(data_results=[[("python",), ("go",)]])
        completeness: dict = {}

        reported = await make_generator(FakeLLM(GOOD_SQL)).generate_and_execute(
            "q", with_sink, SCHEMA, completeness_sink=completeness,
        )
        plain = await make_generator(llm).generate_and_execute("q", without_sink, SCHEMA)

        assert reported == plain == [{"value": "python"}, {"value": "go"}]
        # The probe asks for one row beyond the validated limit and discards the extra,
        # so the caller's rows are the same either way and the row limit the statement
        # declares — 100 — is never widened for the caller.
        assert "LIMIT 101" in with_sink.data_queries[0]
        assert with_sink.data_queries[0] == without_sink.data_queries[0]
        assert len(reported) == 2


# ------------------------------------------------------ rows 28, 51, 55: empty results


class TestEmptyResultPolicy:
    async def test_unexplained_empty_not_retried(self):
        """Rows 28, 51 — zero rows with a sound query is an answer, not a failure."""
        llm = FakeLLM(GOOD_SQL, GOOD_SQL)
        session = FakeSession(data_results=[[]])
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == []
        assert llm.call_count == 1
        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]
        assert sink[0]["row_count"] == 0

    async def test_non_empty_never_retried(self):
        """Row 55 — rows returned wins over every other signal, defect included."""
        llm = FakeLLM(WRONG_RELATION_SQL, GOOD_SQL)
        session = FakeSession(
            value_types={"oracle": ["EMPLOYER"]}, data_results=[[("oracle",)]],
        )
        generator = make_generator(llm)
        sink: list = []

        rows = await generator.generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert rows == [{"value": "oracle"}]
        assert llm.call_count == 1
        assert sink[0]["outcome"] == SQLAttemptOutcome.SUCCESS

    def test_defect_detection_ignores_negated_comparison(self):
        """A `!=` says nothing about where a value lives, so it explains nothing."""
        from src.chat_api.services.sql_generator import _NORMALIZED_VALUE_EQ_RE

        sql = "SELECT * FROM e_skill WHERE normalized_value != 'oracle' LIMIT 100"
        assert _NORMALIZED_VALUE_EQ_RE.findall(sql) == []


# ----------------------------------------------------------- rows 47, 49, 56, 57: feedback


class TestFeedback:
    async def test_retry_prompt_contains_previous_sql_and_reason(self):
        """Rows 49, 56."""
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
        assert "Reconsider the relations" in retry_prompt

    async def test_retry_prompt_restates_the_surface_on_a_validation_failure(self):
        """Rows 26, 47 — the rejected statement, the reason, and the relations that exist."""
        llm = FakeLLM(OFF_SURFACE_SQL, GOOD_SQL)
        session = FakeSession()

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        retry_prompt = llm.prompts[1]
        assert "Rejected by the SQL validation layer" in retry_prompt
        assert OFF_SURFACE_SQL in retry_prompt
        assert "The relations you may query are:" in retry_prompt
        assert "e_skill" in retry_prompt
        assert "subject" in retry_prompt

    async def test_empty_defect_feedback_names_the_holding_relation(self):
        """Row 52 through the loop."""
        llm = FakeLLM(WRONG_RELATION_SQL, GOOD_SQL)
        session = FakeSession(
            value_types={"oracle": ["EMPLOYER"]}, data_results=[[], [("python",)]],
        )

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        retry_prompt = llm.prompts[1]
        assert "0 rows returned" in retry_prompt
        assert "e_employer" in retry_prompt

    def test_sanitizer_strips_sql_and_parameter_echo(self):
        """Row 57 — SQLAlchemy appends the statement and bound values to str(exc)."""
        raw = (
            '(psycopg.errors.UndefinedColumn) column "document_name" does not exist\n'
            'LINE 1: SELECT document_name FROM subject\n'
            "[SQL: SELECT document_name FROM subject WHERE email = %(v)s]\n"
            "[parameters: {'v': 'alice@example.com'}]"
        )
        cleaned = _sanitize_error(Exception(raw))

        assert "alice@example.com" not in cleaned
        assert "[SQL:" not in cleaned
        assert "[parameters:" not in cleaned
        assert "LINE 1" not in cleaned
        assert "column \"document_name\" does not exist" in cleaned

    def test_sanitizer_truncates_to_budget(self):
        """Row 57 — bounded length."""
        cleaned = _sanitize_error(Exception("x" * 5000))
        assert len(cleaned) <= MAX_ERROR_FEEDBACK_CHARS

    def test_sanitizer_names_the_exception_type(self):
        assert _sanitize_error(ValueError("boom")).startswith("ValueError:")


# ------------------------------------------------------ rows 60-65: surface grounding


class TestSurfaceGrounding:
    async def test_surface_columns_and_types_reach_the_prompt(self):
        """Rows 60, 9, 10 — identifiers, declared types, and the tenant's own semantics."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(entity_definitions=(
            definition_row("Skill", "e_skill", description="a professional capability"),
            definition_row(
                "Years Experience", "e_years_experience",
                cardinality="single", value_kind="number", value_unit="years",
            ),
        ))

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        prompt = llm.prompts[0]
        assert "`e_skill`" in prompt
        assert "a professional capability" in prompt
        assert "subject.years_experience" in prompt
        assert "DOUBLE PRECISION" in prompt
        assert "holds a parsed number value in years" in prompt

    async def test_samples_are_listed_under_their_relation(self):
        """Row 61 — keyed by relation, never by the storage-level entity type."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[
            ("SKILL", "python"), ("SKILL", "kubernetes"), ("EMAIL", "a@example.com"),
        ])

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        prompt = llm.prompts[0]
        skill_block = prompt.split("`e_skill`")[1]
        assert "python" in skill_block.split("`e_employer`")[0]
        assert "value in the data: a@example.com" in prompt
        assert "SKILL\n" not in prompt

    async def test_caps_are_respected_per_relation_and_in_total(self, monkeypatch):
        """Row 62 — the two budgets are reinterpreted, not dropped."""
        monkeypatch.setattr(settings, "sql_entity_sample_values_per_type", 2)
        monkeypatch.setattr(settings, "sql_entity_sample_max_values", 3)
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[
            ("SKILL", "a"), ("SKILL", "b"), ("SKILL", "c"),
            ("EMPLOYER", "d"), ("EMPLOYER", "e"),
        ])
        generator = SQLGenerator()
        generator.client = llm

        grounding = await generator._fetch_surface_grounding(
            session, SCHEMA, build_query_surface([
                EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
                EntityDefinitionSpec(name="Employer", sql_identifier="e_employer"),
            ]),
        )

        # Spent in prompt order: the first relation takes its per-relation budget, the
        # second takes what the total budget has left.
        by_identifier = {r.identifier: r.samples for r in grounding.relations}
        assert by_identifier["e_employer"] == ["d", "e"]
        assert by_identifier["e_skill"] == ["a"]
        assert sum(len(v) for v in by_identifier.values()) == 3

    async def test_sample_values_are_truncated(self):
        """The per-value cap is unchanged."""
        session = FakeSession(samples=[("SKILL", "z" * 500)])
        generator = SQLGenerator()

        grounding = await generator._fetch_surface_grounding(session, SCHEMA, SURFACE)

        sample = next(r for r in grounding.relations if r.identifier == "e_skill").samples[0]
        assert len(sample) == MAX_SAMPLE_VALUE_CHARS

    async def test_relation_without_samples_is_still_listed(self):
        """Rows 12, 63 — absence of a sample is not absence of the relation."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(samples=[("SKILL", "python")])

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert "`e_employer`" in llm.prompts[0]
        assert "`subject.email`" in llm.prompts[0]

    async def test_entity_type_claimed_by_no_definition_contributes_nothing(self):
        """The EAV store tolerates undefined types deliberately; they project nowhere."""
        session = FakeSession(samples=[("MYSTERY", "whatever"), ("SKILL", "python")])
        generator = SQLGenerator()

        grounding = await generator._fetch_surface_grounding(session, SCHEMA, SURFACE)

        assert "whatever" not in [s for r in grounding.relations for s in r.samples]
        assert next(r for r in grounding.relations if r.identifier == "e_skill").samples == ["python"]

    async def test_surface_and_samples_fetched_once_per_invocation(self):
        """Rows 13, 64 — three attempts, one resolution and one sample query."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()

        with pytest.raises(SQLGenerationFailed):
            await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert llm.call_count == 3
        assert len(session.definition_queries) == 1
        assert sum(1 for s in session.statements if "ROW_NUMBER() OVER" in s) == 1

    async def test_one_tenants_surface_never_appears_in_anothers_prompt(self):
        """Rows 65, 4 — ADR-001: the surface is resolved from the bound schema."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(entity_definitions=(
            definition_row("Skill", "e_skill"),
            definition_row("Contract", "e_contract", tenant_id="globex"),
        ))

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert "e_skill" in llm.prompts[0]
        assert "e_contract" not in llm.prompts[0]

    async def test_grounding_degrades_to_empty_on_query_failure(self):
        """The prompt loses its samples but the turn proceeds."""
        llm = FakeLLM(GOOD_SQL)

        class BrokenSamples(FakeSession):
            async def execute(self, statement, params=None):
                if "ROW_NUMBER() OVER" in str(statement):
                    raise Exception("relation does not exist")
                return await super().execute(statement, params)

        rows = await make_generator(llm).generate_and_execute("q", BrokenSamples(), SCHEMA)

        assert rows == [{"value": "python"}]

    def test_render_surface_is_empty_without_relations(self):
        generator = SQLGenerator()
        assert generator._render_surface(None) == ""
        assert generator._render_surface(SurfaceGrounding()) == ""


class TestBaseModelGrounding:
    """Rows 11, 14, 15 — ADR-008. On a base-model tenant `entity_type` holds CoNLL labels,
    and only `base_label_mapping` says which relation those values belong to. Name equality
    would leave every base-model tenant with an unsampled surface."""

    BASE_DEFINITIONS = (
        definition_row("Person", "e_person", base_label_mapping={"PER": 1}),
        definition_row("Employer", "e_employer", base_label_mapping={"ORG": 1}),
    )

    async def test_base_label_samples_land_under_the_mapped_relation(self):
        session = FakeSession(
            entity_definitions=self.BASE_DEFINITIONS,
            samples=[("PER", "reshma u"), ("ORG", "acme corp")],
        )
        generator = SQLGenerator()

        grounding = await generator._fetch_surface_grounding(
            session, SCHEMA, build_query_surface([
                EntityDefinitionSpec(name="Person", sql_identifier="e_person",
                                     base_label_mapping={"PER": 1}),
                EntityDefinitionSpec(name="Employer", sql_identifier="e_employer",
                                     base_label_mapping={"ORG": 1}),
            ]),
        )

        by_identifier = {r.identifier: r.samples for r in grounding.relations}
        assert by_identifier["e_person"] == ["reshma u"]
        assert by_identifier["e_employer"] == ["acme corp"]

    async def test_prompt_presents_the_definition_name_not_the_label(self):
        llm = FakeLLM("SELECT document_id, value FROM e_person LIMIT 100")
        session = FakeSession(
            entity_definitions=self.BASE_DEFINITIONS, samples=[("PER", "reshma u")],
        )

        await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        prompt = llm.prompts[0]
        assert "`e_person` (many rows per subject" in prompt
        assert "Person" in prompt
        assert "PER\n" not in prompt

    async def test_wrong_relation_probe_routes_through_the_label_mapping(self):
        """Row 15 — the defect probe uses the same index the projection writes by."""
        wrong = (
            "SELECT document_id, value FROM e_person "
            "WHERE normalized_value = 'acme corp' LIMIT 100"
        )
        llm = FakeLLM(wrong, "SELECT document_id, value FROM e_employer LIMIT 100")
        session = FakeSession(
            entity_definitions=self.BASE_DEFINITIONS,
            value_types={"acme corp": ["ORG"]},
            data_results=[[], [("acme corp",)]],
        )
        sink: list = []

        await make_generator(llm).generate_and_execute("q", session, SCHEMA, attempt_sink=sink)

        assert sink[0]["defect"] == "wrong_relation:acme corp|e_employer"


# ------------------------------------------------- rows 31-33: projection coverage


class TestCoverageProbe:
    """A tenant whose documents predate the projection has full EAV data and an empty
    `subject`. Every relational statement then returns zero rows for a reason that has
    nothing to do with the question, and the zero-rows policy would call that an answer."""

    async def test_unprojected_tenant_fails_rather_than_answering_empty(self):
        """Row 31."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=True, data_results=[])

        with pytest.raises(SQLGenerationFailed) as exc:
            await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert "relational entity surface holds no rows" in str(exc.value)
        assert llm.call_count == 0  # not a wasted generation call either
        assert session.data_queries == []

    async def test_unprojected_scoped_document_fails(self):
        """Row 32 — the same failure at document granularity."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=True, data_results=[])

        with pytest.raises(SQLGenerationFailed) as exc:
            await make_generator(llm).generate_and_execute(
                "q", session, SCHEMA, document_ids=["D1"],
            )

        assert "requested document(s)" in str(exc.value)
        assert "scope_document_ids" in session.coverage_queries[0]

    async def test_a_schema_with_no_subject_table_is_the_same_failure(self):
        """The commoner shape of row 31: a tenant that has not extracted since the projection
        shipped has no generated tables at all. Before the existence check the probe died on
        `UndefinedTable`, was written off as "we don't know", and the turn degraded into three
        failed attempts instead of one clear unavailable-source answer."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(subject_exists=False, extracted=True, data_results=[])

        with pytest.raises(SQLGenerationFailed) as exc:
            await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert "relational entity surface holds no rows" in str(exc.value)
        assert llm.call_count == 0
        assert "false AS projected" in session.coverage_queries[0]

    async def test_no_subject_table_and_no_entities_is_not_a_coverage_failure(self):
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(subject_exists=False, extracted=False, data_results=[[]])

        assert await make_generator(llm).generate_and_execute("q", session, SCHEMA) == []

    async def test_populated_surface_answers_normally(self):
        """Row 33 — a genuinely non-matching question still returns an empty success."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=True, extracted=True, data_results=[[]])
        sink: list = []

        rows = await make_generator(llm).generate_and_execute(
            "q", session, SCHEMA, attempt_sink=sink,
        )

        assert rows == []
        assert [a["outcome"] for a in sink] == [SQLAttemptOutcome.SUCCESS]

    async def test_tenant_with_no_data_at_all_is_not_a_coverage_failure(self):
        """Nothing extracted is nothing to project: an empty answer is the truth."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=False, data_results=[[]])

        rows = await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert rows == []

    async def test_probe_failure_does_not_break_a_working_question(self):
        """A failed probe is best-effort, exactly like the other probes."""
        llm = FakeLLM(GOOD_SQL)

        class BrokenProbe(FakeSession):
            async def execute(self, statement, params=None):
                if "AS projected" in str(statement):
                    raise Exception("relation \"subject\" does not exist")
                return await super().execute(statement, params)

        rows = await make_generator(llm).generate_and_execute("q", BrokenProbe(), SCHEMA)

        assert rows == [{"value": "python"}]

    async def test_no_eav_fallback_statement_is_executed(self):
        """Risk 6 — the failure is explicit; there is no second query model to fall back to."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=True, data_results=[])

        with pytest.raises(SQLGenerationFailed):
            await make_generator(llm).generate_and_execute("q", session, SCHEMA)

        assert not any(
            "FROM document_entities" in s and "AS projected" not in s
            for s in session.data_queries
        )

    async def test_unprojected_tenant_reports_the_source_as_unavailable(self):
        """Row 31 at the tool boundary: an error ToolResult, not an empty success."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(projected=False, extracted=True, data_results=[])
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call(
            {"query": "q"}, _tool_context(orchestrator, session),
        )

        assert result.error is not None
        assert result.results == []


# ------------------------------------------- rows 5-7, 41: validation and isolation


class TestSecurityInvariants:
    async def test_every_retry_is_validated(self):
        """The third attempt's SQL passes through validate_sql."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)
        validated: list[str] = []
        real_validate = generator.validate_sql

        def spy(sql: str, surface=None) -> str:
            validated.append(sql)
            return real_validate(sql, surface)

        generator.validate_sql = spy
        await generator.generate_and_execute("q", session, SCHEMA)

        assert validated == [BAD_TABLE_SQL, BAD_TABLE_SQL, GOOD_SQL]

    async def test_retry_cannot_escape_whitelist(self):
        """A non-whitelisted retry is rejected and never executed."""
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

    async def test_the_prompted_set_and_the_validated_set_are_the_same(self):
        """Row 41 — one resolver call feeds both, so a relation described but not accepted
        (or the reverse) cannot exist."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        surface = await generator._fetch_query_surface(session, SCHEMA)
        prompt = llm.prompts[0]
        for relation in surface.table_names:
            assert relation in prompt
        assert "e_email" not in prompt.replace("subject.email", "")

    async def test_all_attempts_use_request_context_schema(self):
        """The LLM naming another schema changes nothing."""
        hostile_sql = f"SELECT document_id, value FROM e_skill /* {OTHER_SCHEMA} */ LIMIT 100"
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
        """Every execution opens the same read-only transaction."""
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
        """A failure must not arrive downstream as a successful empty."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is not None
        assert "attempt" in result.error
        assert result.results == []

    async def test_legitimate_empty_is_not_an_error(self):
        """The deliberate asymmetry with the test above."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(data_results=[[]])
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is None
        assert result.results == []
        assert llm.call_count == 1

    async def test_trace_records_both_attempts(self):
        """A recovered query is diagnosable from the ToolResult alone."""
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
        """A failure with no trace would not be diagnosable."""
        llm = FakeLLM(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        result = await StructuredRetrievalTool().call({"query": "q"}, _tool_context(orchestrator, session))

        assert result.error is not None
        assert len(result.diagnostics) == 3

    async def test_tool_context_schema_reaches_the_generator(self):
        """The tool's schema, not the question's."""
        llm = FakeLLM(GOOD_SQL)
        session = FakeSession()
        orchestrator = _orchestrator_with(make_generator(llm))

        await StructuredRetrievalTool().call(
            {"query": f"everything in {OTHER_SCHEMA}"}, _tool_context(orchestrator, session),
        )

        assert set(session.search_paths) == {SCHEMA}


# --------------------------------------- rows 8, 41: one resolver, three consumers


class TestOneResolverFeedsEveryConsumer:
    """verification.md rows 8, 41 and Risk 1.

    The three failure modes of these sets disagreeing are all invisible at run time: a granted
    relation the validator rejects, a validated relation the database refuses, and a relation
    described to the generator that neither will accept. So they are asserted equal from one
    resolver call rather than kept in step by discipline.
    """

    async def test_prompted_validated_and_granted_sets_are_equal(self):
        from src.chat_api.services.sql_execution_role import build_role_statements
        from src.chat_api.services.sql_generator import accepted_relations
        from src.shared.entity_views import resolve_generated_tables

        llm = FakeLLM(GOOD_SQL)
        session = FakeSession()
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)
        prompt = llm.prompts[0]

        surface = await generator._fetch_query_surface(session, SCHEMA)
        granted_tables = (await resolve_generated_tables(session, [SCHEMA]))[SCHEMA]
        statements = "\n".join(build_role_statements("role_x", [SCHEMA], {SCHEMA: granted_tables}))

        assert granted_tables == surface.table_names
        for relation in surface.table_names:
            assert relation in prompt, f"{relation} described to nobody"
            assert relation in accepted_relations(surface)
            assert f"GRANT SELECT ON {SCHEMA}.{relation} TO role_x" in statements

    async def test_a_relation_off_the_surface_reaches_none_of_the_three(self):
        from src.chat_api.services.sql_execution_role import build_role_statements
        from src.chat_api.services.sql_generator import accepted_relations
        from src.shared.entity_views import resolve_generated_tables

        llm = FakeLLM(GOOD_SQL)
        session = FakeSession(entity_definitions=(
            definition_row("Skill", "e_skill"),
            definition_row("Retired", "e_retired", is_active=False),
            definition_row("Email", "e_email", cardinality="single"),
        ))
        generator = make_generator(llm)

        await generator.generate_and_execute("q", session, SCHEMA)

        surface = await generator._fetch_query_surface(session, SCHEMA)
        granted = (await resolve_generated_tables(session, [SCHEMA]))[SCHEMA]
        statements = "\n".join(build_role_statements("role_x", [SCHEMA], {SCHEMA: granted}))

        for off_surface in ("e_retired", "e_email"):
            assert off_surface not in surface.table_names
            assert off_surface not in accepted_relations(surface)
            assert f"GRANT SELECT ON {SCHEMA}.{off_surface}" not in statements
            assert f"`{off_surface}`" not in llm.prompts[0]

    def test_no_generated_relation_name_is_hard_coded_outside_entity_views(self):
        """Risk 1 — the surface is per-tenant and mutable at run time, so a name written
        into any other module is a name that cannot follow the catalog."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "src"
        owner = root / "shared" / "entity_views.py"
        literal = re.compile(r"""['"](?:subject|e_[a-z][a-z0-9_]*)['"]""")

        offenders = [
            f"{path.relative_to(root)}:{index}"
            for path in root.rglob("*.py")
            if path != owner
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if literal.search(line)
        ]

        assert offenders == []
