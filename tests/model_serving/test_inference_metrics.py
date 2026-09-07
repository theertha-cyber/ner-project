"""Which model answered, how long it took, and whether the load was cold.

Verification rows 18, 19 and 20.

ADR-008 is what makes row 19 the interesting one. Before it, no promoted model meant a
404; after it, the base model answers and that is the correct Version 0 behaviour. So
base-model inference is a *success* on a distinguishable path, not a fallback counted as a
failure — and the two ways of reaching it are kept apart, because "this tenant has no
model yet" and "this tenant's model raised" need different people to look at them.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


def _inferences(path: str, outcome: str = "success") -> float:
    value = REGISTRY.get_sample_value(
        "ner_inferences_total", {"path": path, "outcome": outcome}
    )
    return float(value or 0.0)


def _duration_count(path: str) -> float:
    value = REGISTRY.get_sample_value("ner_inference_duration_seconds_count", {"path": path})
    return float(value or 0.0)


def _loads(result: str) -> float:
    value = REGISTRY.get_sample_value("ner_model_loads_total", {"result": result})
    return float(value or 0.0)


def _load_duration_count(result: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_model_load_duration_seconds_count", {"result": result}
    )
    return float(value or 0.0)


class TestTheTenantModelPath:
    """Row 18."""

    def test_it_records_a_duration_and_the_path(self):
        before_count = _inferences("tenant_onnx")
        before_duration = _duration_count("tenant_onnx")

        dm.record_inference("tenant_onnx", 0.42, windows=6, batch_size=6)

        assert _inferences("tenant_onnx") == before_count + 1
        assert _duration_count("tenant_onnx") == before_duration + 1

    def test_it_records_the_window_geometry(self):
        before = float(REGISTRY.get_sample_value("ner_inference_windows_sum", {}) or 0.0)

        dm.record_inference("tenant_onnx", 0.1, windows=6, batch_size=6)

        assert float(REGISTRY.get_sample_value("ner_inference_windows_sum", {})) == before + 6

    def test_the_active_version_is_a_span_attribute_not_a_label(self):
        """A version number climbs without bound as a tenant retrains, so as a label it is
        an unbounded value set — the exact failure mode the declarations exist to prevent.
        On the span it is bounded by trace retention and answers the same question."""
        import inspect

        from src.model_serving.services import inference_service

        source = inspect.getsource(inference_service.infer)

        assert 'span.set("model_version", str(version_number))' in source
        assert "model_version" not in dm.INFERENCES.label_names
        assert "model_version" not in dm.INFERENCE_DURATION.label_names


class TestTheBaseModelPathIsASuccess:
    """Row 19 — ADR-008."""

    def test_a_tenant_with_no_promoted_model_records_a_success(self):
        before_success = _inferences("base_model_no_promoted", "success")
        before_error = _inferences("base_model_no_promoted", "error")

        dm.record_inference("base_model_no_promoted", 0.3)

        assert _inferences("base_model_no_promoted", "success") == before_success + 1
        assert _inferences("base_model_no_promoted", "error") == before_error, (
            "ADR-008 makes the base model the correct Version 0 answer; counting it as an "
            "error would make every new tenant look like an outage"
        )

    def test_the_error_fallback_is_a_different_path_from_the_no_promoted_path(self):
        before_no_promoted = _inferences("base_model_no_promoted")
        before_fallback = _inferences("base_model_error_fallback", "error")

        dm.record_inference("base_model_error_fallback", 0.5, exc=RuntimeError("onnx blew up"))

        assert _inferences("base_model_error_fallback", "error") == before_fallback + 1
        assert _inferences("base_model_no_promoted") == before_no_promoted, (
            "a broken ONNX artifact and an ordinary new tenant both answer from the base "
            "model; one needs someone to look at it and the other does not"
        )

    def test_all_three_paths_are_declared(self):
        assert dm.INFERENCE_PATHS >= {
            "tenant_onnx",
            "base_model_no_promoted",
            "base_model_error_fallback",
        }

    def test_the_path_and_the_outcome_are_separate_labels(self):
        """Which is what lets the base model be a success. Folding them into one label
        would force `base_model` to mean either 'worked' or 'degraded' but not both."""
        assert dm.INFERENCES.label_names == ("path", "outcome")


class TestModelLoads:
    """Row 20."""

    def test_a_cold_start_is_recorded_with_its_duration(self):
        before_count = _loads("cold_start")
        before_duration = _load_duration_count("cold_start")

        dm.record_model_load("cold_start", 12.5)

        assert _loads("cold_start") == before_count + 1
        assert _load_duration_count("cold_start") == before_duration + 1

    def test_a_cache_hit_is_a_different_series(self):
        before_cold = _loads("cold_start")
        before_hit = _loads("cache_hit")

        dm.record_model_load("cache_hit", 0.0001)

        assert _loads("cache_hit") == before_hit + 1
        assert _loads("cold_start") == before_cold, (
            "a cold-start rate that stays high means the cache is being evicted faster "
            "than it is used, which is a capacity decision nobody can make blind"
        )

    def test_the_loader_records_both_outcomes(self):
        import inspect

        from src.model_serving.services import inference_service

        source = inspect.getsource(inference_service._load_model_for_tenant)

        assert 'record_model_load("cache_hit"' in source
        assert 'record_model_load("cold_start"' in source


class TestRerankIsMeasuredOnBothSides:
    """Task 6.4. The serving-side and caller-side numbers differ by the network hop, and
    the gap is what says whether a slow rerank is the model or the wire."""

    def test_the_serving_side_records_the_duration(self):
        import inspect

        from src.model_serving.services import rerank_service

        assert "record_rerank_duration" in inspect.getsource(rerank_service.rerank)

    def test_the_caller_side_records_it_too(self):
        import inspect

        from src.shared.retrieval import reranker

        assert "record_rerank_duration" in inspect.getsource(reranker.CrossEncoderReranker)
