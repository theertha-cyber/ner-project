import json
from dataclasses import dataclass
from pathlib import Path

from src.shared.retrieval.eval.metrics import LEGACY_SCORING_RULE, SCORING_RULE

GATED_METRICS = ("recall_at_k", "ndcg_at_k")


class BaselineNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class MetricDelta:
    metric: str
    baseline: float
    observed: float

    @property
    def delta(self) -> float:
        return self.observed - self.baseline

    @property
    def regressed(self) -> bool:
        return self.delta < 0


@dataclass(frozen=True)
class GateResult:
    passed: bool
    deltas: list[MetricDelta]
    message: str


def load_baseline(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise BaselineNotFoundError(
            f"no baseline metrics file found at '{path}'. Generate one by running the full "
            "eval matrix for the default configuration and committing its aggregate metrics "
            "as this file — see design.md Migration Plan step 6."
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _comparability_failure(observed: dict, baseline: dict) -> str | None:
    """A score only means something relative to the rule that produced it and the corpus
    it ran against. Comparing across either is comparing two different measurements, so
    the gate refuses rather than reporting a delta nobody can act on."""
    observed_rule = observed.get("scoring_rule", SCORING_RULE)
    baseline_rule = baseline.get("scoring_rule")
    if baseline_rule is None:
        return (
            "baseline records no scoring rule, so it predates the current one "
            f"('{observed_rule}'). Regenerate it — a baseline produced under "
            f"'{LEGACY_SCORING_RULE}' excluded degraded and failed queries from the mean, "
            "and its numbers are not comparable with a run that scores them zero."
        )
    if baseline_rule != observed_rule:
        return (
            f"scoring rule mismatch: baseline='{baseline_rule}' observed='{observed_rule}'. "
            "Regenerate the baseline under the current rule."
        )

    observed_corpus = observed.get("corpus")
    baseline_corpus = baseline.get("corpus")
    if observed_corpus is not None and baseline_corpus is not None and observed_corpus != baseline_corpus:
        return (
            f"corpus mismatch: baseline='{baseline_corpus}' observed='{observed_corpus}'. "
            "A score against one corpus is not evidence about another."
        )
    return None


def check_regression(observed: dict, baseline: dict, tolerance: float) -> GateResult:
    """`observed` and `baseline` are aggregate-metric-shaped dicts (e.g. AggregateMetrics
    as a dict) containing at least `recall_at_k` and `ndcg_at_k`, plus the `scoring_rule`
    and `corpus` that produced them."""
    incomparable = _comparability_failure(observed, baseline)
    if incomparable:
        return GateResult(passed=False, deltas=[], message=f"Regression gate rejected: {incomparable}")

    deltas = [
        MetricDelta(metric=m, baseline=baseline[m], observed=observed[m])
        for m in GATED_METRICS
    ]

    failing = [d for d in deltas if d.delta < -tolerance]
    if failing:
        lines = [
            f"{d.metric}: baseline={d.baseline:.4f} observed={d.observed:.4f} delta={d.delta:+.4f} (tolerance={tolerance})"
            for d in failing
        ]
        return GateResult(passed=False, deltas=deltas, message="Regression gate failed:\n" + "\n".join(lines))

    improvements = [d for d in deltas if d.delta > 0]
    if improvements:
        lines = [f"{d.metric}: {d.baseline:.4f} -> {d.observed:.4f} ({d.delta:+.4f})" for d in improvements]
        return GateResult(passed=True, deltas=deltas, message="Regression gate passed. Improvements:\n" + "\n".join(lines))

    return GateResult(passed=True, deltas=deltas, message="Regression gate passed.")
