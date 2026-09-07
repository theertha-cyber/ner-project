"""A retrieval that finds nothing is recorded as such, not as an absence of records.

Verification row 4.

A zero-result retrieval is invisible in a duration histogram — it is fast, and it looks
exactly like a fast successful one. It is also the shape of the platform's most common
quality complaint. So the result count is an observation in its own right, and zero gets a
counter of its own so a rate is computable without reading histogram buckets.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

CAPABILITY = "semantic_retrieval"


def _zero_results(capability: str = CAPABILITY) -> float:
    value = REGISTRY.get_sample_value(
        "ner_retrieval_zero_results_total", {"capability": capability}
    )
    return float(value or 0.0)


def _observations(capability: str = CAPABILITY) -> float:
    value = REGISTRY.get_sample_value(
        "ner_retrieval_results_count", {"capability": capability}
    )
    return float(value or 0.0)


def _bucket(le: str, capability: str = CAPABILITY) -> float:
    value = REGISTRY.get_sample_value(
        "ner_retrieval_results_bucket", {"capability": capability, "le": le}
    )
    return float(value or 0.0)


class TestZeroResults:
    """Row 4."""

    def test_an_empty_retrieval_records_a_result_count_of_zero(self):
        before_observations = _observations()
        before_zero_bucket = _bucket("0.0")

        dm.record_retrieval(CAPABILITY, result_count=0)

        assert _observations() == before_observations + 1, (
            "a retrieval that found nothing still happened; recording nothing would make "
            "it indistinguishable from a retrieval that was never attempted"
        )
        assert _bucket("0.0") == before_zero_bucket + 1

    def test_it_also_increments_the_zero_result_counter(self):
        before = _zero_results()

        dm.record_retrieval(CAPABILITY, result_count=0)

        assert _zero_results() == before + 1

    def test_a_non_empty_retrieval_leaves_the_zero_counter_alone(self):
        before = _zero_results()

        dm.record_retrieval(CAPABILITY, result_count=7)

        assert _zero_results() == before

    def test_each_capability_is_counted_separately(self):
        semantic_before = _zero_results("semantic_retrieval")
        structured_before = _zero_results("structured_retrieval")

        dm.record_retrieval("structured_retrieval", result_count=0)

        assert _zero_results("structured_retrieval") == structured_before + 1
        assert _zero_results("semantic_retrieval") == semantic_before, (
            "'the search found nothing' and 'the query matched no rows' are different "
            "failures with different fixes"
        )


class TestTheOrchestratorRecordsEveryDispatchedCapability:
    """The recording sits in `_invoke_entry`, which is the one point every dispatched
    capability passes through — so a third tool added later is measured without being
    touched."""

    def test_the_recording_is_in_the_shared_dispatch_path(self):
        import inspect

        from src.shared.retrieval import orchestrator

        source = inspect.getsource(orchestrator._invoke_entry)

        assert "record_retrieval(entry.capability_name" in source

    def test_the_capability_enumeration_covers_the_registered_tools(self):
        from src.shared.retrieval.tools.document_tools import SemanticRetrievalTool
        from src.shared.retrieval.tools.entity_tools import StructuredRetrievalTool

        declared = dm.RETRIEVAL_CAPABILITIES

        assert SemanticRetrievalTool.name in declared
        assert StructuredRetrievalTool.name in declared


class TestHitRate:
    """Task 3.5's fourth measurement — what survived merge and the cap."""

    def test_a_hit_rate_observation_is_bounded_to_the_unit_interval(self):
        dm.record_retrieval_hit_rate(CAPABILITY, 0.25)

        value = REGISTRY.get_sample_value(
            "ner_retrieval_hit_rate_sum", {"capability": CAPABILITY}
        )
        assert value is not None
        assert dm.RETRIEVAL_HIT_RATE.buckets[-1] == 1.0
