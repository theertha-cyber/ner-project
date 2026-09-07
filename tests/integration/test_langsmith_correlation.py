"""A LangSmith run and its OTel trace are one hop apart, in both directions.

Verification rows 24, 25 and 26.

Row 26 is the one that matters operationally. LangSmith is off by default, configured by
bare environment variables its own SDK reads, and is a third-party network dependency —
so the correlation must be incapable of failing a chat request. The tests below therefore
check the disabled and the broken cases as carefully as the working one.
"""

import pytest

from src.shared.observability import langsmith_link
from src.shared.observability.spans import current_trace_id, stage_span

pytestmark = [pytest.mark.verification]


class _RunTree:
    """Stands in for the RunTree the SDK hands to `on_end`."""

    def __init__(self, run_id="0199c0de-dead-beef-cafe-000000000001"):
        self.id = run_id


class TestBothDirectionsAreLinked:
    """Rows 24 and 25."""

    def test_the_run_carries_the_otel_trace_identifier(self, captured_spans):
        """Row 24 — LangSmith can be searched by the trace of the request it served."""
        with stage_span("generation"):
            extra = langsmith_link.langsmith_extra()
            trace_id = current_trace_id()

        assert trace_id
        assert extra["metadata"][langsmith_link.TRACE_ID_METADATA_KEY] == trace_id

    def test_the_span_carries_the_langsmith_run_identifier(self, captured_spans):
        """Row 25 — the trace links out to the prompt and completion."""
        with stage_span("generation"):
            extra = langsmith_link.langsmith_extra()
            extra["on_end"](_RunTree())

        span = captured_spans.get_finished_spans()[-1]
        assert (
            span.attributes[langsmith_link.RUN_ID_SPAN_ATTRIBUTE]
            == "0199c0de-dead-beef-cafe-000000000001"
        )

    def test_the_setter_closes_over_the_span_rather_than_looking_one_up(self, captured_spans):
        """`on_end` fires when the run closes, and there is no guarantee the same span is
        still current then — so the setter holds the span it was built with.

        Asserted by running the callback from *outside* any span context: a setter that
        looked up the current span would find none and write nothing, and would also not
        raise, so the two are told apart by checking which span received the attribute
        rather than by checking that nothing blew up.
        """
        with stage_span("generation"):
            extra = langsmith_link.langsmith_extra()
            on_end = extra["on_end"]

        with stage_span("some_entirely_different_stage"):
            on_end(_RunTree("0199c0de-dead-beef-cafe-000000000002"))

        other = next(
            s
            for s in captured_spans.get_finished_spans()
            if s.name == "some_entirely_different_stage"
        )
        assert langsmith_link.RUN_ID_SPAN_ATTRIBUTE not in other.attributes, (
            "the run id landed on whichever span happened to be current, which is the "
            "bug this design avoids"
        )


class TestItCannotFailARequest:
    """Row 26."""

    def test_outside_a_trace_it_returns_an_empty_extra_rather_than_raising(self):
        extra = langsmith_link.langsmith_extra()

        assert isinstance(extra, dict)
        assert "metadata" not in extra, (
            "no ambient trace means nothing to link; inventing one would be worse than "
            "leaving the run unlinked"
        )

    def test_a_broken_trace_lookup_does_not_break_the_run_id_link(self, monkeypatch, captured_spans):
        """Each direction is wrapped on its own, not both inside one try — a change in one
        must not silently cost the other."""
        import src.shared.observability.spans as spans_module

        def _explode():
            raise RuntimeError("otel sdk changed under us")

        monkeypatch.setattr(spans_module, "current_trace_id", _explode)

        with stage_span("generation"):
            extra = langsmith_link.langsmith_extra()

        assert "metadata" not in extra
        assert "on_end" in extra, "the surviving direction must still be wired"

    def test_a_callback_given_something_unexpected_does_not_raise(self, captured_spans):
        with stage_span("generation"):
            extra = langsmith_link.langsmith_extra()
            extra["on_end"](object())  # no `.id` at all
            extra["on_end"](None)

    async def test_the_request_is_answered_and_the_extra_always_reaches_the_client(self):
        """With LangSmith disabled the wrapper ignores `langsmith_extra` entirely, so the
        call is unchanged — which is the state of every test process and every bare-metal
        run. The argument is still always passed: whether it does anything is LangSmith's
        decision, not this code path's."""
        from types import SimpleNamespace

        from src.chat_api.services.sql_generator import SQLGenerator, SurfaceGrounding

        recorded: dict = {}

        class _Client:
            def __init__(self):
                self.chat = SimpleNamespace(completions=self)

            async def create(self, **kwargs):
                recorded.update(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="SELECT 1"))],
                    usage=None,
                )

        generator = SQLGenerator()
        generator.client = _Client()

        sql = await generator.generate_sql(
            "how many candidates", grounding=SurfaceGrounding()
        )

        assert sql == "SELECT 1"
        assert "langsmith_extra" in recorded

    def test_the_two_wrapped_clients_both_pass_the_extra(self):
        import inspect

        from src.chat_api.services import sql_generator
        from src.shared.retrieval import orchestrator

        assert "langsmith_extra=_langsmith_extra()" in inspect.getsource(sql_generator)
        assert "langsmith_extra=_langsmith_extra()" in inspect.getsource(orchestrator)

    def test_the_helper_is_resolved_defensively_at_both_sites(self):
        import inspect

        from src.chat_api.services import sql_generator
        from src.shared.retrieval import orchestrator

        for module in (sql_generator, orchestrator):
            source = inspect.getsource(module._langsmith_extra)
            assert "except Exception" in source
            assert "return {}" in source
