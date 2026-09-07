"""Queue depth, wait time and execution duration are three different measurements.

Verification rows 15, 16 and 17.

They are separated because they answer different questions and have different owners.
Depth says "is work piling up" and belongs to whoever produces the work. Wait says "how
long before anything picked it up" and is a property of the message. Duration says "how
long the work took" and is a property of the worker. Collapsing any two of them produces a
number that cannot diagnose either failure.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm
from src.shared.observability import propagation

pytestmark = [pytest.mark.verification]

QUEUE = "extraction"


def _depth(queue: str = QUEUE) -> float:
    return float(REGISTRY.get_sample_value("ner_celery_queue_depth", {"queue": queue}) or 0.0)


def _wait_count(queue: str = QUEUE) -> float:
    value = REGISTRY.get_sample_value("ner_celery_task_wait_seconds_count", {"queue": queue})
    return float(value or 0.0)


def _wait_sum(queue: str = QUEUE) -> float:
    value = REGISTRY.get_sample_value("ner_celery_task_wait_seconds_sum", {"queue": queue})
    return float(value or 0.0)


def _duration_count(queue: str = QUEUE) -> float:
    value = REGISTRY.get_sample_value("ner_celery_task_duration_seconds_count", {"queue": queue})
    return float(value or 0.0)


def _failures(queue: str, error_class: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_celery_task_failures_total", {"queue": queue, "error_class": error_class}
    )
    return float(value or 0.0)


def _skew(queue: str = QUEUE) -> float:
    value = REGISTRY.get_sample_value("ner_celery_clock_skew_total", {"queue": queue})
    return float(value or 0.0)


class TestQueueDepth:
    """Row 15."""

    def test_a_backed_up_queue_reports_a_non_zero_depth(self):
        propagation.register_queue_depth_gauge = dm.register_queue_depth_gauge
        dm.register_queue_depth_gauge(QUEUE, lambda: 7)

        assert _depth() == 7

    def test_depth_is_read_at_scrape_time_rather_than_written_on_a_timer(self):
        """Occupancy is only true at the instant it is read — the same rule the
        foundation established for the database pool collector."""
        readings = iter([3, 11])
        dm.register_queue_depth_gauge(QUEUE, lambda: next(readings))

        assert _depth() == 3
        assert _depth() == 11

    def test_a_broker_that_cannot_be_reached_does_not_fail_the_scrape(self):
        def _explode():
            raise ConnectionError("redis is down")

        dm.register_queue_depth_gauge(QUEUE, _explode)

        assert _depth() == 0.0, (
            "a scraper polls a starting service well before its broker is reachable; a "
            "raising collector would take the whole endpoint down over one gauge"
        )

    def test_the_gauge_is_registered_on_the_producer_side(self):
        """Design Decision 6 — every worker reporting depth would produce N identical
        series differing only by instance."""
        import inspect

        source = inspect.getsource(propagation.register_queue_depth)
        assert "producer" in source

        from src.extraction_service import main as extraction_main

        assert "register_queue_depth" in inspect.getsource(extraction_main)


class TestWaitAndDurationAreSeparateObservations:
    """Row 16."""

    def test_they_are_two_families_not_one(self):
        assert dm.CELERY_TASK_WAIT.name != dm.CELERY_TASK_DURATION.name
        assert dm.CELERY_TASK_WAIT.label_names == ("queue",)
        assert dm.CELERY_TASK_DURATION.label_names == ("queue",)

    def test_a_wait_observation_does_not_touch_the_duration_family(self):
        wait_before = _wait_count()
        duration_before = _duration_count()

        dm.record_celery_wait(QUEUE, 4.0)

        assert _wait_count() == wait_before + 1
        assert _duration_count() == duration_before, (
            "a task that waited four seconds and ran for one is not the same as a task "
            "that waited one and ran for four, and one histogram cannot say which"
        )

    def test_a_duration_observation_does_not_touch_the_wait_family(self):
        wait_before = _wait_count()
        duration_before = _duration_count()

        dm.record_celery_duration(QUEUE, 2.0)

        assert _duration_count() == duration_before + 1
        assert _wait_count() == wait_before


class TestClockSkew:
    """Design Decision 7 — a negative wait is clamped and counted, so skew becomes visible
    rather than silently dragging the distribution left."""

    def test_a_negative_wait_is_clamped_to_zero(self):
        before_sum = _wait_sum()

        dm.record_celery_wait(QUEUE, -5.0)

        assert _wait_sum() == before_sum, "a negative wait must contribute nothing"

    def test_a_negative_wait_increments_the_skew_counter(self):
        before = _skew()

        dm.record_celery_wait(QUEUE, -0.5)

        assert _skew() == before + 1

    def test_a_positive_wait_leaves_the_skew_counter_alone(self):
        before = _skew()

        dm.record_celery_wait(QUEUE, 0.5)

        assert _skew() == before


class TestTaskFailures:
    """Row 17."""

    def test_a_raising_task_increments_under_its_exception_class(self):
        before = _failures(QUEUE, "ValueError")

        dm.record_celery_failure(QUEUE, ValueError("document 41ab-... could not be parsed"))

        assert _failures(QUEUE, "ValueError") == before + 1

    def test_no_message_text_reaches_the_label(self):
        dm.record_celery_failure(QUEUE, RuntimeError("failed on Priya Raman Resume 4.pdf"))

        offenders = [
            sample.labels
            for metric in REGISTRY.collect()
            if metric.name == "ner_celery_task_failures"
            for sample in metric.samples
            if any("Priya" in str(v) or "Resume" in str(v) for v in sample.labels.values())
        ]
        assert offenders == [], (
            f"a task failure message routinely carries the offending value: {offenders}"
        )

    def test_an_undeclared_exception_class_lands_on_other(self):
        exotic = type("SomeVendorSpecificError", (Exception,), {})()
        before = _failures(QUEUE, dm.OTHER)

        dm.record_celery_failure(QUEUE, exotic)

        assert _failures(QUEUE, dm.OTHER) == before + 1


class TestTheEnqueueHeader:
    """Design Decision 7's mechanism — a field on a hook that already exists."""

    def test_the_publish_hook_stamps_an_enqueue_timestamp(self):
        propagation._celery_patched = False
        propagation.instrument_celery()

        from celery import signals

        headers: dict = {}
        signals.before_task_publish.send(sender=None, headers=headers)

        assert propagation.CELERY_ENQUEUED_HEADER in headers
        assert isinstance(headers[propagation.CELERY_ENQUEUED_HEADER], float)

    def test_a_message_without_the_header_is_not_an_error(self):
        """The header is additive: a task enqueued by a producer that predates it must
        still run, and simply reports no wait."""

        class _Request:
            headers: dict = {}
            id = "task-1"
            delivery_info = {"routing_key": QUEUE}

        class _Task:
            request = _Request()

        before = _wait_count()
        propagation._record_wait(_Task())

        assert _wait_count() == before
