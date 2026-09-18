"""Verification for document-content telemetry.

Covers: "An access is recorded as shape", "Metric labels are finite and declared",
"Conversion is observable as shape".

AGENTS.md invariant 4. The temptation here is specific and strong: when a citation will
not open, the useful debugging label is *which document* and *what type it was* — and
both are tenant content. A metric label reaches Prometheus, where retention is long,
access is broad and no redaction filter runs.
"""

import logging

import pytest

from src.shared.document_retention import RETENTION_MODES
from src.shared.observability.domain_metrics import (
    CONVERSION_OUTCOMES,
    DOCUMENT_CONTENT_BYTES,
    DOCUMENT_CONTENT_CLASSES,
    DOCUMENT_CONTENT_OUTCOMES,
    DOCUMENT_CONTENT_REQUESTS,
    DOCUMENT_CONVERSION_DURATION,
    DOCUMENT_CONVERSIONS,
    FAMILIES,
    OTHER,
    RETENTION_MODE_LABELS,
    TENANT_LABEL_ALLOWLIST,
    content_class,
    record_document_content_request,
    record_document_conversion,
)

pytestmark = [pytest.mark.verification]

FAMILY_NAMES = [
    "ner_document_content_requests_total",
    "ner_document_content_bytes",
    "ner_document_conversions_total",
    "ner_document_conversion_duration_seconds",
]


# --- "Metric labels are finite and declared" ----------------------------------------


@pytest.mark.parametrize("name", FAMILY_NAMES)
def test_each_family_is_declared_once_and_reachable_by_import(name):
    assert name in FAMILIES


@pytest.mark.parametrize("name", FAMILY_NAMES)
def test_every_label_value_set_is_finite_with_a_catch_all(name):
    for label in FAMILIES[name].labels:
        assert label.values, f"{name}.{label.name} declares no values"
        assert OTHER in label.values, (
            f"{name}.{label.name} has no catch-all, so an unenumerated value mints a series"
        )


@pytest.mark.parametrize("name", FAMILY_NAMES)
def test_no_family_carries_a_tenant_or_document_identifier(name):
    forbidden = {"tenant_id", "tenant", "document_id", "user_id", "filename", "media_type"}
    assert forbidden.isdisjoint(set(FAMILIES[name].label_names)), name
    assert name not in TENANT_LABEL_ALLOWLIST


def test_series_counts_are_computable_before_shipping():
    """The point of the declaration module: cardinality is known, not discovered."""
    assert DOCUMENT_CONTENT_REQUESTS.series_count() == len(RETENTION_MODE_LABELS) * len(
        DOCUMENT_CONTENT_OUTCOMES
    )
    assert DOCUMENT_CONVERSIONS.series_count() == len(DOCUMENT_CONTENT_CLASSES) * len(
        CONVERSION_OUTCOMES
    )
    for name in FAMILY_NAMES:
        assert FAMILIES[name].series_count() < 100, f"{name} cardinality is larger than intended"


def test_retention_labels_are_imported_not_restated():
    """A rename in the retention module must break the import rather than leave a label
    value matching nothing the code emits."""
    assert RETENTION_MODES <= RETENTION_MODE_LABELS
    assert RETENTION_MODE_LABELS - RETENTION_MODES == {OTHER}


def test_every_failure_outcome_the_api_can_return_is_declared():
    """The viewer distinguishes these; the metric must too, or the dashboard cannot show
    which kind of failure is happening."""
    required = {
        "served", "not_found", "not_permitted", "original_released",
        "original_missing", "source_not_reopenable", "source_unavailable",
        "conversion_failed", "too_large",
    }
    assert required <= DOCUMENT_CONTENT_OUTCOMES


def test_a_released_original_and_an_unreachable_source_are_separate_values():
    """The distinction with product weight: one is permanent and the tenant's own policy,
    the other is transient."""
    assert "original_released" in DOCUMENT_CONTENT_OUTCOMES
    assert "source_unavailable" in DOCUMENT_CONTENT_OUTCOMES
    assert "original_released" != "source_unavailable"


# --- The media type never becomes a label -------------------------------------------


@pytest.mark.parametrize(
    "media_type,expected",
    [
        ("application/pdf", "pdf"),
        ("image/png", "image"),
        ("image/tiff", "image"),
        ("application/msword", "office"),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "office"),
        ("text/csv", "tabular"),
        # The attacker-chosen value: categorised as unknown, never passed through.
        ("text/html", OTHER),
        ("image/svg+xml", "image"),
        (None, OTHER),
        ("'; DROP TABLE documents--", OTHER),
    ],
)
def test_media_types_are_categorised_never_passed_through(media_type, expected):
    assert content_class(media_type) == expected


def test_every_category_is_declared():
    for media_type in ("application/pdf", "image/png", "text/csv", "text/html", None):
        assert content_class(media_type) in DOCUMENT_CONTENT_CLASSES


def test_recording_an_unenumerated_value_does_not_raise():
    """A metric must never be able to fail the work it measures."""
    record_document_content_request("not-a-mode", "not-an-outcome")
    record_document_conversion("not/a-type", "not-an-outcome", 1.0)


# --- "An access is recorded as shape" -----------------------------------------------


def test_the_recorder_signature_admits_no_identifier():
    """The defence against a document id becoming a label is that there is nowhere to
    put one."""
    import inspect

    params = set(inspect.signature(record_document_content_request).parameters)
    assert params == {"retention_mode", "outcome", "media_type", "byte_count"}
    assert not {"document_id", "filename", "user_id", "tenant_id"} & params


def test_size_is_recorded_only_for_a_served_document():
    """A failure has no size; recording zero would distort the distribution the memory
    ceiling is judged from."""
    import inspect

    source = inspect.getsource(record_document_content_request)
    assert 'outcome == "served"' in source


def test_recording_emits_no_record_carrying_content(caplog):
    with caplog.at_level(logging.DEBUG):
        record_document_content_request("platform_blob", "served", "application/pdf", 4096)
        record_document_conversion("text/csv", "converted", 0.5)
    rendered = " ".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
    for leak in ("resume.pdf", "candidate", "tenants/", "blob_path"):
        assert leak not in rendered
