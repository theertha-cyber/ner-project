import json
from dataclasses import dataclass
from pathlib import Path

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


def check_regression(observed: dict, baseline: dict, tolerance: float) -> GateResult:
    """`observed` and `baseline` are aggregate-metric-shaped dicts (e.g. AggregateMetrics
    as a dict) containing at least `recall_at_k` and `ndcg_at_k`."""
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
