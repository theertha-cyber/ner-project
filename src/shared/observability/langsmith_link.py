"""One hop between a LangSmith run and the OTel trace it happened inside.

They are two views of the same LLM call. LangSmith holds the prompt and the completion;
OTel holds where that call sat in a ten-process request. The interesting failures need
both — "the answer was wrong" starts in LangSmith and ends in the trace, "the request took
eleven seconds" starts in the trace and ends in the prompt — and today there is no way to
get from either to the other.

So the link is written in both directions:

- the ambient OTel trace id becomes LangSmith run metadata;
- the LangSmith run id becomes an attribute on the enclosing span.

**Nothing here may fail a chat request.** LangSmith is off by default, is configured by
bare environment variables its own SDK reads (`.env.example:69-74`), and is a third-party
network dependency. Every operation is wrapped on its own — not one try around both — so
a change in the SDK that breaks one direction still leaves the other working. See design
Decision 8 and risk 6.
"""

import logging

logger = logging.getLogger(__name__)

TRACE_ID_METADATA_KEY = "otel_trace_id"
RUN_ID_SPAN_ATTRIBUTE = "langsmith.run_id"


def langsmith_extra() -> dict:
    """`langsmith_extra=` for one wrapped provider call, or `{}` when unavailable.

    Returns a plain dict rather than raising or returning None, so a call site can splat
    it unconditionally:

        response = await client.chat.completions.create(
            ..., langsmith_extra=langsmith_link.langsmith_extra()
        )

    When LangSmith is disabled the wrapper ignores the argument entirely, so the call is
    unchanged — which is the state every test process and every bare-metal run is in.
    """
    extra: dict = {}

    # Direction one: the trace id onto the run. Its own try — a failure to read the
    # ambient trace must not also cost the run-id link below.
    try:
        from src.shared.observability.spans import current_trace_id

        trace_id = current_trace_id()
        if trace_id:
            extra["metadata"] = {TRACE_ID_METADATA_KEY: trace_id}
    except Exception:
        logger.debug("langsmith_trace_metadata_unavailable", exc_info=True)

    # Direction two: the run id onto the span. The span is captured *now* rather than
    # looked up in the callback: `on_end` fires when the run closes, and there is no
    # guarantee the same span is still current at that point.
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            extra["on_end"] = _run_id_setter(span)
    except Exception:
        logger.debug("langsmith_run_id_link_unavailable", exc_info=True)

    return extra


def _run_id_setter(span):
    def _on_end(run_tree) -> None:
        try:
            run_id = getattr(run_tree, "id", None)
            if run_id is None:
                return
            span.set_attribute(RUN_ID_SPAN_ATTRIBUTE, str(run_id))
        except Exception:
            # A callback the SDK invokes on its own schedule. Raising here would surface
            # inside LangSmith's tracing machinery, which is the last place a telemetry
            # error should be able to reach.
            logger.debug("langsmith_run_id_not_recorded", exc_info=True)

    return _on_end
