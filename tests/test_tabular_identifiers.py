"""Column identifier sanitization (tabular-file-ingestion spec)."""

import pytest

from src.shared.tabular_files.identifiers import (
    is_valid_identifier,
    sanitize_all,
    sanitize_identifier,
)


def test_headers_become_safe_identifiers():
    """Scenario: Headers become safe identifiers."""
    headers = ["Order ID", "2024 Revenue ($)", "select", "Amount", "amount"]
    assert sanitize_all(headers) == ["order_id", "c_2024_revenue", "c_select", "amount", "amount_2"]
    # Labels are kept by the caller: sanitizing never mutates the header list.
    assert headers == ["Order ID", "2024 Revenue ($)", "select", "Amount", "amount"]


@pytest.mark.parametrize("header,expected", [
    ("", "c_column"),
    (None, "c_column"),
    ("$$$", "c_column"),
    ("  __Region__  ", "region"),
    ("from", "c_from"),
    ("a" * 80, "a" * 63),
])
def test_edge_headers(header, expected):
    assert sanitize_identifier(header) == expected


def test_dedupe_keeps_length_bound():
    ids = sanitize_all(["x" * 70, "x" * 70, "x" * 70])
    assert ids == ["x" * 63, "x" * 61 + "_2", "x" * 61 + "_3"]
    assert all(len(i) <= 63 for i in ids)


@pytest.mark.parametrize("value,ok", [
    ("amount", True), ("c_select", True), ("drop table x", False),
    ("select", False), ("Amount", False), ("1abc", False), ("", False),
])
def test_is_valid_identifier(value, ok):
    assert is_valid_identifier(value) is ok
