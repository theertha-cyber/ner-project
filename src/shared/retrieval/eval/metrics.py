import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Judgment:
    document_id: str
    chunk_index: int
    grade: int


@dataclass(frozen=True)
class RankedItem:
    document_id: str
    chunk_index: int


def _grade_map(judgments: list[Judgment]) -> dict[tuple[str, int], int]:
    return {(j.document_id, j.chunk_index): j.grade for j in judgments}


def recall_at_k(ranked: list[RankedItem], judgments: list[Judgment], k: int) -> float:
    relevant_keys = {(j.document_id, j.chunk_index) for j in judgments if j.grade >= 1}
    if not relevant_keys:
        return 0.0
    top_k_keys = {(r.document_id, r.chunk_index) for r in ranked[:k]}
    hit = len(relevant_keys & top_k_keys)
    return hit / len(relevant_keys)


def precision_at_k(ranked: list[RankedItem], judgments: list[Judgment], k: int) -> float:
    if k <= 0 or not ranked:
        return 0.0
    relevant_keys = {(j.document_id, j.chunk_index) for j in judgments if j.grade >= 1}
    top_k = ranked[:k]
    if not top_k:
        return 0.0
    hit = sum(1 for r in top_k if (r.document_id, r.chunk_index) in relevant_keys)
    return hit / len(top_k)


def mrr_at_k(ranked: list[RankedItem], judgments: list[Judgment], k: int) -> float:
    relevant_keys = {(j.document_id, j.chunk_index) for j in judgments if j.grade >= 1}
    if not relevant_keys:
        return 0.0
    for rank, r in enumerate(ranked[:k], start=1):
        if (r.document_id, r.chunk_index) in relevant_keys:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: list[RankedItem], judgments: list[Judgment], k: int) -> float:
    grades = _grade_map(judgments)
    if not grades or not any(g >= 1 for g in grades.values()):
        return 0.0

    dcg = 0.0
    for i, r in enumerate(ranked[:k], start=1):
        grade = grades.get((r.document_id, r.chunk_index), 0)
        if grade:
            dcg += (2**grade - 1) / math.log2(i + 1)

    ideal_grades = sorted(grades.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 1) for i, g in enumerate(ideal_grades, start=1) if g)
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


# Scoring rules are versioned because they change what a score MEANS, and a comparison
# across rules is meaningless. Under `skip-degraded` a query whose run degraded or
# errored was marked skipped and excluded from the mean — so a configuration that broke
# on half the golden set scored as well as one that answered all of it, and the
# regression gate could not fail. Under `zero-degraded` those queries score zero and
# stay in the denominator.
SCORING_RULE = "zero-degraded"
LEGACY_SCORING_RULE = "skip-degraded"


@dataclass
class QueryMetrics:
    query_id: str
    recall_at_k: float
    precision_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    # Reserved for queries that were never dispatched for a reason unrelated to system
    # behaviour — a case with no judgments, for instance. A run that degraded, errored,
    # or was abandoned is NOT skipped: it is a zero.
    skipped: bool = False
    skip_reason: str | None = None
    degraded: bool = False
    failed: bool = False
    failure_reason: str | None = None


def zero_metrics(query_id: str, *, degraded: bool = False, failed: bool = False,
                 failure_reason: str | None = None) -> QueryMetrics:
    """A dispatched query that produced nothing usable. Scores zero and counts."""
    return QueryMetrics(
        query_id=query_id, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
        skipped=False, degraded=degraded, failed=failed, failure_reason=failure_reason,
    )


@dataclass
class AggregateMetrics:
    query_count: int
    recall_at_k: float
    precision_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    skipped: list[str] = field(default_factory=list)
    degraded_count: int = 0
    failed_count: int = 0
    scoring_rule: str = SCORING_RULE
    # Share of the structured query classes whose generated SQL returned the expected
    # rows. Entity-quality work is scored on this, not on how tidy the stored values
    # look: a value can read perfectly and still be unreachable by the predicate a SQL
    # generator writes, which is exactly what a zero-width space did to 5 of 7 rows.
    structured_query_success: float = 0.0
    structured_query_count: int = 0


# Golden-set classes whose expected answer requires `document_entities`.
STRUCTURED_QUERY_CLASSES = ("simple_structured", "exact_entity_lookup", "attribute_filtering")


def structured_query_success_rate(
    per_query: list[QueryMetrics],
    query_class_by_id: dict[str, str] | None = None,
) -> tuple[float, int]:
    """Fraction of dispatched structured queries that retrieved their expected rows.

    A query counts as a success only when it was dispatched, did not fail or degrade, and
    recalled every judged item — a partially answered structured lookup is a wrong answer
    to the user, not a partial credit."""
    if not query_class_by_id:
        return 0.0, 0
    structured = [
        m for m in per_query
        if not m.skipped and query_class_by_id.get(m.query_id) in STRUCTURED_QUERY_CLASSES
    ]
    if not structured:
        return 0.0, 0
    successes = sum(
        1 for m in structured
        if not m.failed and not m.degraded and m.recall_at_k >= 1.0
    )
    return successes / len(structured), len(structured)


def compute_query_metrics(query_id: str, ranked: list[RankedItem], judgments: list[Judgment], k: int) -> QueryMetrics:
    if not judgments:
        return QueryMetrics(
            query_id=query_id, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
            skipped=True, skip_reason="no judgments for this query",
        )
    return QueryMetrics(
        query_id=query_id,
        recall_at_k=recall_at_k(ranked, judgments, k),
        precision_at_k=precision_at_k(ranked, judgments, k),
        mrr_at_k=mrr_at_k(ranked, judgments, k),
        ndcg_at_k=ndcg_at_k(ranked, judgments, k),
    )


def aggregate(
    per_query: list[QueryMetrics],
    query_class_by_id: dict[str, str] | None = None,
) -> AggregateMetrics:
    """Means over every DISPATCHED query. A degraded or failed run contributes its zero
    rather than dropping out of the denominator, so a configuration that breaks on half
    the golden set can no longer score the same as one that answers all of it.

    `query_class_by_id` is optional so existing callers are unaffected; supplying it adds
    the structured-query success rate."""
    scored = [m for m in per_query if not m.skipped]
    skipped = [m.query_id for m in per_query if m.skipped]
    degraded_count = sum(1 for m in scored if m.degraded)
    failed_count = sum(1 for m in scored if m.failed)
    structured_rate, structured_count = structured_query_success_rate(per_query, query_class_by_id)
    n = len(scored)
    if n == 0:
        return AggregateMetrics(
            query_count=0, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0,
            skipped=skipped, degraded_count=degraded_count, failed_count=failed_count,
            structured_query_success=structured_rate, structured_query_count=structured_count,
        )
    return AggregateMetrics(
        query_count=n,
        recall_at_k=sum(m.recall_at_k for m in scored) / n,
        precision_at_k=sum(m.precision_at_k for m in scored) / n,
        mrr_at_k=sum(m.mrr_at_k for m in scored) / n,
        ndcg_at_k=sum(m.ndcg_at_k for m in scored) / n,
        skipped=skipped,
        degraded_count=degraded_count,
        failed_count=failed_count,
        structured_query_success=structured_rate,
        structured_query_count=structured_count,
    )
