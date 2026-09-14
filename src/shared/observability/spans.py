"""Span helpers for the workload instrumentation.

Auto-instrumentation gives one span per HTTP request, per SQL statement and per Celery
task. What it cannot give is a span for a *stage* — the guardrail check, the resolution
attempt, the repair loop — because those are function calls, not protocol operations. This
module is the small amount of hand-written span code that fills that gap.

Two rules the whole change depends on:

- **Never raise.** A span that can fail the work it wraps is worse than no span. Every
  entry point here swallows its own errors, exactly as the foundation's exporters do.
- **Attributes are derived facts, never the underlying data.** Counts, categories,
  durations, enumerated outcomes. Never a question, an answer, a generated statement, a
  retrieved passage or an entity value — span attributes travel to the same collector as
  logs and are covered by the release-gate scan, so there is no "spans are safer" tier.
"""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_TRACER_NAME = "ner.workload"


def _tracer():
    from opentelemetry import trace

    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def stage_span(name: str, **attributes):
    """A span for one stage, yielding a setter for attributes decided inside the block.

        with stage_span("entity_resolution", tenant_scoped=True) as span:
            result = resolve()
            span.set("outcome", result.outcome)

    The yielded object is always usable, even when tracing is unavailable, so a call site
    never needs to check.
    """
    started = time.perf_counter()
    try:
        span_context = _tracer().start_as_current_span(name)
    except Exception:
        # No provider, or one that refused. The block still runs, with a setter that
        # discards — a call site never has to check whether tracing is available.
        logger.debug("stage_span_unavailable", extra={"stage": name}, exc_info=True)
        yield _Setter(None)
        return

    # Deliberately *not* inside the try above. An exception raised by the wrapped block
    # has to propagate untouched: catching it here would both swallow the caller's error
    # and resume this generator after a throw, which is itself a RuntimeError.
    with span_context as raw:
        setter = _Setter(raw)
        setter.set_many(attributes)
        try:
            yield setter
        finally:
            setter.set("duration_ms", round((time.perf_counter() - started) * 1000, 3))


class _Setter:
    """Attribute setter that is a no-op when there is no live span."""

    __slots__ = ("_span",)

    def __init__(self, span):
        self._span = span

    def set(self, key: str, value) -> None:
        if self._span is None or value is None:
            return
        try:
            if isinstance(value, bool | int | float | str):
                self._span.set_attribute(key, value)
            else:
                self._span.set_attribute(key, str(value))
        except Exception:
            logger.debug("span_attribute_dropped", extra={"attribute": key})

    def set_many(self, attributes: dict) -> None:
        for key, value in attributes.items():
            self.set(key, value)

    def record_error(self, exc: BaseException) -> None:
        """The exception's *class*, not its message.

        A driver message quotes the offending literal back — `invalid input syntax for
        type integer: "Priya"` — and a span attribute is not redacted anywhere.
        """
        self.set("error_class", type(exc).__name__)


def annotate_current_span(**attributes) -> None:
    """Add attributes to whichever span is already current, if any.

    Used where a stage span already exists — a LangSmith run id on the enclosing span, a
    node outcome — and creating a second one would only duplicate a duration.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return
        _Setter(span).set_many(attributes)
    except Exception:
        logger.debug("span_annotation_unavailable", exc_info=True)


def current_trace_id() -> str | None:
    """The ambient trace id as a 32-character hex string, or None outside a trace."""
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        if not context.is_valid:
            return None
        return format(context.trace_id, "032x")
    except Exception:
        return None
