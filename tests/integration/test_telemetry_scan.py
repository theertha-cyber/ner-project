"""The release-gate scan's four behaviours, re-runnable outside the pipeline.

Verification rows 37, 38, 39 and 40.

A scan is only evidence if it has been shown to fail. Task 8.4 does that expensively —
reintroducing a leak into the running stack and confirming the scan catches it — and this
file does it cheaply and repeatably, by feeding the scan's own checkers records that
contain what they are supposed to catch.

Both halves are needed. This file proves the *checkers* work; the manual verification
proves the *capture* works, which is the half that failed silently in the foundation
change when Loki turned out to be receiving nothing.
"""

import importlib.util
import pathlib

import pytest

pytestmark = [pytest.mark.verification]

_SCAN_PATH = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "telemetry_scan.py"


def _load_scan():
    """Import the script by path — `scripts/` is not a package."""
    spec = importlib.util.spec_from_file_location("telemetry_scan", _SCAN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan = _load_scan()


class TestACleanRunPasses:
    """Row 37."""

    def test_ordinary_derived_telemetry_produces_no_finding(self):
        clean = [
            'span sql_generation attempts=2 repair_depth=1 outcome=succeeded',
            'span chat.guardrail outcome=admitted duration_ms=3.2',
            '__name__=ner_sql_attempts_total outcome=validation_error defect_class=filename:',
            '{"service":"chat_api"} {"event":"sql_attempt","outcome":"success","rows":1}',
        ]

        assert scan.scan_records("mixed", clean) == []

    def test_the_defect_class_is_not_mistaken_for_content(self):
        """`filename:` is a category and must pass; `filename:<a person's name>` must not.
        A checker that could not tell them apart would either be useless or be turned off."""
        assert scan.scan_records("metrics", ["defect_class=filename:"]) == []


class TestALeakFails:
    """Row 38."""

    def test_a_seeded_value_in_a_log_record_is_found(self):
        record = f'{{"service":"chat_api"}} {{"msg":"answering for {scan.SENTINELS[0]}"}}'

        findings = scan.scan_records("logs", [record])

        assert findings

    def test_the_finding_names_the_offending_record(self):
        record = f'{{"service":"chat_api"}} {{"msg":"answering for {scan.SENTINELS[0]}"}}'

        rendered = str(scan.scan_records("logs", [record])[0])

        assert scan.SENTINELS[0] in rendered
        assert "logs" in rendered, "which backend held it is the first thing to know"
        assert "seeded entity value" in rendered

    def test_a_personal_data_pattern_is_found_even_without_a_seeded_value(self):
        """The seeding covers the paths the scan drives; the patterns cover the ones it
        does not."""
        findings = scan.scan_records(
            "logs", ['{"msg":"contact at someone.real@acme-corp.example"}']
        )

        assert findings
        assert "email pattern" in str(findings[0])

    @pytest.mark.parametrize(
        "record",
        [
            '{"msg":"ssn on file 123-45-6789"}',
            '{"msg":"card 4111 1111 1111 1111"}',
        ],
    )
    def test_the_other_patterns_are_matched_too(self, record):
        assert scan.scan_records("logs", [record])


class TestAnEmptyCaptureFails:
    """Row 39 — the rule that makes every other check mean something."""

    def test_nothing_captured_trips_the_floor(self):
        shortfalls = scan.check_capture_floor({"logs": [], "spans": [], "metrics": []})

        assert len(shortfalls) == 3
        assert all("expected at least" in s for s in shortfalls)

    def test_a_handful_of_records_still_trips_it(self):
        """Not 'greater than zero': one log line and one span would pass that, and a flow
        that produced one of each is a flow that did not run."""
        shortfalls = scan.check_capture_floor(
            {"logs": ["x"], "spans": ["x"], "metrics": ["x"]}
        )

        assert len(shortfalls) == 3

    def test_one_backend_being_empty_is_enough_to_fail(self):
        shortfalls = scan.check_capture_floor(
            {
                "logs": ["x"] * scan.MINIMUM_RECORDS["logs"],
                "spans": [],
                "metrics": ["x"] * scan.MINIMUM_RECORDS["metrics"],
            }
        )

        assert len(shortfalls) == 1
        assert shortfalls[0].startswith("spans")

    def test_a_sufficient_capture_does_not_trip_it(self):
        assert (
            scan.check_capture_floor(
                {
                    "logs": ["x"] * scan.MINIMUM_RECORDS["logs"],
                    "spans": ["x"] * scan.MINIMUM_RECORDS["spans"],
                    "metrics": ["x"] * scan.MINIMUM_RECORDS["metrics"],
                }
            )
            == []
        )

    def test_the_floor_is_checked_before_any_content_check(self):
        """Ordering is the whole point: a content check that runs first and finds nothing
        would print a clean result before the floor ever ran."""
        import inspect

        source = inspect.getsource(scan.run)
        assert source.index("check_capture_floor") < source.index("scan_records")


class TestSpansAndLabelsAreCoveredNotOnlyLogs:
    """Row 40 — this change adds most of its new surface there, and the foundation's
    redaction filter sits on neither."""

    def test_a_sentinel_only_in_a_span_attribute_is_found(self):
        findings = scan.scan_records(
            "spans", [f"span extraction_run entities.{scan.SENTINELS[0]}=3"]
        )

        assert findings
        assert "spans" in str(findings[0])

    def test_a_sentinel_only_in_a_metric_label_is_found(self):
        findings = scan.scan_records(
            "metrics",
            [f"__name__=ner_extraction_jobs_total tenant_id={scan.SENTINELS[3]}"],
        )

        assert findings
        assert "metrics" in str(findings[0])

    def test_all_three_backends_are_captured(self):
        import inspect

        source = inspect.getsource(scan.run)

        assert "capture_logs" in source
        assert "capture_spans" in source
        assert "capture_metric_labels" in source

    def test_spans_are_rendered_with_every_attribute_rather_than_filtered(self):
        """An attribute key nobody expected is exactly the one a leak arrives on, so the
        renderer must not select keys."""
        payload = {
            "batches": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "name": "extraction_run",
                                    "attributes": [
                                        {"key": "outcome", "value": {"stringValue": "succeeded"}},
                                        {
                                            "key": "a.key.nobody.declared",
                                            "value": {"stringValue": scan.SENTINELS[1]},
                                        },
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        rendered = scan._render_spans(payload)

        assert rendered
        assert scan.SENTINELS[1] in rendered[0]
        assert scan.scan_records("spans", rendered)


class TestTheSelfCheckIsTheSameLogic:
    """`--dry-run` is what CI can run without a stack, so it must exercise the real
    checkers rather than a parallel copy of them."""

    def test_the_self_check_passes(self):
        assert scan.self_check() == 0

    def test_it_exercises_the_real_checkers(self):
        import inspect

        source = inspect.getsource(scan.self_check)

        assert "scan_records(" in source
        assert "check_capture_floor(" in source


class TestExitCodesAreDistinguishable:
    """A pipeline has to tell 'leak' from 'the stack was down' from 'the capture was
    thin', because they need different responses and only one of them is a code change."""

    def test_the_documented_codes_appear_in_the_runner(self):
        import inspect

        source = inspect.getsource(scan.run)

        assert "return 1" in source  # a finding
        assert "return 2" in source  # capture too thin
        assert "return 3" in source  # backend unreachable
        assert "return 0" in source  # clean
