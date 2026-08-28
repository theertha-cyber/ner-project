from types import SimpleNamespace

import pytest
from src.chat_api.services.guardrails import (
    FALLBACK_REPLY,
    INCOMPLETE_RETRIEVAL_REPLY,
    GuardrailService,
)
from src.chat_api.api.v1.schemas import Source
from src.shared.retrieval.orchestrator import (
    OUTCOME_EMPTY,
    OUTCOME_FAILED,
    OUTCOME_SKIPPED,
    CapabilityStatus,
    RetrievalStatus,
)

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class ScriptedClassifierClient:
    def __init__(self, verdict: str | None = None, raises: Exception | None = None):
        self.verdict = verdict
        self.raises = raises
        self.call_count = 0

        async def create(**kwargs):
            self.call_count += 1
            if self.raises is not None:
                raise self.raises
            message = SimpleNamespace(content=self.verdict)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class HistorySensitiveClassifierClient:
    """Returns a different verdict depending on whether conversation history was
    included in the call, so the two views `classify_domain` consults can be scripted
    independently. History is detected structurally: a bare call carries exactly the
    system prompt plus the user message."""

    def __init__(self, with_history: str, without_history: str):
        self.with_history = with_history
        self.without_history = without_history
        self.call_count = 0
        self.verdicts_served: list[str] = []

        async def create(**kwargs):
            self.call_count += 1
            messages = kwargs["messages"]
            verdict = self.without_history if len(messages) == 2 else self.with_history
            self.verdicts_served.append(verdict)
            message = SimpleNamespace(content=verdict)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class TestSourceCitationEnforcement:
    def setup_method(self):
        self.guardrails = GuardrailService()

    def test_empty_sources_rejected(self):
        reply = "Here is some information"
        result_reply, result_sources = self.guardrails.enforce_sources(reply, [])
        assert result_reply == "I couldn't find relevant information to answer that question."
        assert result_sources == []

    def test_non_empty_sources_passes(self):
        reply = "Here is some information"
        sources = [Source(source_type="sql", value="test", relevance_score=1.0)]
        result_reply, result_sources = self.guardrails.enforce_sources(reply, sources)
        assert result_reply == reply
        assert result_sources == sources

    def test_empty_retrieval_yields_no_match_reply(self):
        """verification.md row 14 — every attempted capability succeeded and found
        nothing. That is a real negative and the user should be told so."""
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="structured_retrieval", outcome=OUTCOME_EMPTY),
            CapabilityStatus(capability_name="semantic_retrieval", outcome=OUTCOME_EMPTY),
        ])
        reply, sources = self.guardrails.enforce_sources("Here is some information", [], status)

        assert reply == FALLBACK_REPLY
        assert sources == []

    def test_failed_retrieval_yields_incomplete_reply_not_absence(self):
        """verification.md row 15 — six upstream conditions used to collapse into one
        sentence, so a broken turn was indistinguishable from a genuine negative."""
        status = RetrievalStatus(entries=[
            CapabilityStatus(
                capability_name="structured_retrieval", outcome=OUTCOME_FAILED,
                error="SQL generation failed after 3 attempt(s)",
            ),
        ])
        reply, sources = self.guardrails.enforce_sources("Here is some information", [], status)

        assert reply == INCOMPLETE_RETRIEVAL_REPLY
        assert reply != FALLBACK_REPLY
        assert sources == []
        # Must not assert the data is absent.
        assert "couldn't find relevant information" not in reply
        assert "doesn't mean the information isn't in your data" in reply

    def test_skipped_recovery_also_yields_the_incomplete_reply(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="structured_retrieval", outcome=OUTCOME_EMPTY),
            CapabilityStatus(
                capability_name="semantic_retrieval", outcome=OUTCOME_SKIPPED,
                reason="insufficient remaining budget", recovery=True,
            ),
        ])
        reply, _ = self.guardrails.enforce_sources("Here is some information", [], status)
        assert reply == INCOMPLETE_RETRIEVAL_REPLY

    def test_absent_status_keeps_the_prior_reply(self):
        """A turn that never reached retrieval passes no status; behaviour is unchanged."""
        reply, sources = self.guardrails.enforce_sources("Here is some information", [], None)
        assert reply == FALLBACK_REPLY
        assert sources == []

    def test_failure_does_not_override_a_sourced_reply(self):
        status = RetrievalStatus(entries=[
            CapabilityStatus(capability_name="structured_retrieval", outcome=OUTCOME_FAILED, error="boom"),
        ])
        sources = [Source(source_type="sql", value="test", relevance_score=1.0)]
        reply, result_sources = self.guardrails.enforce_sources("Partial answer", sources, status)

        assert reply == "Partial answer"
        assert result_sources == sources

    # Note: verification.md row 48 ("Domain decline keeps its message") is verified at
    # the graph level (tests/test_chat_graph_topology.py), not here — the domain decline
    # is never passed through enforce_sources at all: a declined turn returns directly
    # from guardrail_node and never reaches generation_node, which is the only caller of
    # enforce_sources. There is no special-casing to test at this layer.


class TestDisclaimer:
    def setup_method(self):
        self.guardrails = GuardrailService()

    def test_disclaimer_injected(self):
        disclaimer = self.guardrails.inject_disclaimer()
        assert "generated by AI" in disclaimer
        assert "may contain errors" in disclaimer


class TestCrossTenantShortCircuit:
    """Covers verification.md row 44."""

    def setup_method(self):
        self.guardrails = GuardrailService()

    def test_cross_tenant_detected(self):
        reason = self.guardrails.check_blocked_question_type("How is tenant_abc doing?", tenant_id="tenant_xyz")
        assert reason is not None

    def test_same_tenant_not_blocked(self):
        reason = self.guardrails.check_blocked_question_type("How is our data?", tenant_id="tenant_xyz")
        assert reason is None

    def test_cross_tenant_short_circuits_without_llm_call(self):
        client = ScriptedClassifierClient(verdict="in_domain")
        reason = self.guardrails.check_blocked_question_type("How is tenant_abc doing?", tenant_id="tenant_xyz")

        assert reason == "cross_tenant"
        assert client.call_count == 0


class TestPiiShortCircuit:
    def setup_method(self):
        self.guardrails = GuardrailService()

    def test_pii_query_blocked(self):
        reason = self.guardrails.check_blocked_question_type("Show me social security numbers", tenant_id="tenant_xyz")
        assert reason == "pii"


class TestDomainClassification:
    """Covers verification.md rows 41-43, 45-46, 55."""

    def setup_method(self):
        self.guardrails = GuardrailService()

    @pytest.mark.parametrize("message", [
        "Who is the American president?",
        "Tell me a joke.",
        "What's the weather today?",
    ])
    async def test_out_of_domain_prompts_declined(self, message):
        client = ScriptedClassifierClient(verdict="out_of_domain")
        is_in_domain = await self.guardrails.classify_domain(message, None, client, "gpt-4o")
        assert is_in_domain is False

    async def test_in_domain_question_admitted(self):
        client = ScriptedClassifierClient(verdict="in_domain")
        is_in_domain = await self.guardrails.classify_domain("Which contracts mention Acme Corp?", None, client, "gpt-4o")
        assert is_in_domain is True

    async def test_classifier_failure_fails_open(self):
        client = ScriptedClassifierClient(raises=RuntimeError("classifier down"))
        is_in_domain = await self.guardrails.classify_domain("Which contracts mention Acme Corp?", None, client, "gpt-4o")
        assert is_in_domain is True

    async def test_history_induced_decline_is_overridden(self):
        """A question the classifier calls in-domain on its own must not be declined
        just because prior turns are prepended. Observed in production: "what tool
        frameworks has <candidate> used" classified in_domain with no history and
        out_of_domain 5/5 once ordinary earlier turns about that same candidate were
        included. Disagreement resolves to admit."""
        history = [{"role": "user", "content": "which candidates suit an AI engineer role"},
                   {"role": "assistant", "content": "Arjun Jayakumar built a RAG pipeline."}]
        client = HistorySensitiveClassifierClient(
            with_history="out_of_domain", without_history="in_domain",
        )
        admitted = await self.guardrails.classify_domain(
            "what tool frameworks has Arjun Jayakumar used", history, client, "gpt-4o",
        )
        assert admitted is True
        assert client.call_count == 2

    async def test_bare_out_of_domain_rescued_by_history(self):
        """The mirror case: an anaphoric follow-up ("and him?") reads as out-of-domain
        stripped of context, and history is what makes it legible. Admitting on
        disagreement has to hold in this direction too, or history stops earning its
        place in the call."""
        history = [{"role": "user", "content": "which candidates suit an AI engineer role"},
                   {"role": "assistant", "content": "Arjun Jayakumar built a RAG pipeline."}]
        client = HistorySensitiveClassifierClient(
            with_history="in_domain", without_history="out_of_domain",
        )
        admitted = await self.guardrails.classify_domain("and him?", history, client, "gpt-4o")
        assert admitted is True

    async def test_unanimous_out_of_domain_still_declines(self):
        """Genuine out-of-domain requests read the same way with and without history,
        so consensus still declines them — the rule loosens false declines without
        disarming the filter."""
        history = [{"role": "user", "content": "which candidates suit an AI engineer role"},
                   {"role": "assistant", "content": "Arjun Jayakumar built a RAG pipeline."}]
        client = HistorySensitiveClassifierClient(
            with_history="out_of_domain", without_history="out_of_domain",
        )
        admitted = await self.guardrails.classify_domain("tell me a joke", history, client, "gpt-4o")
        assert admitted is False

    async def test_no_history_makes_a_single_call(self):
        """With no history the two views are the same call, so only one is made."""
        client = HistorySensitiveClassifierClient(
            with_history="in_domain", without_history="in_domain",
        )
        await self.guardrails.classify_domain("Which contracts mention Acme Corp?", None, client, "gpt-4o")
        assert client.call_count == 1

    def test_no_complexity_assessment_method_remains(self):
        """Covers verification.md row 55: complexity assessment is removed entirely."""
        assert not hasattr(self.guardrails, "assess_complexity")
        assert not hasattr(self.guardrails, "check_blocked_question")

    def test_multi_lookup_question_is_not_a_guardrail_concern(self):
        """Covers verification.md row 46: the guardrail has no complexity notion at all
        — multi-lookup questions are only ever a matter for the orchestrator."""
        assert not hasattr(self.guardrails, "MAX_COMPLEXITY_SCORE")
