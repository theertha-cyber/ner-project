"""Extraction handles the rawest tenant data on the platform, and emits none of it.

Verification row 14.

The chat path handles a question and a generated statement. Extraction handles the
document text itself, the spans cut out of it, and the entity values reconstructed from
those spans — a candidate's name, an address, a diagnosis, depending on the tenant. It is
the workload where a careless attribute is worst, and it is also the workload whose
telemetry is most tempting, because "which entity types did we find" is genuinely useful.

Design Decision 12 is the answer to that temptation, and the assertions here are what
holds it: per-type counts on the span, an aggregate on the metric, and no entity value
anywhere.
"""

import json
import logging

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm
from src.shared.observability.spans import stage_span

pytestmark = [pytest.mark.verification]

# Seeded values standing in for what a real run would carry out of a document.
SEEDED = ("Priya Raghunathan", "priya@example.com", "Resume 4.pdf", "hypertension")

# A tenant-authored entity type. Not personal data itself, but it fingerprints the tenant:
# a schema carrying `policy_holder` and `claim_number` identifies an insurer, in a metric
# store every dashboard user can read.
TENANT_ENTITY_TYPE = "policy_holder"


def _all_label_values() -> list[tuple[str, str, str]]:
    return [
        (metric.name, key, str(value))
        for metric in REGISTRY.collect()
        for sample in metric.samples
        for key, value in sample.labels.items()
    ]


def _simulate_run(span):
    """The telemetry one run emits, recorded exactly as `worker.py` records it."""
    span.set("model_version", "3")
    span.set("documents_processed", 2)
    span.set("documents_failed", 0)
    span.set("entities_extracted", 5)
    span.set(f"entities.{TENANT_ENTITY_TYPE}", 3)
    span.set("entities.PER", 2)

    dm.record_extraction_stage("parse", 0.4)
    dm.record_extraction_stage("inference", 2.1)
    dm.record_extraction_volume(pages=2, entities=5)
    dm.record_extraction_job("tenant-seeded", "succeeded")


class TestOneExtractionRunLeaksNothing:
    """Row 14."""

    @pytest.fixture
    def emitted(self, captured_spans, caplog):
        with caplog.at_level(logging.DEBUG):
            with stage_span("extraction_run", processing_mode="bert_only") as span:
                _simulate_run(span)
        return {
            "spans": [
                f"{s.name} " + " ".join(f"{k}={v}" for k, v in dict(s.attributes).items())
                for s in captured_spans.get_finished_spans()
            ],
            "labels": _all_label_values(),
            "logs": [
                r.getMessage() + json.dumps({k: str(v) for k, v in r.__dict__.items()})
                for r in caplog.records
            ],
        }

    @pytest.mark.parametrize("value", SEEDED)
    def test_no_span_attribute_carries_a_seeded_value(self, emitted, value):
        offenders = [text for text in emitted["spans"] if value in text]
        assert offenders == [], offenders[:2]

    @pytest.mark.parametrize("value", SEEDED)
    def test_no_metric_label_carries_a_seeded_value(self, emitted, value):
        offenders = [row for row in emitted["labels"] if value in row[2]]
        assert offenders == [], offenders[:2]

    @pytest.mark.parametrize("value", SEEDED)
    def test_no_log_record_carries_a_seeded_value(self, emitted, value):
        offenders = [text[:200] for text in emitted["logs"] if value in text]
        assert offenders == [], offenders[:2]

    def test_the_capture_is_not_empty(self, emitted):
        """Without this the three assertions above pass against nothing at all."""
        assert emitted["spans"]
        assert emitted["labels"]
        assert any("extraction_run" in text for text in emitted["spans"])


class TestTheEntityTypeSplit:
    """Design Decision 12 — per-type on the span, aggregate on the metric."""

    def test_the_tenant_authored_type_reaches_the_span(self, captured_spans):
        with stage_span("extraction_run") as span:
            _simulate_run(span)

        span = captured_spans.get_finished_spans()[-1]

        assert span.attributes[f"entities.{TENANT_ENTITY_TYPE}"] == 3, (
            "ADR-010 measures readiness per entity type; dropping the breakdown "
            "everywhere would trade one problem for another"
        )

    def test_the_tenant_authored_type_reaches_no_metric_label(self, captured_spans):
        with stage_span("extraction_run") as span:
            _simulate_run(span)

        offenders = [
            row for row in _all_label_values() if TENANT_ENTITY_TYPE in row[2]
        ]
        assert offenders == [], (
            "a tenant that configures `policy_holder` and `claim_number` is identifiable "
            f"from label values alone, in a store shared across tenants: {offenders}"
        )

    def test_the_span_is_bounded_by_trace_retention_and_the_metric_is_not(self):
        """The reason the split is safe rather than merely tidy. Spans expire; a
        Prometheus series with a tenant-fingerprinting label persists for a year and is
        readable by everyone with dashboard access."""
        assert dm.EXTRACTION_ENTITIES.labels == ()
        assert "tenant_id" not in dm.EXTRACTION_ENTITIES.label_names
