import re
import logging
from src.chat_api.api.v1.schemas import Source, Citation, ChatResponse

logger = logging.getLogger(__name__)

PII_PATTERN = re.compile(r"(ssn|social security|credit card|passport|driver.?s license)\s+(number|info|details)", re.IGNORECASE)

FALLBACK_REPLY = "I couldn't find relevant information to answer that question."

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


class GuardrailService:
    def check_blocked_question_type(self, message: str, tenant_id: str) -> str | None:
        """Deterministic short-circuits that decline without an LLM call: a reference to
        another tenant's schema, or a request for PII not present in extracted entities.
        Everything else is left to `classify_domain`."""
        cross_tenant = re.search(rf"(?!\b{re.escape(tenant_id)}\b)\btenant_\w+\b", message, re.IGNORECASE) if tenant_id else False
        if cross_tenant:
            logger.info("Cross-tenant query detected")
            return "cross_tenant"
        if PII_PATTERN.search(message):
            logger.info("PII query detected")
            return "pii"
        return None

    async def classify_domain(self, message: str, conversation_context: list[dict] | None, llm_client, llm_model: str) -> bool:
        """Returns True if the query is in-domain. Fails open (treats the query as
        in-domain) on any classifier error, since tenant isolation is enforced
        structurally elsewhere and an unsourced answer is already refused downstream —
        the guardrail here is a scope/cost filter, not a security boundary."""
        messages = [{"role": "system", "content": DOMAIN_CLASSIFIER_SYSTEM_PROMPT}]
        if conversation_context:
            for turn in conversation_context[-3:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": message})

        try:
            response = await llm_client.chat.completions.create(
                model=llm_model, messages=messages, temperature=0, max_tokens=5,
            )
            verdict = (response.choices[0].message.content or "").strip().lower()
            return "out_of_domain" not in verdict
        except Exception as e:
            logger.warning("Domain classifier failed, failing open (admitting query): %s", e)
            return True

    def enforce_sources(self, reply: str, sources: list[Source | Citation]) -> tuple[str, list[Source | Citation]]:
        """Only `generation_node` calls this. An entity-resolution clarification reply
        never reaches `generation_node` — `entity_resolution_node` routes straight to
        END on ambiguity — so a clarification's empty `sources` is never subject to
        this check by construction, not by a special case here. See design.md
        Decision 1 and the `chat-api` delta spec's guardrail exemption requirement."""
        if not sources:
            logger.warning("Guardrail: empty sources detected, returning fallback reply")
            return FALLBACK_REPLY, []
        return reply, sources

    def inject_disclaimer(self) -> str:
        return "This answer was generated by AI and may contain errors. Verify important information against source documents."
