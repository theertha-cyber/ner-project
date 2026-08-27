"""Replays the fixture through three pipeline configurations and gates the result.

Three arms, not two. `BERT_ONLY` reproduces the pipeline as it behaved before this
change; `BERT_REPAIRS` adds the deterministic fixes; `BERT_REPAIRS_POSTPROCESS` adds the
LLM stage. Only the delta between the last two is the post-processor's contribution —
comparing the first and last would credit it with the regex fixes as well.
"""

from dataclasses import dataclass, field
from typing import Callable

from src.extraction_service.services import entity_normalizer, entity_postprocessor
from src.extraction_service.services.entity_normalizer import (
    collapse_duplicates,
    filter_valid_entities,
    merge_wordpieces,
    reconstruct_entities,
)
from src.extraction_service.services.semantic_normalizer import (
    EntityTypeConfig,
    apply_semantic_normalization,
)
from src.shared.config import settings
from src.shared.entity_eval.fixture import FixtureCase, token_records
from src.shared.entity_eval.metrics import EntityMetrics, _comparable, compare, score_case

BERT_ONLY = "bert_only"
BERT_REPAIRS = "bert_repairs"
BERT_REPAIRS_POSTPROCESS = "bert_repairs_postprocess"
CONFIGURATIONS = (BERT_ONLY, BERT_REPAIRS, BERT_REPAIRS_POSTPROCESS)


def _type_config(case: FixtureCase) -> dict:
    return {
        name.lower(): EntityTypeConfig(
            value_kind=spec.get("value_kind"), value_unit=spec.get("value_unit")
        )
        for name, spec in (case.entity_type_config or {}).items()
    }


def _run_deterministic(case: FixtureCase, repairs_enabled: bool) -> list:
    """The deterministic half of the pipeline.

    With `repairs_enabled=False` the pre-change behaviour is reproduced by disabling the
    gap tolerance, skipping the token-record fill, and skipping the validity gate and
    duplicate collapse — the three places the repairs changed what reaches the database."""
    records = token_records(case)
    merged = merge_wordpieces(case.predictions)

    if repairs_enabled:
        entities = reconstruct_entities(merged, records)
    else:
        original_gap = settings.max_entity_word_gap
        original_fold = entity_normalizer.fold_text
        try:
            settings.max_entity_word_gap = 0
            # The pre-change canonicalizer did not strip format characters or fold
            # typographic punctuation.
            entity_normalizer.fold_text = lambda value: value
            entities = reconstruct_entities(merged)
        finally:
            settings.max_entity_word_gap = original_gap
            entity_normalizer.fold_text = original_fold

    entities, _ = apply_semantic_normalization(entities, _type_config(case))

    if repairs_enabled:
        entities, _ = filter_valid_entities(entities)
        entities = collapse_duplicates(entities)
    return entities


@dataclass
class RunResult:
    metrics: dict[str, EntityMetrics] = field(default_factory=dict)
    deltas: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "configurations": [self.metrics[name].as_dict() for name in CONFIGURATIONS if name in self.metrics],
            "deltas": self.deltas,
        }


def run_fixture(
    cases: list[FixtureCase],
    postprocess_call: Callable[[str, str], tuple[object, int]] | None = None,
) -> RunResult:
    """Scores every configuration over every case.

    `postprocess_call` stands in for the provider so the harness is runnable without
    spending tokens; passing None scores the post-processing arm identically to the
    repairs arm, which is the honest result for "no post-processor available"."""
    result = RunResult()
    for name in CONFIGURATIONS:
        result.metrics[name] = EntityMetrics(configuration=name)

    for case in cases:
        baseline_entities = _run_deterministic(case, repairs_enabled=False)
        repaired_entities = _run_deterministic(case, repairs_enabled=True)

        score_case(
            result.metrics[BERT_ONLY], baseline_entities, case.expected,
            case.source_text, failure_class=case.failure_class,
        )
        score_case(
            result.metrics[BERT_REPAIRS], repaired_entities, case.expected,
            case.source_text, failure_class=case.failure_class,
        )

        # What the post-processor was actually shown. An entity it returns that is not
        # a correction of one of these traces to no BERT candidate, which is the second
        # half of the hallucination definition.
        anchored = {
            _comparable(e.entity_value)
            for e in _run_deterministic(case, repairs_enabled=True)
        }

        if postprocess_call is None:
            postprocessed = _run_deterministic(case, repairs_enabled=True)
        else:
            postprocessed = _run_postprocess(case, postprocess_call)
            anchored |= {_comparable(e.entity_value) for e in postprocessed if e.source_entity_value}

        score_case(
            result.metrics[BERT_REPAIRS_POSTPROCESS], postprocessed, case.expected,
            case.source_text, anchored_values=anchored, failure_class=case.failure_class,
        )

    result.deltas = [
        compare(result.metrics[BERT_ONLY], result.metrics[BERT_REPAIRS]),
        compare(result.metrics[BERT_REPAIRS], result.metrics[BERT_REPAIRS_POSTPROCESS]),
    ]
    return result


def _run_postprocess(case: FixtureCase, postprocess_call) -> list:
    entities = _run_deterministic(case, repairs_enabled=True)
    original_call = entity_postprocessor.call_postprocessor
    entity_postprocessor.call_postprocessor = postprocess_call
    try:
        outcome, _ = entity_postprocessor.postprocess_document(
            entities,
            token_records(case),
            _type_config(case),
            {name.upper() for name in (case.entity_type_config or {})} or
            {(e.entity_type or "").upper() for e in case.expected},
        )
    finally:
        entity_postprocessor.call_postprocessor = original_call
    return outcome.entities


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    configuration: str = BERT_REPAIRS_POSTPROCESS
    postprocess_model: str | None = None
    postprocess_prompt_version: str | None = None

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "configuration": self.configuration,
            "postprocess_model": self.postprocess_model,
            "postprocess_prompt_version": self.postprocess_prompt_version,
        }


def evaluate_gate(
    result: RunResult,
    structured_query_success: dict[str, float] | None = None,
) -> GateResult:
    """Whether the post-processing configuration may be offered as a processing mode.

    Two conditions, both necessary: zero hallucination on the fixture, and no regression
    in structured-query success against the repairs-only arm. An F1 improvement on its
    own is explicitly not sufficient — the objective is a structured representation
    downstream retrieval can rely on, not values that read better."""
    reasons: list[str] = []
    candidate = result.metrics.get(BERT_REPAIRS_POSTPROCESS)
    baseline = result.metrics.get(BERT_REPAIRS)

    if candidate is None or baseline is None:
        return GateResult(passed=False, reasons=["evaluation did not produce both configurations"])

    if candidate.hallucination_rate > 0:
        reasons.append(
            f"hallucination rate is {candidate.hallucination_rate:.4f}; it must be zero "
            f"({candidate.unsupported_values} unsupported value(s), "
            f"{candidate.unanchored_entities} unanchored entity/entities)"
        )

    if structured_query_success:
        before = structured_query_success.get(BERT_REPAIRS)
        after = structured_query_success.get(BERT_REPAIRS_POSTPROCESS)
        if before is not None and after is not None and after < before:
            reasons.append(
                f"structured-query success regressed from {before:.4f} to {after:.4f}"
            )

    return GateResult(
        passed=not reasons,
        reasons=reasons,
        postprocess_model=settings.azure_openai_chat_deployment,
        postprocess_prompt_version=settings.postprocess_prompt_version,
    )
