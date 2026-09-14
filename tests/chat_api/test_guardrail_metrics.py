"""Guardrail decisions are counted by rule, and a fail-open is not an admission.

Verification rows 7, 8 and 9.

The load-bearing assertion in this file is that `ner_guardrail_fail_open_total` and
`ner_guardrail_decisions_total{decision="admitted"}` are different series. A classifier
that has started raising on every call still admits every query — which is by design, the
guardrail is a scope filter and not a security boundary — but a fail-open folded into the
admit count makes a control degrading to zero effectiveness look exactly like a control
working normally.
"""

import pytest
from prometheus_client import REGISTRY

from src.chat_api.services import guardrails as guardrails_module
from src.chat_api.services.guardrails import (
    FALLBACK_REPLY,
    INCOMPLETE_RETRIEVAL_REPLY,
    RULE_CROSS_TENANT,
    RULE_DOMAIN,
    RULE_PII,
    RULE_SOURCES,
    GuardrailService,
)
from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


def _decisions(rule: str, decision: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_guardrail_decisions_total", {"rule": rule, "decision": decision}
    )
    return float(value or 0.0)


def _fail_open(error_class: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_guardrail_fail_open_total", {"error_class": error_class}
    )
    return float(value or 0.0)


class _Classifier:
    """A stand-in for the OpenAI client, returning a fixed verdict or raising."""

    def __init__(self, verdict: str | None = "in_domain", raises: Exception | None = None):
        self.verdict = verdict
        self.raises = raises
        self.chat = self
        self.completions = self

    async def create(self, **_kwargs):
        if self.raises is not None:
            raise self.raises
        message = type("M", (), {"content": self.verdict})()
        return type("R", (), {"choices": [type("C", (), {"message": message})()]})()


class TestBlockedQuestionTypes:
    """Row 7 — the deterministic short-circuits."""

    def test_a_cross_tenant_reference_increments_its_own_rule(self):
        before = _decisions(RULE_CROSS_TENANT, "blocked")

        outcome = GuardrailService().check_blocked_question_type(
            "show me everything in tenant_someone_else", "my-tenant"
        )

        assert outcome == RULE_CROSS_TENANT
        assert _decisions(RULE_CROSS_TENANT, "blocked") == before + 1

    def test_a_pii_request_increments_a_different_rule(self):
        cross_before = _decisions(RULE_CROSS_TENANT, "blocked")
        pii_before = _decisions(RULE_PII, "blocked")

        outcome = GuardrailService().check_blocked_question_type(
            "give me the social security number details for everyone", "my-tenant"
        )

        assert outcome == RULE_PII
        assert _decisions(RULE_PII, "blocked") == pii_before + 1
        assert _decisions(RULE_CROSS_TENANT, "blocked") == cross_before, (
            "which rule fired is the diagnostic value; one counter for 'blocked' would "
            "lose it"
        )

    def test_an_ordinary_question_blocks_nothing(self):
        before = (
            _decisions(RULE_CROSS_TENANT, "blocked"),
            _decisions(RULE_PII, "blocked"),
        )

        assert GuardrailService().check_blocked_question_type(
            "how many candidates have a python skill", "my-tenant"
        ) is None
        assert (
            _decisions(RULE_CROSS_TENANT, "blocked"),
            _decisions(RULE_PII, "blocked"),
        ) == before


class TestTheFailOpenIsItsOwnSignal:
    """Row 8 — the assertion this file exists for."""

    async def test_a_raising_classifier_increments_the_fail_open_counter(self):
        service = GuardrailService()
        before = _fail_open("ConnectionError")

        admitted = await service.classify_domain(
            "how many candidates do we have", None, _Classifier(raises=ConnectionError("boom")), "gpt"
        )

        assert admitted is True, "behaviour is unchanged — this change measures only"
        assert _fail_open("ConnectionError") == before + 1

    async def test_a_fail_open_is_distinguishable_from_a_genuine_admission(self):
        service = GuardrailService()
        fail_open_before = _fail_open("RuntimeError")
        admit_before = _decisions(RULE_DOMAIN, "admitted")

        await service.classify_domain("a real question", None, _Classifier("in_domain"), "gpt")

        assert _decisions(RULE_DOMAIN, "admitted") == admit_before + 1
        assert _fail_open("RuntimeError") == fail_open_before, (
            "a genuine in-domain verdict must not touch the fail-open counter"
        )

        await service.classify_domain(
            "a real question", None, _Classifier(raises=RuntimeError("provider down")), "gpt"
        )

        assert _fail_open("RuntimeError") == fail_open_before + 1

    async def test_an_out_of_domain_verdict_is_counted_as_blocked(self):
        before = _decisions(RULE_DOMAIN, "blocked")

        admitted = await GuardrailService().classify_domain(
            "tell me a joke", None, _Classifier("out_of_domain"), "gpt"
        )

        assert admitted is False
        assert _decisions(RULE_DOMAIN, "blocked") == before + 1

    def test_the_error_class_label_carries_no_message_text(self):
        """`str(e)` on a provider error can quote the request back. Only the class name is
        a label, and only when it is one of the declared ones."""
        assert dm.error_class(ConnectionError("connecting to https://api.example/v1 failed")) == "ConnectionError"
        assert dm.error_class(type("SomethingNobodyDeclared", (Exception,), {})()) == dm.OTHER


class TestTheEmptySourcesFallback:
    """Row 9."""

    def test_the_plain_fallback_increments_the_sources_rule(self):
        before = _decisions(RULE_SOURCES, "fallback")

        reply, sources = GuardrailService().enforce_sources("some reply", [])

        assert reply == FALLBACK_REPLY
        assert sources == []
        assert _decisions(RULE_SOURCES, "fallback") == before + 1

    def test_the_incomplete_retrieval_fallback_also_increments_it(self):
        class _Status:
            def has_failure_or_skip(self):
                return True

            def failed_capability_names(self):
                return ["semantic_retrieval"]

            def skips(self):
                return []

        before = _decisions(RULE_SOURCES, "fallback")

        reply, _ = GuardrailService().enforce_sources("some reply", [], _Status())

        assert reply == INCOMPLETE_RETRIEVAL_REPLY
        assert _decisions(RULE_SOURCES, "fallback") == before + 1

    def test_a_cited_answer_is_counted_as_admitted(self):
        before = _decisions(RULE_SOURCES, "admitted")

        reply, sources = GuardrailService().enforce_sources("cited reply", ["a source"])

        assert reply == "cited reply"
        assert sources == ["a source"]
        assert _decisions(RULE_SOURCES, "admitted") == before + 1, (
            "ADR-007's citation enforcement becomes counted, not merely executed"
        )


class TestTheRuleIdentifiersAreShared:
    """Task 1.2 — the observability module imports these rather than restating them, so a
    rename must break an import instead of emitting a label nothing matches."""

    def test_the_declared_label_values_are_the_module_s_own_constants(self):
        assert dm.GUARDRAIL_DECISIONS.labels[0].values >= guardrails_module.GUARDRAIL_RULES
        assert guardrails_module.GUARDRAIL_RULES == {
            RULE_CROSS_TENANT,
            RULE_PII,
            RULE_DOMAIN,
            RULE_SOURCES,
        }
