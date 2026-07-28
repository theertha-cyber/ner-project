from src.shared.retrieval.eval.metrics import (
    Judgment,
    RankedItem,
    aggregate,
    compute_query_metrics,
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def _ranked(*keys: tuple[str, int]) -> list[RankedItem]:
    return [RankedItem(document_id=d, chunk_index=c) for d, c in keys]


def _judgments(*entries: tuple[str, int, int]) -> list[Judgment]:
    return [Judgment(document_id=d, chunk_index=c, grade=g) for d, c, g in entries]


class TestPerfectRanking:
    """Covers verification.md row 27."""

    def test_perfect_ranking_scores_one(self):
        judgments = _judgments(("doc-a", 0, 3), ("doc-a", 1, 2), ("doc-a", 2, 1))
        ranked = _ranked(("doc-a", 0), ("doc-a", 1), ("doc-a", 2))

        assert recall_at_k(ranked, judgments, 5) == 1.0
        assert ndcg_at_k(ranked, judgments, 5) == 1.0
        assert mrr_at_k(ranked, judgments, 5) == 1.0


class TestEmptyResults:
    """Covers verification.md row 28."""

    def test_empty_results_score_zero(self):
        judgments = _judgments(("doc-a", 0, 2))
        ranked: list[RankedItem] = []

        assert recall_at_k(ranked, judgments, 5) == 0.0
        assert precision_at_k(ranked, judgments, 5) == 0.0
        assert mrr_at_k(ranked, judgments, 5) == 0.0
        assert ndcg_at_k(ranked, judgments, 5) == 0.0


class TestRankSensitivity:
    """Covers verification.md row 29."""

    def test_rank_position_affects_mrr_ndcg_not_recall(self):
        judgments = _judgments(("doc-a", 0, 1))
        rank_one = _ranked(("doc-a", 0), ("x", 1), ("x", 2), ("x", 3), ("x", 4))
        rank_four = _ranked(("x", 1), ("x", 2), ("x", 3), ("doc-a", 0), ("x", 4))

        assert recall_at_k(rank_one, judgments, 5) == recall_at_k(rank_four, judgments, 5)
        assert mrr_at_k(rank_one, judgments, 5) > mrr_at_k(rank_four, judgments, 5)
        assert ndcg_at_k(rank_one, judgments, 5) > ndcg_at_k(rank_four, judgments, 5)


class TestGradedRelevance:
    """Covers verification.md row 30."""

    def test_graded_relevance_ordering(self):
        judgments = _judgments(("a", 0, 3), ("b", 0, 1))
        high_first = _ranked(("a", 0), ("b", 0))
        low_first = _ranked(("b", 0), ("a", 0))

        assert ndcg_at_k(high_first, judgments, 5) > ndcg_at_k(low_first, judgments, 5)


class TestZeroJudgmentQuerySkipped:
    """Covers verification.md row 31."""

    def test_zero_judgment_query_excluded_from_aggregate(self):
        with_judgments = compute_query_metrics("q1", _ranked(("a", 0)), _judgments(("a", 0, 1)), 5)
        without_judgments = compute_query_metrics("q2", _ranked(("a", 0)), [], 5)

        assert without_judgments.skipped is True
        assert without_judgments.skip_reason

        agg = aggregate([with_judgments, without_judgments])
        assert agg.query_count == 1
        assert agg.skipped == ["q2"]
