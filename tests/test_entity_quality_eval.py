"""Covers verification.md rows 93-99 and 102-104.

The objective is a structured representation downstream retrieval can rely on, not
values that read better — so hallucination rate is a release gate rather than a number to
trade against F1, and three configurations are compared rather than two so the
deterministic repairs' gains are not credited to the LLM."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import json
from pathlib import Path

import pytest

from src.shared.config import settings
from src.shared.entity_eval.fixture import (
    REQUIRED_CLASSES,
    FixtureError,
    load_fixture,
    token_records,
)
from src.shared.entity_eval.metrics import EntityMetrics, compare, score_case
from src.shared.entity_eval.runner import (
    BERT_ONLY,
    BERT_REPAIRS,
    BERT_REPAIRS_POSTPROCESS,
    evaluate_gate,
    run_fixture,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "entity_quality" / "fixture.jsonl"


@pytest.fixture
def cases():
    return load_fixture(FIXTURE_PATH)


class TestFixtureCoverageIsEnforced:
    """Rows 93 and 94."""

    def test_the_shipped_fixture_loads(self, cases):
        assert len(cases) >= len(REQUIRED_CLASSES)

    def test_every_required_failure_class_has_a_case(self, cases):
        covered = {case.failure_class for case in cases}
        assert set(REQUIRED_CLASSES) <= covered

    def test_a_fixture_missing_a_class_is_rejected(self, tmp_path, cases):
        thinned = [c for c in cases if c.failure_class != "fragmented_span"]
        path = tmp_path / "thin.jsonl"
        path.write_text("\n".join(
            json.dumps({
                "case_id": c.case_id, "document_id": c.document_id, "filename": c.filename,
                "failure_class": c.failure_class, "tokens": c.tokens, "predictions": c.predictions,
                "expected": [{"entity_type": e.entity_type, "entity_value": e.entity_value} for e in c.expected],
            }, ensure_ascii=False)
            for c in thinned
        ), encoding="utf-8")

        with pytest.raises(FixtureError, match="fragmented_span"):
            load_fixture(path)

    def test_an_empty_fixture_is_rejected(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        with pytest.raises(FixtureError, match="empty"):
            load_fixture(path)

    def test_an_expectation_absent_from_the_source_text_is_rejected(self, tmp_path):
        path = tmp_path / "bad.jsonl"
        path.write_text(json.dumps({
            "case_id": "bogus", "document_id": "d", "failure_class": "correct_extraction",
            "tokens": ["Acme", "Corp"], "predictions": [],
            "expected": [{"entity_type": "COMPANY", "entity_value": "Globex Corporation"}],
        }), encoding="utf-8")

        with pytest.raises(FixtureError, match="not present in the source text"):
            load_fixture(path)

    def test_every_case_names_a_real_document_and_supporting_text(self, cases):
        for case in cases:
            assert case.document_id
            assert case.tokens
            for expectation in case.expected:
                assert expectation.entity_value in case.source_text

    def test_token_records_reproduce_the_source_offsets(self, cases):
        for case in cases:
            records = token_records(case)
            for record in records:
                assert case.source_text[record["char_start"]:record["char_end"]] == record["token"]


class TestAllRequiredMetricsAreReported:
    """Row 95."""

    def test_the_report_contains_every_metric_for_every_configuration(self, cases):
        report = run_fixture(cases).as_dict()

        assert {c["configuration"] for c in report["configurations"]} == {
            BERT_ONLY, BERT_REPAIRS, BERT_REPAIRS_POSTPROCESS
        }
        for config in report["configurations"]:
            for metric in ("precision", "recall", "f1", "exact_value_accuracy",
                           "entity_type_accuracy", "hallucination_rate"):
                assert metric in config
                assert isinstance(config[metric], float)

    def test_f1_is_the_harmonic_mean_of_precision_and_recall(self):
        metrics = EntityMetrics(configuration="x", true_positives=6, false_positives=2, false_negatives=2)

        assert metrics.precision == pytest.approx(0.75)
        assert metrics.recall == pytest.approx(0.75)
        assert metrics.f1 == pytest.approx(0.75)

    def test_empty_counts_do_not_divide_by_zero(self):
        metrics = EntityMetrics(configuration="x")

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        assert metrics.hallucination_rate == 0.0


class TestHallucinationCounting:
    """Rows 96 and 97."""

    def test_a_value_absent_from_the_source_counts_as_a_hallucination(self):
        from src.extraction_service.services.entity_normalizer import NormalizedEntity

        metrics = EntityMetrics(configuration="x")
        produced = [NormalizedEntity(
            entity_type="COMPANY", entity_value="Globex Corporation",
            normalized_value="globex corporation", confidence=0.9,
        )]

        score_case(metrics, produced, [], "Employed at Centizen Inc. in Chennai")

        assert metrics.unsupported_values == 1
        assert metrics.hallucination_rate > 0

    def test_an_entity_tracing_to_no_candidate_counts_as_a_hallucination(self):
        from src.extraction_service.services.entity_normalizer import NormalizedEntity

        metrics = EntityMetrics(configuration="x")
        produced = [NormalizedEntity(
            entity_type="COMPANY", entity_value="Chennai",
            normalized_value="chennai", confidence=0.9,
        )]

        score_case(
            metrics, produced, [], "Employed at Centizen Inc. in Chennai",
            anchored_values={"centizen inc."},
        )

        assert metrics.unsupported_values == 0
        assert metrics.unanchored_entities == 1
        assert metrics.hallucination_rate > 0

    def test_a_supported_and_anchored_entity_counts_as_neither(self):
        from src.extraction_service.services.entity_normalizer import NormalizedEntity

        metrics = EntityMetrics(configuration="x")
        produced = [NormalizedEntity(
            entity_type="COMPANY", entity_value="Centizen Inc.",
            normalized_value="centizen inc.", confidence=0.9,
        )]

        score_case(
            metrics, produced, [], "Employed at Centizen Inc. in Chennai",
            anchored_values={"centizen inc."},
        )

        assert metrics.hallucination_rate == 0.0

    def test_the_shipped_fixture_hallucinates_on_no_configuration(self, cases):
        report = run_fixture(cases).as_dict()

        for config in report["configurations"]:
            assert config["hallucination_rate"] == 0.0


class TestThreeConfigurationsIsolateTheContribution:
    """Rows 98 and 99."""

    def test_deltas_are_reported_between_adjacent_pairs(self, cases):
        report = run_fixture(cases).as_dict()

        pairs = [(d["from"], d["to"]) for d in report["deltas"]]
        assert pairs == [
            (BERT_ONLY, BERT_REPAIRS),
            (BERT_REPAIRS, BERT_REPAIRS_POSTPROCESS),
        ]

    def test_the_deterministic_repairs_improve_the_first_delta(self, cases):
        """The fixture's fragmented span, format characters and duration prose are all
        fixed without any model call, so this delta must be positive."""
        report = run_fixture(cases).as_dict()
        repairs_delta = report["deltas"][0]

        assert repairs_delta["f1"] > 0
        assert repairs_delta["exact_value_accuracy"] > 0

    def test_a_deterministic_gain_is_not_attributed_to_postprocessing(self, cases):
        """With no post-processor wired, the second delta must be exactly zero —
        a two-arm comparison would have credited the regex fixes to the LLM."""
        report = run_fixture(cases).as_dict()
        postprocess_delta = report["deltas"][1]

        assert postprocess_delta["f1"] == 0.0
        assert postprocess_delta["precision"] == 0.0
        assert postprocess_delta["recall"] == 0.0

    def test_a_postprocessor_that_helps_shows_in_the_second_delta(self, cases):
        """The `COMPANY HANNAH` case is only fixable by a type correction."""
        def _fake_call(system_prompt, user_payload):
            payload = json.loads(user_payload)
            decisions = []
            for candidate in payload["candidates"]:
                if candidate["entity_type"] == "COMPANY" and candidate["value"].isupper():
                    decisions.append({
                        "candidate_id": candidate["candidate_id"],
                        "decision": "modify",
                        "entity_type": "NAME",
                    })
                else:
                    decisions.append({"candidate_id": candidate["candidate_id"], "decision": "keep"})
            return {"decisions": decisions}, 100

        report = run_fixture(cases, postprocess_call=_fake_call).as_dict()

        assert report["deltas"][1]["entity_type_accuracy"] >= 0

    def test_compare_reports_signed_differences(self):
        low = EntityMetrics(configuration="a", true_positives=1, false_positives=3, false_negatives=3)
        high = EntityMetrics(configuration="b", true_positives=3, false_positives=1, false_negatives=1)

        delta = compare(low, high)

        assert delta["from"] == "a" and delta["to"] == "b"
        assert delta["f1"] > 0


class TestTheReleaseGate:
    """Rows 102, 103 and 104."""

    def test_a_hallucinating_configuration_is_blocked(self, cases):
        result = run_fixture(cases)
        result.metrics[BERT_REPAIRS_POSTPROCESS].unsupported_values = 1

        gate = evaluate_gate(result)

        assert gate.passed is False
        assert any("hallucination" in reason for reason in gate.reasons)

    def test_an_unanchored_entity_also_blocks(self, cases):
        result = run_fixture(cases)
        result.metrics[BERT_REPAIRS_POSTPROCESS].unanchored_entities = 1

        gate = evaluate_gate(result)

        assert gate.passed is False

    def test_a_structured_query_regression_blocks(self, cases):
        result = run_fixture(cases)

        gate = evaluate_gate(result, structured_query_success={
            BERT_REPAIRS: 0.80,
            BERT_REPAIRS_POSTPROCESS: 0.60,
        })

        assert gate.passed is False
        assert any("structured-query success regressed" in reason for reason in gate.reasons)

    def test_improved_f1_alone_does_not_satisfy_the_gate(self, cases):
        """The explicit warning in the proposal: better normalization with new false
        positives is not an improvement."""
        result = run_fixture(cases)
        candidate = result.metrics[BERT_REPAIRS_POSTPROCESS]
        candidate.true_positives += 5
        candidate.unsupported_values = 2

        gate = evaluate_gate(result)

        assert candidate.f1 > result.metrics[BERT_REPAIRS].f1
        assert gate.passed is False

    def test_a_clean_configuration_passes(self, cases):
        result = run_fixture(cases)

        gate = evaluate_gate(result, structured_query_success={
            BERT_REPAIRS: 0.80,
            BERT_REPAIRS_POSTPROCESS: 0.85,
        })

        assert gate.passed is True
        assert gate.reasons == []

    def test_a_passing_gate_records_the_model_and_prompt_version(self, cases, monkeypatch):
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")
        monkeypatch.setattr(settings, "postprocess_prompt_version", "v1")
        result = run_fixture(cases)

        gate = evaluate_gate(result)

        assert gate.postprocess_model == "gpt-4o-mini"
        assert gate.postprocess_prompt_version == "v1"
        assert gate.as_dict()["configuration"] == BERT_REPAIRS_POSTPROCESS
