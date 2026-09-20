"""Verification for uploader-scoping telemetry — verification.md rows 20-21.

AGENTS.md invariant 4: log the shape of data, never the data. Narrowing an answer is
exactly the kind of event whose debuggable form ("which document did it drop?") is the
form that must never be emitted — a metric label reaches Prometheus, where retention is
long, access is broad and no redaction filter runs at all.
"""

import logging

import pytest

from src.shared.document_visibility import NO_REQUESTING_USER, ROLE_TENANT_ADMIN, RequestingUser
from src.shared.observability.domain_metrics import (
    FAMILIES,
    OTHER,
    TENANT_LABEL_ALLOWLIST,
    UPLOADER_SCOPE_APPLICATIONS,
    UPLOADER_SCOPE_CHANNELS,
    UPLOADER_SCOPE_OUTCOMES,
    record_uploader_scope,
    uploader_scope_outcome,
)

FAMILY_NAME = "ner_uploader_scope_applications_total"


# --- Row 21: labels are declared and finite ----------------------------------------


def test_family_is_declared_once_and_reachable_by_import():
    assert FAMILIES[FAMILY_NAME] is UPLOADER_SCOPE_APPLICATIONS


def test_label_keys_are_exactly_channel_and_outcome():
    assert UPLOADER_SCOPE_APPLICATIONS.label_names == ("channel", "outcome")


def test_every_label_value_set_is_finite_and_enumerated():
    for label in UPLOADER_SCOPE_APPLICATIONS.labels:
        assert label.values, f"{label.name} declares no values"
        assert OTHER in label.values, (
            f"{label.name} has no catch-all, so an unenumerated value would mint a series"
        )
    # The series count is computable before shipping, which is the whole point of the
    # declaration module.
    assert UPLOADER_SCOPE_APPLICATIONS.series_count() == len(UPLOADER_SCOPE_CHANNELS) * len(
        UPLOADER_SCOPE_OUTCOMES
    )


def test_no_label_is_a_user_or_tenant_identifier():
    forbidden = {"tenant_id", "tenant", "user_id", "user", "uploaded_by", "requesting_user"}
    assert forbidden.isdisjoint(set(UPLOADER_SCOPE_APPLICATIONS.label_names))


def test_family_is_not_on_the_tenant_label_allowlist():
    assert FAMILY_NAME not in TENANT_LABEL_ALLOWLIST


def test_label_values_carry_no_identifiers():
    """A declared value set is only safe if the values themselves are categories. A
    tenant id smuggled in as a declared value would be just as unbounded in practice."""
    for label in UPLOADER_SCOPE_APPLICATIONS.labels:
        for value in label.values:
            assert value.islower() or value == OTHER
            assert "-" not in value, f"{value!r} looks like an identifier, not a category"


@pytest.mark.parametrize("bad", ["'; DROP TABLE documents--", "u-1234", "", "SEMANTIC_RETRIEVAL"])
def test_out_of_set_values_coerce_to_other(bad):
    channel_label, outcome_label = UPLOADER_SCOPE_APPLICATIONS.labels
    assert channel_label.coerce(bad) == OTHER
    assert outcome_label.coerce(bad) == OTHER


def test_none_coerces_without_raising():
    channel_label, _ = UPLOADER_SCOPE_APPLICATIONS.labels
    assert channel_label.coerce(None) == OTHER


def test_recording_an_unenumerated_value_does_not_raise():
    """A metric must never be able to fail the work it measures."""
    record_uploader_scope("a-channel-that-does-not-exist", "an-outcome-that-does-not-exist")
    record_uploader_scope("semantic_retrieval", "scoped_to_user")


# --- The outcome classifier --------------------------------------------------------


def test_outcome_classifier_covers_the_three_cases():
    assert uploader_scope_outcome(RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN)) == "unscoped_admin"
    assert uploader_scope_outcome(RequestingUser(user_id="u1", role="business_user")) == "scoped_to_user"
    assert uploader_scope_outcome(NO_REQUESTING_USER) == "scoped_anonymous"
    assert uploader_scope_outcome(None) == "scoped_anonymous"


def test_every_classifier_result_is_declared():
    for user in (
        RequestingUser(user_id="admin", role=ROLE_TENANT_ADMIN),
        RequestingUser(user_id="u1", role="business_user"),
        NO_REQUESTING_USER,
        None,
    ):
        assert uploader_scope_outcome(user) in UPLOADER_SCOPE_OUTCOMES


# --- Row 20: narrowing is recorded as shape ----------------------------------------


def test_recorder_signature_admits_no_payload():
    """The defence against a filename becoming a label is that there is nowhere to put
    one: the recorder takes two category arguments and nothing else."""
    import inspect

    params = list(inspect.signature(record_uploader_scope).parameters)
    assert params == ["channel", "outcome"]


def test_recording_emits_no_log_record_carrying_content(caplog):
    with caplog.at_level(logging.DEBUG):
        record_uploader_scope("semantic_retrieval", "scoped_to_user")
    for record in caplog.records:
        rendered = record.getMessage() + str(getattr(record, "__dict__", {}))
        for leak in ("resume.pdf", "SELECT", "uploaded_by=", "u1"):
            assert leak not in rendered
