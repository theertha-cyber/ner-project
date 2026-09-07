"""Everything one chat request emits, checked against the content it was built from.

Verification row 6.

The three surfaces this change adds to are span attributes, metric labels and log records,
and they do not share a safety story. The foundation's redaction filter sits on the
logging path only — it is not on the metrics path at all, and metric retention is long and
dashboard access is broad. Spans reach the same collector as the logs with no filter in
between. So all three are collected here and checked against the same sentinels.

The sentinels are chosen to be the things this repository has actually leaked or nearly
leaked: an entity value in a WHERE clause, a filename that is a candidate's name, the
generated statement, and the question itself.
"""

import json
import logging

import pytest
from prometheus_client import REGISTRY

from src.chat_api.services.sql_generator import SQLAttemptOutcome, SQLGenerator
from src.shared.observability import domain_metrics as dm

from tests.chat_api.test_sql_attempt_logging import (
    GOOD_SQL,
    LEAKED_VALUE,
    SCHEMA,
    FakeLLM,
    FakeSession,
)

pytestmark = [pytest.mark.verification]

QUESTION = "which candidates named Priya Raman know python"

# Every one of these is content, not a derived fact. Each is drawn from something the
# chat path genuinely handles: an extracted entity value, the filename it came from, a
# fragment of the generated statement, and the user's own words.
SENTINELS = (
    LEAKED_VALUE,          # an extracted entity value — a real person's name
    "Resume 4.pdf",        # a filename, routinely a candidate's name
    "document_entities",   # the generated statement's own table
    "SELECT",              # any generated statement at all
    "named Priya",         # the question's own words
)


def _generator(*responses) -> SQLGenerator:
    generator = SQLGenerator()
    generator.client = FakeLLM(*responses)
    return generator


def _all_metric_label_values() -> list[tuple[str, str, str]]:
    return [
        (metric.name, key, str(value))
        for metric in REGISTRY.collect()
        for sample in metric.samples
        for key, value in sample.labels.items()
    ]


def _rendered_records(caplog) -> list[str]:
    rendered = []
    for record in caplog.records:
        rendered.append(
            record.getMessage()
            + json.dumps({k: str(v) for k, v in record.__dict__.items()})
        )
    return rendered


def _span_text(exporter) -> list[str]:
    return [
        f"{span.name} " + " ".join(f"{k}={v}" for k, v in dict(span.attributes).items())
        for span in exporter.get_finished_spans()
    ]


class TestOneChatRequestLeaksNothing:
    """Row 6 — spans, labels and log records from the same request, checked together."""

    @pytest.fixture
    async def emitted(self, captured_spans, caplog):
        """Drive one question end to end through the instrumented generation path."""
        with caplog.at_level(logging.DEBUG, logger="src.chat_api.services.sql_generator"):
            await _generator(GOOD_SQL).generate_and_execute(QUESTION, FakeSession(), SCHEMA)
        return {
            "spans": _span_text(captured_spans),
            "labels": _all_metric_label_values(),
            "logs": _rendered_records(caplog),
        }

    @pytest.mark.parametrize("sentinel", SENTINELS)
    async def test_no_span_attribute_carries_it(self, emitted, sentinel):
        offenders = [text for text in emitted["spans"] if sentinel in text]

        assert offenders == [], (
            "a span attribute reaches the same collector as a log record and there is no "
            f"redaction filter on that path: {offenders[:2]}"
        )

    @pytest.mark.parametrize("sentinel", SENTINELS)
    async def test_no_metric_label_carries_it(self, emitted, sentinel):
        offenders = [
            (family, key, value)
            for family, key, value in emitted["labels"]
            if sentinel in value
        ]

        assert offenders == [], (
            "metric retention is long, dashboard access is broad, and the foundation's "
            f"redaction filter is not on the metrics path at all: {offenders[:2]}"
        )

    @pytest.mark.parametrize("sentinel", (LEAKED_VALUE, "document_entities"))
    async def test_no_log_record_carries_it(self, emitted, sentinel):
        offenders = [text[:200] for text in emitted["logs"] if sentinel in text]

        assert offenders == [], offenders[:2]

    async def test_the_capture_is_not_empty(self, emitted):
        """The assertion that makes the three above mean anything.

        A scan that inspects nothing reports clean, and a clean report from an empty
        capture is worse than no report because it becomes evidence for a gate. This is
        the same rule the release-gate scan enforces, applied at unit scale.
        """
        assert emitted["spans"], "no spans were emitted — the checks above proved nothing"
        assert emitted["labels"], "no metric samples were recorded"
        assert emitted["logs"], "no log records were emitted"

        assert any("sql_generation" in text for text in emitted["spans"])


class TestTheDerivedFactsSurviveTheRedaction:
    """The corollary. A telemetry surface that carries nothing useful also passes every
    test above, so what is asserted here is that the *shape* is still there."""

    async def test_the_span_still_answers_what_the_generation_did(self, captured_spans):
        await _generator(GOOD_SQL).generate_and_execute(QUESTION, FakeSession(), SCHEMA)

        span = next(
            s for s in captured_spans.get_finished_spans() if s.name == "sql_generation"
        )
        attributes = dict(span.attributes)

        assert attributes["outcome"] == "succeeded"
        assert attributes["attempts"] == 1
        assert attributes["repair_depth"] == 0

    def test_the_defect_class_is_kept_while_its_payload_is_not(self):
        dm.record_sql_attempt(
            SQLAttemptOutcome.EMPTY_WITH_DEFECT, f"filename:{LEAKED_VALUE} Resume 4.pdf"
        )

        classes = {
            value
            for family, key, value in _all_metric_label_values()
            if family == "ner_sql_attempts" and key == "defect_class"
        }
        assert "filename:" in classes, (
            "the category is what a dashboard reads; stripping the payload must not "
            "strip the signal"
        )
        assert not any(LEAKED_VALUE in value for value in classes)
