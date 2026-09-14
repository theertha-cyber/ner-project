"""Entity resolution records its outcome and how many mentions it checked — and nothing else.

Verification row 10.

The second half of this file matters more than the first. `ResolutionResult` carries
`mention`, `resolved_entity_value` and `candidates`, and every one of those is the
tenant's own extracted data — a candidate's name, verbatim, drawn from a resume. The
resolver is therefore the single most tempting place in the chat path to put a useful
string on a span, and span attributes reach the same collector as logs with no redaction
filter in between.
"""

import pytest
from prometheus_client import REGISTRY

from src.chat_api.services.entity_resolver import (
    AMBIGUOUS,
    OVER_CAP,
    UNIQUE,
    UNRESOLVED,
    ResolutionResult,
)
from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

OUTCOMES = (UNRESOLVED, UNIQUE, AMBIGUOUS, OVER_CAP)


def _resolutions(outcome: str) -> float:
    value = REGISTRY.get_sample_value("ner_entity_resolutions_total", {"outcome": outcome})
    return float(value or 0.0)


def _mentions_count(outcome: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_entity_resolution_mentions_checked_count", {"outcome": outcome}
    )
    return float(value or 0.0)


def _mentions_sum(outcome: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_entity_resolution_mentions_checked_sum", {"outcome": outcome}
    )
    return float(value or 0.0)


class TestEveryOutcomeIsRecorded:
    """Row 10's first clause — all four constants, not just the interesting ones."""

    @pytest.mark.parametrize("outcome", OUTCOMES)
    def test_the_outcome_and_mentions_checked_are_recorded_together(self, outcome):
        before_count = _resolutions(outcome)
        before_observations = _mentions_count(outcome)
        before_sum = _mentions_sum(outcome)

        dm.record_entity_resolution(outcome, mentions_checked=3)

        assert _resolutions(outcome) == before_count + 1
        assert _mentions_count(outcome) == before_observations + 1
        assert _mentions_sum(outcome) == before_sum + 3, (
            "the count without the mentions checked cannot distinguish 'the question "
            "named nobody' from 'it named three people and none matched'"
        )

    def test_the_declared_values_are_the_resolver_s_own_constants(self):
        """A rename in `entity_resolver.py` must break this import rather than leave a
        label value no dashboard matches."""
        declared = dm.ENTITY_RESOLUTIONS.labels[0].values

        assert set(OUTCOMES) <= declared

    def test_an_undeclared_outcome_cannot_mint_a_series(self):
        before = _resolutions(dm.OTHER)

        dm.record_entity_resolution("an outcome nobody declared", mentions_checked=1)

        assert _resolutions(dm.OTHER) == before + 1


class TestNoMentionTextAnywhere:
    """Row 10's second clause."""

    async def test_the_span_carries_counts_and_categories_but_no_entity_value(
        self, captured_spans, monkeypatch
    ):
        from src.chat_api.services import entity_resolver

        async def _fake(message, session, schema, tenant_id):
            return ResolutionResult(
                outcome=UNIQUE,
                mention="Priya Raghunathan",
                mentions_checked=2,
                resolved_document_ids=["doc-1"],
                resolved_entity_value="Priya Raghunathan",
            )

        monkeypatch.setattr(entity_resolver, "_resolve_entity", _fake)

        result = await entity_resolver.resolve_entity(
            "is Priya Raghunathan a good engineer", None, "tenant_x", "tenant-1"
        )

        assert result.outcome == UNIQUE, "behaviour is unchanged; only measurement is added"

        spans = captured_spans.get_finished_spans()
        assert [s.name for s in spans] == ["entity_resolution"]

        attributes = dict(spans[0].attributes)
        assert attributes["outcome"] == UNIQUE
        assert attributes["mentions_checked"] == 2
        assert attributes["resolved_documents"] == 1

        rendered = " ".join(f"{k}={v}" for k, v in attributes.items())
        assert "Priya" not in rendered and "Raghunathan" not in rendered, (
            "the resolved value is a real person's name from a tenant document; the span "
            "reaches the same collector as the logs, with no redaction filter in between"
        )

    def test_no_declared_label_could_hold_a_mention(self):
        """Structural rather than incidental: both families label on `outcome` alone, so
        there is no label key a mention could be passed as."""
        for family in (dm.ENTITY_RESOLUTIONS, dm.ENTITY_RESOLUTION_MENTIONS):
            assert family.label_names == ("outcome",)
            assert family.labels[0].values == frozenset({*OUTCOMES, dm.OTHER})
