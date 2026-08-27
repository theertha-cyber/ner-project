"""Covers verification.md rows 100-101.

nDCG and recall@k say whether the right chunk ranked highly. Neither says whether the
generated SQL actually retrieved the rows a structured question needed — which is the
thing entity quality determines, and the thing that silently failed when a zero-width
space made 5 of 7 matching rows unreachable by equality."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.shared.retrieval.eval.metrics import (
    STRUCTURED_QUERY_CLASSES,
    QueryMetrics,
    aggregate,
    structured_query_success_rate,
    zero_metrics,
)


def _metrics(query_id, recall=1.0, degraded=False, failed=False, skipped=False):
    return QueryMetrics(
        query_id=query_id,
        recall_at_k=recall,
        precision_at_k=recall,
        mrr_at_k=recall,
        ndcg_at_k=recall,
        skipped=skipped,
        degraded=degraded,
        failed=failed,
    )


class TestStructuredQuerySuccessIsReported:
    """Row 100."""

    def test_the_rate_covers_the_structured_query_classes(self):
        per_query = [
            _metrics("q1"),
            _metrics("q2"),
            _metrics("q3", recall=0.0),
        ]
        classes = {
            "q1": "simple_structured",
            "q2": "exact_entity_lookup",
            "q3": "attribute_filtering",
        }

        rate, count = structured_query_success_rate(per_query, classes)

        assert count == 3
        assert rate == pytest.approx(2 / 3)

    def test_every_structured_class_is_recognised(self):
        assert set(STRUCTURED_QUERY_CLASSES) == {
            "simple_structured", "exact_entity_lookup", "attribute_filtering"
        }

    def test_non_structured_classes_are_excluded(self):
        per_query = [_metrics("q1"), _metrics("q2", recall=0.0)]
        classes = {"q1": "simple_structured", "q2": "document_content"}

        rate, count = structured_query_success_rate(per_query, classes)

        assert count == 1
        assert rate == 1.0

    def test_the_aggregate_surfaces_the_rate(self):
        per_query = [_metrics("q1"), _metrics("q2", recall=0.0)]
        classes = {"q1": "simple_structured", "q2": "exact_entity_lookup"}

        agg = aggregate(per_query, classes)

        assert agg.structured_query_count == 2
        assert agg.structured_query_success == pytest.approx(0.5)

    def test_the_aggregate_is_unchanged_for_callers_that_pass_no_classes(self):
        per_query = [_metrics("q1"), _metrics("q2")]

        agg = aggregate(per_query)

        assert agg.structured_query_count == 0
        assert agg.structured_query_success == 0.0
        assert agg.recall_at_k == pytest.approx(1.0)


class TestUnreachableRowsScoreAsFailures:
    """Row 101 — the zero-width-space shape."""

    def test_a_query_whose_rows_exist_but_are_unreachable_scores_zero(self):
        """Expected rows exist in `document_entities`; the equality predicate missed
        them, so recall is 0 and the query is a failure, not a partial success."""
        per_query = [_metrics("unreachable", recall=0.0)]
        classes = {"unreachable": "exact_entity_lookup"}

        rate, count = structured_query_success_rate(per_query, classes)

        assert count == 1
        assert rate == 0.0

    def test_a_partially_recalled_structured_query_is_not_a_success(self):
        per_query = [_metrics("partial", recall=0.5)]
        classes = {"partial": "attribute_filtering"}

        rate, _ = structured_query_success_rate(per_query, classes)

        assert rate == 0.0

    def test_a_failed_query_is_not_a_success(self):
        per_query = [zero_metrics("boom", failed=True, failure_reason="sql error")]
        classes = {"boom": "simple_structured"}

        rate, count = structured_query_success_rate(per_query, classes)

        assert count == 1
        assert rate == 0.0

    def test_a_degraded_query_is_not_a_success(self):
        per_query = [_metrics("degraded", recall=1.0, degraded=True)]
        classes = {"degraded": "simple_structured"}

        rate, _ = structured_query_success_rate(per_query, classes)

        assert rate == 0.0

    def test_a_skipped_query_leaves_the_denominator(self):
        per_query = [_metrics("skipped", skipped=True), _metrics("ok")]
        classes = {"skipped": "simple_structured", "ok": "simple_structured"}

        rate, count = structured_query_success_rate(per_query, classes)

        assert count == 1
        assert rate == 1.0

    def test_no_structured_queries_reports_zero_count(self):
        per_query = [_metrics("q1")]

        rate, count = structured_query_success_rate(per_query, {"q1": "document_content"})

        assert (rate, count) == (0.0, 0)
