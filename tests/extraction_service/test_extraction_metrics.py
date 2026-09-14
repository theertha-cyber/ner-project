"""An extraction run reports its shape; a failed one reports where it stopped.

Verification rows 11 and 12.

The entity-count split is the design decision worth reading twice. ADR-010 measures
dataset readiness *per entity type*, so the per-type breakdown has to survive somewhere —
but entity types are tenant-configured (`list_entity_types(tenant_id)`), which makes them
neither enumerable at declaration nor safe as label values in a store shared across
tenants: a tenant that configures `policy_holder` and `claim_number` is identifiable from
label values alone, in a store with no redaction on the metrics path. So the per-type
counts live on the run's span, which is already tenant-scoped and bounded by trace
retention, and the metric carries an aggregate. See design Decision 12.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

TENANT = "tenant-extract"


def _jobs(outcome: str, tenant_id: str = TENANT) -> float:
    value = REGISTRY.get_sample_value(
        "ner_extraction_jobs_total", {"tenant_id": tenant_id, "outcome": outcome}
    )
    return float(value or 0.0)


def _stage_reached(stage: str) -> float:
    value = REGISTRY.get_sample_value("ner_extraction_stage_reached_total", {"stage": stage})
    return float(value or 0.0)


def _stage_duration_count(stage: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_extraction_stage_duration_seconds_count", {"stage": stage}
    )
    return float(value or 0.0)


def _failures(error_class: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_extraction_failures_total", {"error_class": error_class}
    )
    return float(value or 0.0)


def _entities_total() -> float:
    return float(REGISTRY.get_sample_value("ner_extraction_entities_total", {}) or 0.0)


def _pages_sum() -> float:
    return float(REGISTRY.get_sample_value("ner_extraction_pages_processed_sum", {}) or 0.0)


class TestASuccessfulRun:
    """Row 11."""

    def test_a_stage_records_both_a_duration_and_the_fact_it_was_reached(self):
        before_reached = _stage_reached("parse")
        before_duration = _stage_duration_count("parse")

        dm.record_extraction_stage("parse", 1.5)

        assert _stage_reached("parse") == before_reached + 1
        assert _stage_duration_count("parse") == before_duration + 1, (
            "the duration says how long a stage took; the reach counter says a run got "
            "that far at all, which is how a failed run is located without reading logs"
        )

    def test_pages_and_the_aggregate_entity_count_are_recorded(self):
        before_pages = _pages_sum()
        before_entities = _entities_total()

        dm.record_extraction_volume(pages=12, entities=340)

        assert _pages_sum() == before_pages + 12
        assert _entities_total() == before_entities + 340

    def test_a_completed_run_is_counted_under_its_tenant(self):
        before = _jobs("succeeded")

        dm.record_extraction_job(TENANT, "succeeded")

        assert _jobs("succeeded") == before + 1

    def test_a_run_with_some_documents_failed_is_partial_not_succeeded(self):
        before_partial = _jobs("partial")
        before_succeeded = _jobs("succeeded")

        dm.record_extraction_job(TENANT, "partial")

        assert _jobs("partial") == before_partial + 1
        assert _jobs("succeeded") == before_succeeded, (
            "a run where three of forty documents failed is not a success and not a "
            "failure; folding it into either loses the only actionable state"
        )

    def test_the_run_span_carries_the_model_version_and_the_per_type_counts(self):
        """Read off the source rather than executed, because driving a real run needs
        model serving, MinIO and a seeded tenant. What is pinned is that the per-type
        breakdown goes on the span and the aggregate goes on the metric."""
        import inspect

        from src.extraction_service import worker

        source = inspect.getsource(worker._run_batch_extraction)

        assert 'span.set("model_version", model_version)' in source
        assert 'span.set(f"entities.{entity_type}", count)' in source
        assert "record_extraction_volume(pages=processed, entities=entities_total)" in source


class TestAFailedRun:
    """Row 12."""

    def test_a_failure_increments_under_its_exception_class(self):
        before = _failures("OperationalError")

        dm.record_extraction_failure(
            type("OperationalError", (Exception,), {})("relation does not exist")
        )

        assert _failures("OperationalError") == before + 1

    def test_no_exception_message_reaches_the_label(self):
        dm.record_extraction_failure(ValueError("could not parse Priya Raman Resume 4.pdf"))

        offenders = [
            sample.labels
            for metric in REGISTRY.collect()
            if metric.name == "ner_extraction_failures"
            for sample in metric.samples
            if any("Priya" in str(v) or "Resume" in str(v) for v in sample.labels.values())
        ]
        assert offenders == []

    def test_the_failing_stage_is_identifiable_from_the_reach_counter(self):
        """The failure counter is labelled by exception class and the stage is not on it,
        deliberately: the two labels multiply, and the stage is already answerable from
        the reach counter and from the span."""
        assert dm.EXTRACTION_FAILURES.label_names == ("error_class",)
        assert dm.EXTRACTION_STAGE_REACHED.label_names == ("stage",)

    def test_a_partial_failure_is_counted_separately_from_a_run_failure(self):
        before_partial = float(
            REGISTRY.get_sample_value(
                "ner_extraction_partial_failures_total", {"stage": "inference"}
            )
            or 0.0
        )
        before_failed = _failures("ValueError")

        dm.record_extraction_partial_failure("inference")

        after_partial = float(
            REGISTRY.get_sample_value(
                "ner_extraction_partial_failures_total", {"stage": "inference"}
            )
            or 0.0
        )
        assert after_partial == before_partial + 1
        assert _failures("ValueError") == before_failed


class TestEntityTypeIsNeverALabel:
    """Design Decision 12 and verification row 41, asserted here as well as in the
    declaration test — this is the boundary that erodes under the first dashboard
    request for a per-type breakdown."""

    def test_the_aggregate_counter_carries_no_labels_at_all(self):
        assert dm.EXTRACTION_ENTITIES.labels == ()

    def test_no_extraction_family_carries_an_entity_type_label(self):
        extraction_families = [
            family
            for name, family in dm.FAMILIES.items()
            if name.startswith("ner_extraction_")
        ]
        assert extraction_families

        for family in extraction_families:
            assert "entity_type" not in family.label_names

    def test_the_extraction_jobs_family_is_the_only_tenant_labelled_one_here(self):
        tenant_labelled = {
            name
            for name, family in dm.FAMILIES.items()
            if name.startswith("ner_extraction_") and "tenant_id" in family.label_names
        }
        assert tenant_labelled == {"ner_extraction_jobs_total"}
        assert tenant_labelled <= dm.TENANT_LABEL_ALLOWLIST
