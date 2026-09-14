"""LLM calls report tokens, latency and an outcome — and never the provider's words.

Verification row 5.

Provider spend is one of the five things allowed to carry a `tenant_id` label, because
consumption attribution is not answerable from traces: sampling makes a consumption figure
wrong by construction, and a billing number has to be exact. That makes this file the one
place where the tenant label is deliberately exercised rather than deliberately excluded.

The error-class assertions are the other half. A provider's error body can echo the prompt
back — a rate-limit or content-filter message routinely quotes the request — so only
`type(e).__name__`, mapped into a declared set, becomes a label.
"""

from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

OPERATION = "sql_generation"
TENANT = "tenant-a"


def _calls(outcome: str, error_class: str = dm.NONE, operation: str = OPERATION) -> float:
    value = REGISTRY.get_sample_value(
        "ner_llm_calls_total",
        {"operation": operation, "outcome": outcome, "error_class": error_class},
    )
    return float(value or 0.0)


def _tokens(direction: str, tenant_id: str = TENANT, operation: str = OPERATION) -> float:
    value = REGISTRY.get_sample_value(
        "ner_llm_tokens_total",
        {"tenant_id": tenant_id, "operation": operation, "direction": direction},
    )
    return float(value or 0.0)


def _latency_observations(operation: str = OPERATION) -> float:
    value = REGISTRY.get_sample_value("ner_llm_duration_seconds_count", {"operation": operation})
    return float(value or 0.0)


def _response(prompt_tokens=None, completion_tokens=None):
    usage = (
        SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        if prompt_tokens is not None
        else None
    )
    return SimpleNamespace(usage=usage, choices=[])


class TestASuccessfulCall:
    """Row 5's first clause."""

    async def test_it_records_tokens_in_and_out_latency_and_an_outcome(self):
        before_calls = _calls("success")
        before_in = _tokens("input")
        before_out = _tokens("output")
        before_latency = _latency_observations()

        async with dm.measure_llm_call(OPERATION, TENANT) as call:
            call.usage(_response(prompt_tokens=120, completion_tokens=35))

        assert _calls("success") == before_calls + 1
        assert _tokens("input") == before_in + 120
        assert _tokens("output") == before_out + 35
        assert _latency_observations() == before_latency + 1

    async def test_latency_is_measured_around_the_provider_call_only(self):
        """The whole point of a per-call histogram: a slow stage containing a fast LLM
        call and a slow retrieval is exactly the ambiguity this change removes."""
        import asyncio

        async with dm.measure_llm_call(OPERATION, TENANT) as call:
            await asyncio.sleep(0.02)
            call.usage(_response(1, 1))

        total = REGISTRY.get_sample_value("ner_llm_duration_seconds_sum", {"operation": OPERATION})
        assert total >= 0.02

    async def test_a_streamed_response_records_latency_without_inventing_tokens(self):
        before_in = _tokens("input", operation="answer_generation")
        before_calls = _calls("success", operation="answer_generation")

        async with dm.measure_llm_call("answer_generation", TENANT) as call:
            call.usage(_response())  # no usage block, as on a stream

        assert _calls("success", operation="answer_generation") == before_calls + 1
        assert _tokens("input", operation="answer_generation") == before_in, (
            "a stream carries no usage unless it is requested; a guessed count is worse "
            "than no count when the number is destined for a billing dashboard"
        )


class TestAFailedCall:
    """Row 5's second clause."""

    async def test_the_exception_propagates_untouched(self):
        with pytest.raises(TimeoutError):
            async with dm.measure_llm_call(OPERATION, TENANT):
                raise TimeoutError("provider did not answer")

    async def test_it_records_an_enumerated_error_class(self):
        before = _calls("error", "TimeoutError")

        with pytest.raises(TimeoutError):
            async with dm.measure_llm_call(OPERATION, TENANT):
                raise TimeoutError("provider did not answer")

        assert _calls("error", "TimeoutError") == before + 1

    async def test_no_provider_message_text_reaches_any_label(self):
        message = "rate limit exceeded for prompt: who is Priya Raman"

        with pytest.raises(RuntimeError):
            async with dm.measure_llm_call(OPERATION, TENANT):
                raise RuntimeError(message)

        offenders = [
            (metric.name, sample.labels)
            for metric in REGISTRY.collect()
            for sample in metric.samples
            if any("Priya" in str(v) or "rate limit" in str(v) for v in sample.labels.values())
        ]
        assert offenders == [], (
            f"a provider error body routinely quotes the prompt back: {offenders}"
        )

    async def test_a_failed_call_still_records_its_latency(self):
        before = _latency_observations()

        with pytest.raises(ValueError):
            async with dm.measure_llm_call(OPERATION, TENANT):
                raise ValueError("bad request")

        assert _latency_observations() == before + 1, (
            "a call that failed after eight seconds is the interesting one; recording "
            "latency only on success hides exactly the slow failures"
        )

    def test_an_undeclared_exception_class_lands_on_other(self):
        exotic = type("SomeProviderSpecificError", (Exception,), {})()

        assert dm.error_class(exotic) == dm.OTHER


class TestCost:
    """Cost is derived from configured rates, not from a table in source."""

    def test_cost_is_zero_when_no_rates_are_configured(self, monkeypatch):
        from src.shared.config import settings

        monkeypatch.setattr(settings, "llm_cost_per_1k_input_usd", 0.0)
        monkeypatch.setattr(settings, "llm_cost_per_1k_output_usd", 0.0)

        assert dm.estimate_llm_cost_usd(1000, 1000) == 0.0

    def test_cost_follows_the_configured_rates(self, monkeypatch):
        from src.shared.config import settings

        monkeypatch.setattr(settings, "llm_cost_per_1k_input_usd", 0.5)
        monkeypatch.setattr(settings, "llm_cost_per_1k_output_usd", 1.5)

        assert dm.estimate_llm_cost_usd(2000, 1000) == pytest.approx(1.0 + 1.5)

    async def test_spend_accumulates_under_the_tenant_label(self, monkeypatch):
        from src.shared.config import settings

        monkeypatch.setattr(settings, "llm_cost_per_1k_input_usd", 1.0)
        monkeypatch.setattr(settings, "llm_cost_per_1k_output_usd", 0.0)

        def _cost():
            value = REGISTRY.get_sample_value(
                "ner_llm_cost_usd_total", {"tenant_id": TENANT, "operation": OPERATION}
            )
            return float(value or 0.0)

        before = _cost()
        async with dm.measure_llm_call(OPERATION, TENANT) as call:
            call.usage(_response(prompt_tokens=1000, completion_tokens=0))

        assert _cost() == pytest.approx(before + 1.0)

    def test_the_tenant_labelled_families_are_exactly_the_allowlisted_ones(self):
        assert "ner_llm_tokens_total" in dm.TENANT_LABEL_ALLOWLIST
        assert "ner_llm_cost_usd_total" in dm.TENANT_LABEL_ALLOWLIST
        assert "ner_llm_calls_total" not in dm.TENANT_LABEL_ALLOWLIST, (
            "the call *count* is answerable from a trace; only the consumption figures "
            "need to be exact, and only they carry the label"
        )
        assert "tenant_id" not in dm.LLM_DURATION.label_names


class TestTenantAttributionFallsBackToTheRequestContext:
    """Found on the running stack, not in a test.

    Three of the four LLM operations — the guardrail classifier, the retrieval planner and
    the SQL generator — are several frames below the request boundary and hold no tenant
    argument. They were attributing every token to `tenant_id="unknown"`, which left only
    `answer_generation` correctly attributed and made the two allowlisted consumption
    families useless for the billing question that justifies the label at all.
    """

    async def test_an_omitted_tenant_is_taken_from_the_ambient_context(self):
        from src.shared.observability.context import reset_context, set_tenant_id

        set_tenant_id("tenant-from-context")
        try:
            async with dm.measure_llm_call("sql_generation") as call:
                call.usage(_response(prompt_tokens=10, completion_tokens=5))
        finally:
            reset_context()

        value = REGISTRY.get_sample_value(
            "ner_llm_tokens_total",
            {
                "tenant_id": "tenant-from-context",
                "operation": "sql_generation",
                "direction": "input",
            },
        )
        assert value == 10, (
            "a call site with no tenant argument must still attribute to the request's "
            "tenant, or most of the platform's token volume lands under `unknown`"
        )

    async def test_an_explicit_tenant_still_wins(self):
        from src.shared.observability.context import reset_context, set_tenant_id

        set_tenant_id("tenant-from-context")
        try:
            async with dm.measure_llm_call("answer_generation", "tenant-explicit") as call:
                call.usage(_response(prompt_tokens=7, completion_tokens=1))
        finally:
            reset_context()

        value = REGISTRY.get_sample_value(
            "ner_llm_tokens_total",
            {
                "tenant_id": "tenant-explicit",
                "operation": "answer_generation",
                "direction": "input",
            },
        )
        assert value == 7

    async def test_no_context_and_no_argument_is_still_recorded(self):
        """Attribution degrades to `unknown` rather than dropping the observation — a lost
        token count is worse than an unattributed one."""
        from src.shared.observability.context import reset_context

        reset_context()
        async with dm.measure_llm_call("entity_selection") as call:
            call.usage(_response(prompt_tokens=3, completion_tokens=1))

        value = REGISTRY.get_sample_value(
            "ner_llm_tokens_total",
            {"tenant_id": "unknown", "operation": "entity_selection", "direction": "input"},
        )
        assert value == 3
