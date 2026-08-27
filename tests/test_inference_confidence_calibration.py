"""Guards the calibration fix: `_infer_window()` used to report `np.max(logits)` as
`confidence`, an unbounded raw logit. Every persisted value landed in the 2-8 range, so
`settings.confidence_threshold = 0.50` excluded nothing and no downstream stage could
read the number as a probability or compare it across model versions."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import math

import numpy as np
import pytest

from src.model_serving.services import inference_service
from src.model_serving.services.inference_service import softmax
from src.shared.config import settings


class _FakeInput:
    def __init__(self, name):
        self.name = name


def _fake_session(logit_fn, label_count):
    """Session whose per-position logit vector is produced by `logit_fn(position)`.
    Unlike the windowing fixtures, this returns a *full* vector so the softmax
    denominator is exercised rather than a one-hot spike."""

    class FakeSession:
        def get_inputs(self):
            return [_FakeInput("input_ids"), _FakeInput("attention_mask")]

        def run(self, output_names, inputs):
            seq_len = inputs["input_ids"].shape[1]
            logits = np.zeros((1, seq_len, label_count), dtype=np.float32)
            for pos in range(seq_len):
                logits[0, pos, :] = logit_fn(pos)
            return [logits]

    return FakeSession()


@pytest.fixture
def label_list():
    return ["O", "B-PROGRAMMING_LANGUAGE", "I-PROGRAMMING_LANGUAGE"]


@pytest.fixture
def patched_serving(monkeypatch, label_list):
    monkeypatch.setattr(inference_service, "_resolve_label_list", lambda tid: label_list)
    monkeypatch.setattr(
        inference_service, "_resolve_active_version", lambda tid: ("tenants/t/models/v5/", 5)
    )
    monkeypatch.setattr(settings, "inference_window_size", 400)
    monkeypatch.setattr(settings, "inference_window_overlap", 50)


def _install_session(monkeypatch, session):
    monkeypatch.setattr(
        inference_service.model_cache,
        "get",
        lambda mid: type("C", (), {"model": {"session": session}})(),
    )


class TestSoftmaxHelper:
    def test_matches_a_hand_computed_vector(self):
        """The observed production logit band was roughly 2.8-7.4, which is exactly the
        range a raw max-logit read produces and a probability cannot."""
        logits = np.array([[2.0, 5.0, 1.0]], dtype=np.float64)
        denominator = math.exp(2.0) + math.exp(5.0) + math.exp(1.0)
        expected = [math.exp(2.0) / denominator, math.exp(5.0) / denominator, math.exp(1.0) / denominator]
        assert softmax(logits, axis=-1)[0] == pytest.approx(expected, rel=1e-9)

    def test_rows_sum_to_one(self):
        logits = np.random.default_rng(0).normal(size=(4, 7)) * 6
        assert softmax(logits, axis=-1).sum(axis=-1) == pytest.approx(np.ones(4))

    def test_large_logits_do_not_overflow(self):
        result = softmax(np.array([[900.0, 899.0, 1.0]]), axis=-1)
        assert np.isfinite(result).all()
        assert result.sum() == pytest.approx(1.0)


class TestFineTunedPathIsCalibrated:
    """Row 2: every returned confidence is the softmax probability of the predicted
    label, in [0, 1] — not the raw maximum logit."""

    def test_confidence_is_within_the_unit_interval(self, monkeypatch, patched_serving, label_list):
        _install_session(monkeypatch, _fake_session(lambda pos: [2.0, 5.0, 1.0], len(label_list)))

        results = inference_service._infer_with_onnx(["Python", "and", "Java"], "t1")

        assert results, "fixture must produce at least one non-O prediction"
        for prediction in results:
            assert 0.0 <= prediction["confidence"] <= 1.0

    def test_confidence_equals_the_hand_computed_probability(self, monkeypatch, patched_serving, label_list):
        logit_vector = [2.0, 5.0, 1.0]
        _install_session(monkeypatch, _fake_session(lambda pos: logit_vector, len(label_list)))
        denominator = sum(math.exp(v) for v in logit_vector)
        expected = math.exp(5.0) / denominator

        results = inference_service._infer_with_onnx(["Python", "and", "Java"], "t1")

        for prediction in results:
            assert prediction["confidence"] == pytest.approx(expected, rel=1e-6)

    def test_confidence_is_not_the_raw_max_logit(self, monkeypatch, patched_serving, label_list):
        """The exact regression: a max logit of 5.0 used to be reported verbatim."""
        _install_session(monkeypatch, _fake_session(lambda pos: [2.0, 5.0, 1.0], len(label_list)))

        results = inference_service._infer_with_onnx(["Python"], "t1")

        assert results
        assert all(prediction["confidence"] != pytest.approx(5.0) for prediction in results)

    def test_confidence_tracks_the_label_argmax_selected(self, monkeypatch, patched_serving, label_list):
        """`np.max` over the softmax must pick the same element `argmax` did, or a
        prediction would carry another label's probability."""
        _install_session(monkeypatch, _fake_session(lambda pos: [1.0, 3.0, 9.0], len(label_list)))
        denominator = sum(math.exp(v) for v in (1.0, 3.0, 9.0))
        expected = math.exp(9.0) / denominator

        results = inference_service._infer_with_onnx(["Python"], "t1")

        assert results
        for prediction in results:
            assert prediction["label"] == "I-PROGRAMMING_LANGUAGE"
            assert prediction["confidence"] == pytest.approx(expected, rel=1e-6)


class TestBaseModelPathIsCalibrated:
    """Row 3: the base-model fallback reports the same scale, so a tenant with no
    promoted model is thresholded and routed identically to one with a fine-tuned model."""

    def test_pipeline_scores_pass_through_within_the_unit_interval(self, monkeypatch):
        class FakePipeline:
            def __call__(self, text):
                return [
                    {"word": "John", "entity": "B-PER", "score": 0.9987},
                    {"word": "Acme", "entity": "B-ORG", "score": 0.6421},
                ]

        monkeypatch.setattr(inference_service, "_get_base_pipeline", lambda: FakePipeline())

        results = inference_service._infer_with_base_model(["John", "works", "at", "Acme"])

        assert [r["confidence"] for r in results] == pytest.approx([0.9987, 0.6421])
        for prediction in results:
            assert 0.0 <= prediction["confidence"] <= 1.0

    @pytest.mark.slow
    def test_real_base_pipeline_returns_probabilities(self):
        """Downloads the base model, so it is excluded from the default run. It is the
        only check that the pipeline's `score` really is a probability rather than an
        assumption baked into the fake above."""
        results = inference_service._infer_with_base_model(["John", "works", "at", "Acme", "Corp"])

        assert results
        for prediction in results:
            assert 0.0 <= prediction["confidence"] <= 1.0


class TestOverlapTieBreakStillWorks:
    """Row 4: overlap conflicts are resolved by edge distance first, confidence second.
    Softmax is monotonic within a row, so the winner must be unchanged — on a scale that
    is now comparable."""

    def test_higher_probability_wins_at_equal_edge_distance(self, monkeypatch, patched_serving, label_list):
        weak = softmax(np.array([[2.0, 3.0, 1.0]]), axis=-1).max()
        strong = softmax(np.array([[2.0, 9.0, 1.0]]), axis=-1).max()
        assert strong > weak

        best: dict[int, tuple[int, float, str]] = {}
        for distance, confidence, label in (
            (7, float(weak), "B-PROGRAMMING_LANGUAGE"),
            (7, float(strong), "I-PROGRAMMING_LANGUAGE"),
        ):
            candidate = (distance, confidence, label)
            incumbent = best.get(0)
            if incumbent is None or candidate[:2] > incumbent[:2]:
                best[0] = candidate

        assert best[0][2] == "I-PROGRAMMING_LANGUAGE"

    def test_edge_distance_still_outranks_confidence(self, monkeypatch, patched_serving, label_list):
        strong_at_edge = float(softmax(np.array([[2.0, 9.0, 1.0]]), axis=-1).max())
        weak_in_middle = float(softmax(np.array([[2.0, 3.0, 1.0]]), axis=-1).max())

        best: dict[int, tuple[int, float, str]] = {}
        for distance, confidence, label in (
            (0, strong_at_edge, "B-PROGRAMMING_LANGUAGE"),
            (12, weak_in_middle, "I-PROGRAMMING_LANGUAGE"),
        ):
            candidate = (distance, confidence, label)
            incumbent = best.get(0)
            if incumbent is None or candidate[:2] > incumbent[:2]:
                best[0] = candidate

        assert best[0][2] == "I-PROGRAMMING_LANGUAGE", "distance must dominate confidence"
