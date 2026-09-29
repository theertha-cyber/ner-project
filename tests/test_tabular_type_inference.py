"""Type inference by candidate elimination (tabular-file-ingestion spec)."""

import csv

from src.shared.tabular_files import ingest


def _profile(tmp_path, header, values):
    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([header])
        for value in values:
            writer.writerow([value])
    staging = str(tmp_path / "staging.duckdb")
    labels, _ = ingest.stage_original(str(path), "csv", None, staging, 1_000_000, str(tmp_path))
    con = ingest.open_staging(staging)
    try:
        return ingest.build_profile(con, labels, "data")["columns"][0]
    finally:
        con.close()


def test_leading_zeros_stay_text(tmp_path):
    """Scenario: Leading zeros stay text."""
    assert _profile(tmp_path, "code", ["007", "012", "145"])["type"] == "text"


def test_null_tokens_are_ignored(tmp_path):
    """Scenario: Null tokens are ignored."""
    column = _profile(tmp_path, "amount", ["1200", "450", "N/A", "-", ""])
    assert column["type"] == "bigint"
    assert column["null_count"] == 3


def test_mixed_column_falls_back_with_a_warning(tmp_path):
    """Scenario: Mixed column falls back with a warning."""
    values = [str(i) for i in range(1, 10_001)]
    bad_rows = list(range(500, 10_000, 1000))  # 10 positions
    for position in bad_rows:
        values[position] = "abc"
    column = _profile(tmp_path, "qty", values)
    assert column["type"] == "text"
    [warning] = column["warnings"]
    assert warning["code"] == "mixed_values"
    assert warning["candidate"] == "bigint"
    assert warning["count"] == 10
    # Row numbers count the header as row 1.
    assert warning["rows"] == [p + 2 for p in bad_rows]


def test_ambiguous_dates_are_not_guessed(tmp_path):
    """Scenario: Ambiguous dates are not guessed."""
    column = _profile(tmp_path, "closed_on", ["03/04/2026", "05/06/2026", "11/12/2026"])
    assert column["type"] == "date"
    assert column["date_format_required"] is True
    assert column["date_format"] is None


def test_unambiguous_day_first_dates_are_detected(tmp_path):
    """Scenario: Unambiguous day-first dates are detected."""
    column = _profile(tmp_path, "closed_on", ["03/04/2026", "25/04/2026", "11/12/2026"])
    assert column["type"] == "date"
    assert column["date_format"] == "DD/MM/YYYY"
    assert column["date_format_required"] is False


def test_bad_value_in_the_last_row_only(tmp_path):
    """Hallucination risk 7: evidence covers every row, not a sample."""
    values = [str(i) for i in range(1, 50_001)] + ["oops"]
    column = _profile(tmp_path, "n", values)
    assert column["type"] == "text"
    assert column["warnings"][0]["rows"] == [50_002]


def test_candidate_order_and_strictness(tmp_path):
    assert _profile(tmp_path, "b", ["yes", "no", "True"])["type"] == "boolean"
    assert _profile(tmp_path, "n", ["1.5", "2", "3e2"])["type"] == "numeric"
    assert _profile(tmp_path, "d", ["2026-01-02", "2026-12-31"])["type"] == "date"
    assert _profile(tmp_path, "t", ["2026-01-02 10:00", "2026-12-31T23:59:59"])["type"] == "timestamp"
    # DuckDB would cast these; the product rules do not.
    assert _profile(tmp_path, "h", ["0x1A", "12"])["type"] == "text"
    assert _profile(tmp_path, "e", ["", "N/A"])["type"] == "text"


def test_profile_stats(tmp_path):
    column = _profile(tmp_path, "region", ["EMEA", "APAC", "EMEA", "AMER"])
    assert column["distinct_count"] == 3
    assert column["top_values"][0] == {"value": "EMEA", "count": 2}
    assert {v["value"] for v in column["top_values"]} == {"EMEA", "APAC", "AMER"}
    numeric = _profile(tmp_path, "amount", ["5", "900", "12"])
    assert (numeric["min"], numeric["max"]) == (5, 900)
