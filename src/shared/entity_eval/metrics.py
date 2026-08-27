"""Entity-level metrics, including the one that decides whether a configuration ships.

The objective is a structured representation that downstream retrieval can rely on, not
values that look tidier. Precision, recall and F1 measure whether the right facts are
present; hallucination rate measures whether anything untrue was added, and it is a
release gate rather than a number to trade against F1."""

from dataclasses import dataclass, field

from src.extraction_service.services.entity_normalizer import fold_text


@dataclass
class EntityMetrics:
    configuration: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    type_correct: int = 0
    type_total: int = 0
    exact_value_correct: int = 0
    exact_value_total: int = 0
    unsupported_values: int = 0
    unanchored_entities: int = 0
    produced_entities: int = 0
    per_class: dict = field(default_factory=dict)

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        if not (self.precision + self.recall):
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)

    @property
    def entity_type_accuracy(self) -> float:
        return self.type_correct / self.type_total if self.type_total else 0.0

    @property
    def exact_value_accuracy(self) -> float:
        return self.exact_value_correct / self.exact_value_total if self.exact_value_total else 0.0

    @property
    def hallucination_rate(self) -> float:
        """Entities with no textual support, plus entities tracing to no BERT candidate,
        over everything produced. Any value above zero blocks the configuration."""
        if not self.produced_entities:
            return 0.0
        return (self.unsupported_values + self.unanchored_entities) / self.produced_entities

    def as_dict(self) -> dict:
        return {
            "configuration": self.configuration,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "exact_value_accuracy": round(self.exact_value_accuracy, 4),
            "entity_type_accuracy": round(self.entity_type_accuracy, 4),
            "hallucination_rate": round(self.hallucination_rate, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "unsupported_values": self.unsupported_values,
            "unanchored_entities": self.unanchored_entities,
            "produced_entities": self.produced_entities,
            "per_class": self.per_class,
        }


def _comparable(value: str) -> str:
    return " ".join(fold_text(value or "").casefold().split())


def _key(entity_type: str, value: str) -> tuple[str, str]:
    return ((entity_type or "").upper(), _comparable(value))


def score_case(
    metrics: EntityMetrics,
    produced: list,
    expected: list,
    source_text: str,
    anchored_values: set[str] | None = None,
    failure_class: str = "",
) -> None:
    """Folds one case into the running totals.

    Matching is on `(entity_type, folded value)`. Folding is used deliberately: a
    configuration is not credited or penalised for a zero-width space, because that is
    what the deterministic layer exists to remove, and leaving it in the comparison
    would make the Unicode fix look like an accuracy gain it is not."""
    expected_keys = {_key(e.entity_type, e.entity_value) for e in expected}
    produced_keys = [_key(p.entity_type, p.entity_value) for p in produced]

    matched = set()
    for produced_key in produced_keys:
        if produced_key in expected_keys:
            matched.add(produced_key)
            metrics.true_positives += 1
        else:
            metrics.false_positives += 1
    metrics.false_negatives += len(expected_keys - matched)

    metrics.produced_entities += len(produced)

    comparable_source = _comparable(source_text)
    for entity in produced:
        if _comparable(entity.entity_value) not in comparable_source:
            metrics.unsupported_values += 1
        if anchored_values is not None and _comparable(entity.entity_value) not in anchored_values:
            metrics.unanchored_entities += 1

    # Type and exact-value accuracy are scored over the expected set, pairing each
    # expectation with the produced entity whose value matches it.
    produced_by_value: dict[str, list] = {}
    for entity in produced:
        produced_by_value.setdefault(_comparable(entity.entity_value), []).append(entity)

    for expectation in expected:
        metrics.type_total += 1
        metrics.exact_value_total += 1
        candidates = produced_by_value.get(_comparable(expectation.entity_value), [])
        if candidates:
            metrics.exact_value_correct += 1
            if any((c.entity_type or "").upper() == expectation.entity_type.upper() for c in candidates):
                metrics.type_correct += 1

    if failure_class:
        bucket = metrics.per_class.setdefault(failure_class, {"cases": 0, "expected_matched": 0, "expected_total": 0})
        bucket["cases"] += 1
        bucket["expected_total"] += len(expected_keys)
        bucket["expected_matched"] += len(matched)


def compare(baseline: EntityMetrics, candidate: EntityMetrics) -> dict:
    """The delta between two adjacent configurations.

    Reporting adjacent pairs rather than only first-versus-last is what keeps the
    deterministic repairs' gains from being credited to the LLM — with a two-arm
    comparison those fixes would inflate the post-processor's apparent value."""
    return {
        "from": baseline.configuration,
        "to": candidate.configuration,
        "precision": round(candidate.precision - baseline.precision, 4),
        "recall": round(candidate.recall - baseline.recall, 4),
        "f1": round(candidate.f1 - baseline.f1, 4),
        "exact_value_accuracy": round(candidate.exact_value_accuracy - baseline.exact_value_accuracy, 4),
        "entity_type_accuracy": round(candidate.entity_type_accuracy - baseline.entity_type_accuracy, 4),
        "hallucination_rate": round(candidate.hallucination_rate - baseline.hallucination_rate, 4),
    }
