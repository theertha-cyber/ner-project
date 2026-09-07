import asyncio
import re
import logging
from src.shared.conversation_history import recent_messages
from src.chat_api.api.v1.schemas import Source, Citation, ChatResponse

logger = logging.getLogger(__name__)

PII_PATTERN = re.compile(r"(ssn|social security|credit card|passport|driver.?s license)\s+(number|info|details)", re.IGNORECASE)

# The rules this service can decide under. Named constants rather than string literals at
# the return sites, because they are also the enumerated label values on
# `ner_guardrail_decisions_total` — a rename here must break the observability module's
# import rather than leave a stale label that no dashboard matches.
RULE_CROSS_TENANT = "cross_tenant"
RULE_PII = "pii"
RULE_DOMAIN = "domain"
RULE_SOURCES = "sources"

GUARDRAIL_RULES = frozenset({RULE_CROSS_TENANT, RULE_PII, RULE_DOMAIN, RULE_SOURCES})

FALLBACK_REPLY = "I couldn't find relevant information to answer that question."

# Six distinct upstream conditions used to collapse into FALLBACK_REPLY, so a broken
# turn and a genuine negative were indistinguishable — to the user and in production
# logs. This reply is for the broken case and deliberately asserts nothing about
# whether the data exists.
INCOMPLETE_RETRIEVAL_REPLY = (
    "I couldn't complete the search for that question — one of the sources I use failed "
    "while retrieving. This doesn't mean the information isn't in your data. Please try "
    "again in a moment."
)

DOMAIN_DECLINE_REPLY = (
    "I can only answer questions about your tenant's documents and the entities "
    "extracted from them. I can't help with that."
)

DOMAIN_CLASSIFIER_SYSTEM_PROMPT = """You are a domain filter for a multi-tenant document and \
entity-extraction platform. Each tenant uploads its own documents (which could be contracts, \
resumes, invoices, medical records, support tickets, or any other document type) and the \
platform extracts structured entities from them (e.g. names, dates, organizations, skills, \
amounts — whatever entity types that tenant has configured). The platform then answers \
questions about that tenant's uploaded documents and the entities extracted from them: \
lookups, filters, counts, aggregates, comparisons, and semantic search over document content, \
on ANY subject matter the tenant's documents happen to cover.

Decide whether the user's message is a question seeking information from the tenant's own \
documents/extracted entities (in_domain), or a request for something the platform has no \
access to and was never meant to do — general knowledge, entertainment, unrelated content \
generation, or requests entirely unconnected to any document or entity data (out_of_domain).

Respond with exactly one word: "in_domain" or "out_of_domain".

In-domain examples (note: the subject matter varies by tenant — all of these are valid):
- "How many organizations did we extract?"
- "Which contracts mention Acme Corp?"
- "Summarize the findings in this contract."
- "Compare what document A and document B say about liability."
- "What entities appear on page 3 of the uploaded lease?"
- "Find me candidates who graduated in 2026."
- "Is Arjun a good AI engineer?" (a lookup/judgement over this tenant's resume data)
- "Find me candidates for a Backend Engineer role, preferably at an MNC."
- "Which invoices are overdue?"
- "List patients diagnosed with hypertension."
- "Rank programming languages by popularity" (a ranking/frequency question over this tenant's own extracted entity values — "popularity" here means how often a value appears in the data, never general-knowledge/industry trivia)
- "What's the most common job title?" / "Which skill is most in-demand among our candidates?"

Out-of-domain examples (requests with no connection to any tenant document or extracted entity):
- "Who is the American president?"
- "Tell me a joke."
- "What's the weather today?"
- "Write me a poem about the ocean."
- "What's 2+2?"

When in doubt, prefer in_domain: this classifier's job is only to filter out requests with \
no plausible connection to tenant document/entity data, not to judge whether the platform can \
fully answer the specific question. In particular, words like "popular", "common", "top", \
"most", or "ranked" do NOT make a question out-of-domain trivia — the platform only ever has \
access to this tenant's own extracted data, so a ranking/frequency word always means "ranked \
within our documents," never "ranked in the real world."
"""


def _metrics():
    """The domain-metric recorders, resolved on first use.

    `domain_metrics` imports `GUARDRAIL_RULES` from this module so that renaming a rule is
    an ImportError there rather than a label value no dashboard matches. Importing it back
    at module scope would close that cycle.
    """
    from src.shared.observability import domain_metrics

    return domain_metrics


class GuardrailService:
    def check_blocked_question_type(self, message: str, tenant_id: str) -> str | None:
        """Deterministic short-circuits that decline without an LLM call: a reference to
        another tenant's schema, or a request for PII not present in extracted entities.
        Everything else is left to `classify_domain`."""
        cross_tenant = re.search(rf"(?!\b{re.escape(tenant_id)}\b)\btenant_\w+\b", message, re.IGNORECASE) if tenant_id else False
        if cross_tenant:
            logger.info("Cross-tenant query detected")
            _metrics().record_guardrail_decision(RULE_CROSS_TENANT, "blocked")
            return RULE_CROSS_TENANT
        if PII_PATTERN.search(message):
            logger.info("PII query detected")
            _metrics().record_guardrail_decision(RULE_PII, "blocked")
            return RULE_PII
        return None

    async def _classify_once(self, message: str, history: list[dict], llm_client, llm_model: str) -> bool:
        """One classifier call. Returns True (in-domain) on any error, so a provider
        failure never manifests as a decline."""
        messages = [{"role": "system", "content": DOMAIN_CLASSIFIER_SYSTEM_PROMPT}]
        for turn in history:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": message})

        try:
            async with _metrics().measure_llm_call("domain_classification") as call:
                response = await llm_client.chat.completions.create(
                    model=llm_model, messages=messages, temperature=0, max_tokens=5,
                )
                call.usage(response)
            verdict = (response.choices[0].message.content or "").strip().lower()
            return "out_of_domain" not in verdict
        except Exception as e:
            logger.warning(
                "domain_classifier_failed",
                extra={"outcome": "fail_open_admitted", "error_class": type(e).__name__},
            )
            # A dedicated counter, deliberately not the admit counter. A fail-open that
            # increments `decisions{rule="domain",decision="admitted"}` is a security
            # control degrading invisibly inside a normal-looking series. Behaviour is
            # unchanged here — whether this should keep failing open is flagged in
            # design.md's Open Questions and belongs to its own change.
            _metrics().record_guardrail_fail_open(e)
            return True

    async def classify_domain(self, message: str, conversation_context: list[dict] | None, llm_client, llm_model: str) -> bool:
        """Returns True if the query is in-domain. Fails open (treats the query as
        in-domain) on any classifier error, since tenant isolation is enforced
        structurally elsewhere and an unsourced answer is already refused downstream —
        the guardrail here is a scope/cost filter, not a security boundary.

        Blocks only when the message reads as out-of-domain BOTH with and without the
        conversation history. History is genuinely load-bearing — "and him?" or "tell me
        more" classify as out-of-domain stripped of context and in-domain with it — but
        it also flips clearly in-domain questions the other way: "what tool frameworks has
        <candidate> used" classified in_domain 5/5 bare and out_of_domain 5/5 once a few
        ordinary prior turns about that same candidate were prepended. Neither view is
        trustworthy alone, and the two failure directions are not symmetric: admitting an
        out-of-domain question costs one wasted retrieval, while declining a real one is
        user-visible breakage that also persists — the decline is written to the
        conversation and fed back here on the next turn. So the two views are consulted
        concurrently (no added latency; each is a `max_tokens=5` call) and disagreement
        resolves to admit. Only unanimous out-of-domain declines."""
        history = recent_messages(conversation_context)
        if not history:
            in_domain = await self._classify_once(message, [], llm_client, llm_model)
            _metrics().record_guardrail_decision(
                RULE_DOMAIN, "admitted" if in_domain else "blocked"
            )
            return in_domain

        with_history, without_history = await asyncio.gather(
            self._classify_once(message, history, llm_client, llm_model),
            self._classify_once(message, [], llm_client, llm_model),
        )
        if with_history != without_history:
            logger.info(
                "Domain classifier split (with_history=%s bare=%s), admitting query",
                with_history, without_history,
            )
            # The split is its own outcome, not an ordinary admission. Both views are
            # untrustworthy alone and disagreement always resolves to admit, so a rising
            # split rate is the signal that the classifier is drifting — invisible if it
            # were folded into the admit count.
            _metrics().record_guardrail_classifier_split()

        in_domain = with_history or without_history
        _metrics().record_guardrail_decision(
            RULE_DOMAIN, "admitted" if in_domain else "blocked"
        )
        return in_domain

    def enforce_sources(
        self,
        reply: str,
        sources: list[Source | Citation],
        retrieval_status=None,
    ) -> tuple[str, list[Source | Citation]]:
        """Only `generation_node` calls this. An entity-resolution clarification reply
        never reaches `generation_node` — `entity_resolution_node` routes straight to
        END on ambiguity — so a clarification's empty `sources` is never subject to
        this check by construction, not by a special case here. See design.md
        Decision 1 and the `chat-api` delta spec's guardrail exemption requirement.

        With no sources, the reply depends on *why* there are none. Every attempted
        capability succeeded and found nothing: that is a real negative and the user
        should be told so. Any capability failed or was skipped: the turn is incomplete
        and asserting absence would be a false statement about the tenant's data. The
        distinction comes from `retrieval_status`, never from inspecting the reply."""
        if sources:
            _metrics().record_guardrail_decision(RULE_SOURCES, "admitted")
            return reply, sources

        if retrieval_status is not None and retrieval_status.has_failure_or_skip():
            failed = retrieval_status.failed_capability_names()
            skipped = sorted({e.capability_name for e in retrieval_status.skips()})
            logger.warning(
                "Guardrail: empty sources after retrieval failure failed=%s skipped=%s",
                failed or None, skipped or None,
            )
            _metrics().record_guardrail_decision(RULE_SOURCES, "fallback")
            return INCOMPLETE_RETRIEVAL_REPLY, []

        logger.warning("Guardrail: empty sources detected, returning fallback reply")
        _metrics().record_guardrail_decision(RULE_SOURCES, "fallback")
        return FALLBACK_REPLY, []

    def inject_disclaimer(self) -> str:
        return "This answer was generated by AI and may contain errors. Verify important information against source documents."
