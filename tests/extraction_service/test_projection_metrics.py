"""Projection reports how long it took and whether it wrote what it meant to.

Verification row 13.

The drift indicator exists because the failure mode it catches is silent. A projection
statement that does not execute leaves the relational query surface incomplete while the
run still reports `completed` — and the chat path then answers questions against a surface
that is missing rows, confidently and wrongly. Nothing today notices.

The comparison is between statements built and rows written, not between EAV entities and
relational rows: a `single` definition collapses many entities into one column and an
entity routed by no active definition is written nowhere, both by design, so those two
counts are *expected* to disagree and a drift signal built on them would fire constantly.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


def _projections(drift: str) -> float:
    value = REGISTRY.get_sample_value("ner_projections_total", {"drift": drift})
    return float(value or 0.0)


def _duration_count() -> float:
    value = REGISTRY.get_sample_value("ner_projection_duration_seconds_count", {})
    return float(value or 0.0)


def _duration_sum() -> float:
    value = REGISTRY.get_sample_value("ner_projection_duration_seconds_sum", {})
    return float(value or 0.0)


class TestACleanProjection:
    """Row 13's first clause."""

    def test_it_records_a_duration(self):
        before_count = _duration_count()
        before_sum = _duration_sum()

        dm.record_projection(0.25, source_rows=10, projected_rows=10)

        assert _duration_count() == before_count + 1
        assert _duration_sum() == pytest.approx(before_sum + 0.25)

    def test_matching_counts_are_recorded_as_clean(self):
        before = _projections("clean")

        dm.record_projection(0.1, source_rows=42, projected_rows=42)

        assert _projections("clean") == before + 1

    def test_a_projection_that_wrote_nothing_from_nothing_is_still_clean(self):
        before = _projections("clean")

        dm.record_projection(0.01, source_rows=0, projected_rows=0)

        assert _projections("clean") == before + 1, (
            "a document with no routable entities projects nothing and that is correct; "
            "counting it as drift would make the signal useless"
        )


class TestADriftingProjection:
    """Row 13's second clause."""

    def test_mismatched_counts_produce_the_drift_value(self):
        before_drift = _projections("row_count_mismatch")
        before_clean = _projections("clean")

        dm.record_projection(0.1, source_rows=10, projected_rows=7)

        assert _projections("row_count_mismatch") == before_drift + 1
        assert _projections("clean") == before_clean

    def test_drift_is_a_label_on_one_family_rather_than_a_separate_counter(self):
        """So the rate is `drift / total` on one query rather than a join between two
        families that may have been scraped at different instants."""
        assert dm.PROJECTIONS.label_names == ("drift",)
        assert dm.PROJECTIONS.labels[0].values == frozenset(
            {"clean", "row_count_mismatch", dm.OTHER}
        )

    def test_the_projector_measures_statements_built_against_rows_written(self):
        import inspect

        from src.extraction_service.services import relational_projection

        source = inspect.getsource(relational_projection.project_document_entities)

        assert "source_rows=len(statements)" in source
        assert "projected_rows=written" in source


class TestThePostProcessorWasAudited:
    """Task 5.3's second clause. The audit conclusion is that post-processing is not a
    projection — it rewrites entity values in memory and writes no relational rows — so
    there are no two row counts to disagree. What it does have is a provider call, and
    that is measured on the LLM families instead."""

    def test_the_postprocessor_writes_no_relational_rows(self):
        import inspect

        from src.extraction_service.services import entity_postprocessor

        source = inspect.getsource(entity_postprocessor)

        assert "project_document_entities" not in source
        assert "record_projection" not in source

    def test_its_provider_call_is_measured_under_its_own_operation(self):
        assert "entity_postprocess" in dm.LLM_OPERATIONS

        import inspect

        from src.extraction_service.services import entity_postprocessor

        assert "_record_call(" in inspect.getsource(entity_postprocessor.call_postprocessor)
