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


@dataclass
class QueryMetrics:
    query_id: str
    recall_at_k: float
    precision_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class AggregateMetrics:
    query_count: int
    recall_at_k: float
    precision_at_k: float
    mrr_at_k: float
    ndcg_at_k: float
    skipped: list[str] = field(default_factory=list)


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


def aggregate(per_query: list[QueryMetrics]) -> AggregateMetrics:
    scored = [m for m in per_query if not m.skipped]
    skipped = [m.query_id for m in per_query if m.skipped]
    n = len(scored)
    if n == 0:
        return AggregateMetrics(query_count=0, recall_at_k=0.0, precision_at_k=0.0, mrr_at_k=0.0, ndcg_at_k=0.0, skipped=skipped)
    return AggregateMetrics(
        query_count=n,
        recall_at_k=sum(m.recall_at_k for m in scored) / n,
        precision_at_k=sum(m.precision_at_k for m in scored) / n,
        mrr_at_k=sum(m.mrr_at_k for m in scored) / n,
        ndcg_at_k=sum(m.ndcg_at_k for m in scored) / n,
        skipped=skipped,
    )
