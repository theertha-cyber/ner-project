"""The repair loop, measured.

Verification rows 2 and 3.

The Phase 1 claim about the repair loop — that a first invalid query gets corrected rather
than abandoned — has been checkable only by running a question suite by hand. `SQLAttempt`
has carried `attempt`, `outcome` and `defect` all along and nothing counted any of it.
These tests pin the counting.

The defect assertions are the security-relevant half. `SQLAttempt.defect` carries its
evidence inline — `filename:<literal>`, `wrong_relation:<literal>|<relation>` — and those
literals come from the tenant's own documents, where a filename is routinely a candidate's
name. `_defect_class` strips the payload, and `record_sql_attempt` is the only path from
the field to a label.
"""

from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

from src.chat_api.services.sql_generator import (
    DEFECT_CLASSES,
    SQLAttemptOutcome,
    SQLGenerationFailed,
    SQLGenerator,
)
from src.shared.observability import domain_metrics as dm

from tests.chat_api.test_sql_attempt_logging import (
    BAD_TABLE_SQL,
    GOOD_SQL,
    SCHEMA,
    FakeLLM,
    FakeSession,
)

pytestmark = [pytest.mark.verification]


def _generator(*responses) -> SQLGenerator:
    generator = SQLGenerator()
    generator.client = FakeLLM(*responses)
    return generator


def _attempts(outcome: str, defect_class: str = dm.NONE) -> float:
    value = REGISTRY.get_sample_value(
        "ner_sql_attempts_total", {"outcome": outcome, "defect_class": defect_class}
    )
    return float(value or 0.0)


def _repair_observations() -> float:
    return float(REGISTRY.get_sample_value("ner_sql_repair_depth_count", {}) or 0.0)


def _repair_sum() -> float:
    return float(REGISTRY.get_sample_value("ner_sql_repair_depth_sum", {}) or 0.0)


def _generations(outcome: str, abandon_reason: str = dm.NONE) -> float:
    value = REGISTRY.get_sample_value(
        "ner_sql_generations_total", {"outcome": outcome, "abandon_reason": abandon_reason}
    )
    return float(value or 0.0)


def _span_named(exporter, name: str):
    return next((s for s in exporter.get_finished_spans() if s.name == name), None)


class TestARepairedQuery:
    """Row 2 — first invalid, second valid."""

    async def test_the_span_records_two_attempts_and_one_repair(self, captured_spans):
        await _generator(BAD_TABLE_SQL, GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        span = _span_named(captured_spans, "sql_generation")
        assert span is not None
        assert span.attributes["attempts"] == 2
        assert span.attributes["repair_depth"] == 1, (
            "repair depth is attempts minus one — the number of times the loop had to "
            "correct itself, which is the quantity the Phase 1 claim is about"
        )
        assert span.attributes["outcome"] == "succeeded"

    async def test_the_first_attempt_is_counted_under_an_enumerated_outcome(self):
        before = _attempts(SQLAttemptOutcome.VALIDATION_ERROR)

        await _generator(BAD_TABLE_SQL, GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        assert _attempts(SQLAttemptOutcome.VALIDATION_ERROR) == before + 1

    async def test_a_histogram_observation_is_recorded_per_completed_generation(self):
        before_count = _repair_observations()
        before_sum = _repair_sum()

        await _generator(BAD_TABLE_SQL, GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        assert _repair_observations() == before_count + 1
        assert _repair_sum() == before_sum + 1

    async def test_a_first_attempt_success_records_a_repair_depth_of_zero(self):
        before_count = _repair_observations()
        before_sum = _repair_sum()

        await _generator(GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        assert _repair_observations() == before_count + 1
        assert _repair_sum() == before_sum, (
            "a query that needed no repair still needs an observation, or the "
            "distribution is computed over failures only"
        )

    async def test_a_successful_generation_is_counted_with_no_abandon_reason(self):
        before = _generations("succeeded")

        await _generator(GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        assert _generations("succeeded") == before + 1


class TestAnAbandonedQuery:
    """Row 3 — attempt exhaustion and deadline exhaustion are both `abandoned`, under
    reasons that tell them apart. One is a generation-quality problem and the other is a
    budget problem, and they have different fixes."""

    async def test_attempt_exhaustion_records_its_own_reason(self):
        before = _generations("abandoned", "attempts_exhausted")

        with pytest.raises(SQLGenerationFailed):
            await _generator(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL).generate_and_execute(
                "who knows python", FakeSession(), SCHEMA
            )

        assert _generations("abandoned", "attempts_exhausted") == before + 1

    async def test_deadline_exhaustion_records_a_different_reason(self):
        import time

        before_deadline = _generations("abandoned", "deadline_exhausted")
        before_attempts = _generations("abandoned", "attempts_exhausted")

        with pytest.raises(SQLGenerationFailed):
            await _generator(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL).generate_and_execute(
                "who knows python",
                FakeSession(),
                SCHEMA,
                # Already past when the loop checks it, so the second attempt is the one
                # that trips the deadline branch rather than the attempt budget.
                deadline=time.monotonic() - 1,
            )

        assert _generations("abandoned", "deadline_exhausted") == before_deadline + 1
        assert _generations("abandoned", "attempts_exhausted") == before_attempts, (
            "a run that ran out of time must not be counted as one that ran out of tries"
        )

    async def test_the_span_records_the_abandonment(self, captured_spans):
        with pytest.raises(SQLGenerationFailed):
            await _generator(BAD_TABLE_SQL, BAD_TABLE_SQL, BAD_TABLE_SQL).generate_and_execute(
                "who knows python", FakeSession(), SCHEMA
            )

        span = _span_named(captured_spans, "sql_generation")
        assert span.attributes["outcome"] == "abandoned"
        assert span.attributes["abandon_reason"] == "attempts_exhausted"


class TestTheDefectPayloadNeverBecomesALabel:
    """Design Decision 2 and risk 1 — the highest-risk aspect of this change, and not a
    hypothetical one."""

    @pytest.mark.parametrize(
        "defect, expected",
        [
            ("filename:Priya Raman Resume 4.pdf", "filename:"),
            ("wrong_relation:Priya Raman|subject.name", "wrong_relation:"),
            ("scope:documents,document_entities", "scope:"),
        ],
    )
    def test_only_the_class_reaches_the_label(self, defect, expected):
        before = _attempts(SQLAttemptOutcome.EMPTY_WITH_DEFECT, expected)

        dm.record_sql_attempt(SQLAttemptOutcome.EMPTY_WITH_DEFECT, defect)

        assert _attempts(SQLAttemptOutcome.EMPTY_WITH_DEFECT, expected) == before + 1

    def test_the_literal_appears_in_no_series_on_the_registry(self):
        dm.record_sql_attempt(
            SQLAttemptOutcome.EMPTY_WITH_DEFECT, "filename:Priya Raman Resume 4.pdf"
        )

        offenders = [
            (metric.name, sample.labels)
            for metric in REGISTRY.collect()
            for sample in metric.samples
            if any("Priya" in str(value) for value in sample.labels.values())
        ]
        assert offenders == [], (
            "a filename literal is drawn from a tenant document and is routinely a "
            f"person's name; Prometheus has no redaction filter: {offenders}"
        )

    def test_the_declared_classes_are_the_generator_s_own(self):
        """A fourth defect kind added upstream without widening `DEFECT_CLASSES` lands on
        `other` rather than minting a series — and the declaration test catches it."""
        declared = dm.SQL_ATTEMPTS.labels[1].values

        assert DEFECT_CLASSES <= declared
        assert dm.NONE in declared

    def test_an_attempt_with_no_defect_is_recorded_as_none(self):
        before = _attempts(SQLAttemptOutcome.GENERATION_ERROR, dm.NONE)

        dm.record_sql_attempt(SQLAttemptOutcome.GENERATION_ERROR, None)

        assert _attempts(SQLAttemptOutcome.GENERATION_ERROR, dm.NONE) == before + 1


class TestExecutionIsMeasured:
    """Task 4.4 — duration, rows and truncation."""

    async def test_a_successful_execution_records_rows_and_truncation(self):
        before = float(
            REGISTRY.get_sample_value("ner_sql_executions_total", {"truncated": "false"}) or 0.0
        )

        await _generator(GOOD_SQL).generate_and_execute(
            "who knows python", FakeSession(), SCHEMA
        )

        after = float(
            REGISTRY.get_sample_value("ner_sql_executions_total", {"truncated": "false"}) or 0.0
        )
        assert after == before + 1
        assert REGISTRY.get_sample_value("ner_sql_execution_rows_count", {}) is not None

    def test_truncation_is_a_label_rather_than_a_bucket_edge(self):
        """An answer built from a capped row set is a different claim about the tenant's
        data, so it must be queryable directly rather than inferred from a row count."""
        assert dm.SQL_EXECUTIONS.label_names == ("truncated",)
        assert dm.SQL_EXECUTIONS.labels[0].values == frozenset({"true", "false"})
