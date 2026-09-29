import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import wraps

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.extraction_service.services.entity_normalizer import canonicalize
from src.shared.config import settings
from src.shared.conversation_history import recent_messages
from src.shared.database import get_engine, get_resolver
from src.shared.retrieval.orchestrator import (
    SEMANTIC_CAPABILITY_NAME,
    STOP_EMPTY_PLAN,
    STOP_PLANNER_ERROR,
    STRUCTURED_CAPABILITY_NAME,
    OrchestrationBudget,
    PlanEntry,
    RetrievalPlan,
    build_fallback_plan,
    execute_plan,
    plan_retrieval,
)
from src.shared.external_postgres.capability import resolve_external_capability
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.external_tools import ExternalDatabaseTool, render_external_tool_description
from src.shared.retrieval.tools.registry import ToolRegistry
from src.shared.retrieval.tools.tabular_tools import (
    TABULAR_TOOL_ADDENDUM,
    TabularFilesTool,
    render_tabular_tool_description,
)
from src.shared.tabular_files.capability import resolve_tabular_capability
from src.chat_api.api.v1.schemas import CandidateEntity, PendingClarification, Source
from src.chat_api.graph.state import ChatState
from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services import entity_resolver
from src.chat_api.services.chart_tool import ChartFrame, RENDER_CHART_SCHEMA, parse_chart_tool_call
from src.chat_api.services.context_assembler import ContextAssembler
from src.chat_api.services.guardrails import FALLBACK_REPLY, INCOMPLETE_RETRIEVAL_REPLY
from src.shared.observability import get_tenant_id
from src.shared.observability.domain_metrics import (
    measure_llm_call,
    record_answer,
    record_chat_stage,
)
from src.shared.observability.langsmith_link import langsmith_extra
from src.shared.observability.spans import stage_span

logger = logging.getLogger(__name__)

DOMAIN_DECLINE_REASON = "out_of_domain"

# Appended to the planner's system prompt only on a turn where `external_database`
# is offered (design.md Decision 5) — omitted, the planner's input is unchanged.
EXTERNAL_TOOL_ADDENDUM = (
    "A third capability, `external_database`, is offered this turn: it answers "
    "questions about the records in the tenant's own connected database by "
    "running a generated SQL query. Use it for questions about that connected "
    "database's data specifically — not for questions about uploaded documents, "
    "which the other two capabilities already cover."
)

DECLINE_MESSAGES = {
    "cross_tenant": "I can only answer questions about your tenant's data. Cross-tenant queries are not supported.",
    "pii": "I cannot access or search for personally identifiable information.",
    DOMAIN_DECLINE_REASON: (
        "I can only answer questions about your tenant's documents and the entities "
        "extracted from them. I can't help with that."
    ),
}


def _node_outcome(name: str, result: dict) -> str:
    """What this node decided, as a category — never what it decided *about*.

    Every value returned here is derived from a field the node already sets, so a node
    that grows a new branch reports `completed` rather than a wrong answer. The question,
    the reply, the resolved entity and the sources are all in `result` and none of them
    reaches a span.
    """
    if not isinstance(result, dict):
        return "completed"
    if name == "guardrail":
        return "blocked" if result.get("blocked_reason") else "admitted"
    if name == "orchestrator":
        if result.get("orchestration_degraded"):
            return "degraded"
        return "planned"
    if name == "entity_resolution":
        if result.get("pending_clarification") is not None:
            return "clarification"
        return result.get("entity_resolution_outcome") or "none"
    if name == "source_assembly":
        return "sourced" if result.get("sources") else "empty"
    if name == "generation":
        reply = result.get("reply")
        if reply in (FALLBACK_REPLY, INCOMPLETE_RETRIEVAL_REPLY):
            return "hedged"
        return "answered"
    return "completed"


def _traced(name: str, count_key: str | None = None):
    """Log, span and time one graph node.

    The span lives here rather than in a second wrapper because this decorator already
    brackets every node and already measures the elapsed time; a separate wrapper would
    time the same call twice and produce two numbers that drift.

    Deliberately thin, per design Decision 3. The node layer sees inputs and outputs; it
    cannot see the attempt loop, the fallback branch or the classifier exception, which is
    exactly what is missing today — those are measured inside the service functions. What
    the node layer *is* the right place for is the stage-per-request requirement: which
    stages this request executed, in what order, and how long each took.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapper(state: ChatState) -> dict:
            start = time.monotonic()
            with stage_span(f"chat.{name}") as span:
                try:
                    result = await fn(state)
                except Exception as exc:
                    span.set("outcome", "error")
                    span.record_error(exc)
                    record_chat_stage(name, time.monotonic() - start)
                    raise
                span.set("outcome", _node_outcome(name, result))
            elapsed_ms = (time.monotonic() - start) * 1000
            record_chat_stage(name, elapsed_ms / 1000)
            count = None
            if count_key is not None:
                value = result.get(count_key)
                count = len(value) if isinstance(value, list) else (1 if value is not None else 0)
            logger.info(
                "graph node=%s tenant_id=%s elapsed_ms=%.1f output_count=%s",
                name, state.get("tenant_id"), elapsed_ms, count,
            )
            return result
        return wrapper
    return decorator


_ANAPHORA_RE = re.compile(
    r"\b(she|he|her|him|his|they|them|their|that person|this candidate|that candidate)\b",
    re.IGNORECASE,
)


def _has_anaphoric_reference(message: str) -> bool:
    return bool(_ANAPHORA_RE.search(message))


def _per_entry_documents(plan, mention_documents: dict[str, list[str]] | None) -> dict[int, list[str] | None]:
    """For a plan that split the question per subject — more than one entry of the same
    capability — the documents each entry should be scoped to: those of the resolved
    mentions its own query names, or None (leave it unscoped) when it names none of them.

    Without this, "compare Hannah and Harshith" — where only Hannah resolved, because
    Harshith's name was never extracted — scoped Harshith's own entry to Hannah's
    document, so it could only ever come back empty. An entry that is its capability's
    only one is not in the result: it is the whole question, and the whole resolved set
    is its scope."""
    if not mention_documents:
        return {}
    counts: dict[str, int] = {}
    for entry in plan.entries:
        if not entry.rejected:
            counts[entry.capability_name] = counts.get(entry.capability_name, 0) + 1
    per_entry: dict[int, list[str] | None] = {}
    for index, entry in enumerate(plan.entries):
        if entry.rejected or counts.get(entry.capability_name, 0) < 2:
            continue
        query = str(entry.arguments.get("query", "")).lower()
        ids: list[str] = []
        for mention, docs in mention_documents.items():
            if mention and mention.lower() in query:
                ids.extend(d for d in docs if d not in ids)
        per_entry[index] = ids or None
    return per_entry


def _rewrite_plan_for_resolution(plan, document_ids: list[str], query_override: str | None,
                                 mention_documents: dict[str, list[str]] | None = None):
    """Returns a new RetrievalPlan with every `semantic_retrieval` entry's `scope`
    overridden to the resolved documents, and every `structured_retrieval` entry
    constrained to the same set. When `query_override` is given (resuming after a
    selection), both capabilities' `query` argument is replaced with it so retrieval
    answers the original request rather than the selection utterance.

    Takes the whole set, never a single identifier: this signature is half of why
    "compare Hannah and Girish" used to reach the prompt as a question about Girish."""
    document_ids = list(document_ids)
    if not document_ids:
        return plan

    per_entry = _per_entry_documents(plan, mention_documents)
    new_entries = []
    for index, entry in enumerate(plan.entries):
        args = dict(entry.arguments)
        if entry.capability_name in (SEMANTIC_CAPABILITY_NAME, STRUCTURED_CAPABILITY_NAME):
            if query_override is not None:
                args["query"] = query_override
            entry_ids = per_entry[index] if index in per_entry else document_ids
            if entry_ids:
                args["scope"] = {"type": "document", "document_ids": entry_ids}
        new_entries.append(PlanEntry(
            capability_name=entry.capability_name, arguments=args,
            rejected=entry.rejected, rejection_reason=entry.rejection_reason,
        ))
    return RetrievalPlan(entries=new_entries, truncated=plan.truncated)


def _candidates_to_schema(candidates: list[entity_resolver.Candidate]) -> list[CandidateEntity]:
    return [
        CandidateEntity(
            document_id=c.document_id, name=c.name, organization=c.organization,
            experience=c.experience, skills=c.skills, filename=c.filename,
        )
        for c in candidates
    ]


async def _conversation_attachment_filenames(session, schema: str, conversation_id: str | None) -> list[str]:
    """The filenames this conversation owns, for the domain guardrail.

    Read here rather than threaded down from the route because this node already holds
    the session, schema and conversation — and because a person attaches once and then
    asks about it over several turns, so the later turns carry no files of their own.
    Best-effort: a failed lookup must never turn into a declined question.
    """
    if not conversation_id or session is None:
        return []
    try:
        result = await session.execute(
            text(f"SELECT filename FROM {schema}.documents WHERE conversation_id = :cid ORDER BY created_at ASC"),
            {"cid": conversation_id},
        )
        return [r.filename for r in result.fetchall()]
    except Exception:
        logger.info("attachment_filenames_lookup_failed")
        return []


async def _tabular_sources_for_guardrail(tenant_id: str) -> list[str]:
    """One line per `ready` uploaded file — display name, table description and
    column names from the served contract — so the domain guardrail can tell that
    a quantitative question is about the tenant's own spreadsheet. Read on its own
    platform session (Design D10), like the orchestrator's capability resolution.
    Best-effort: a failed lookup must never turn into a declined question."""
    try:
        platform_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with platform_factory() as platform_session:
            capability = await resolve_tabular_capability(platform_session, tenant_id)
    except Exception as e:
        logger.info("guardrail_tabular_lookup_failed", extra={"error_class": type(e).__name__})
        return []
    if not capability.get("executable"):
        return []
    sources = []
    for served in capability["files"]:
        contract = served["contract"]
        line = served["display_name"]
        if contract.get("description"):
            line += f" — {contract['description']}"
        columns = [c["name"] for c in contract.get("columns", [])]
        if columns:
            line += f" (columns: {', '.join(columns)})"
        sources.append(line)
    return sources


def _pin_structured_query_to_question(plan, message: str, conversation_context) -> RetrievalPlan:
    """On a turn with no history, a plan's single structured entry asks the user's own
    question. The planner's only licence to rewrite is resolving references, and with no
    history there are none — yet it still paraphrased "What is the most common programming
    language" into "What programming languages do candidates know", dropping the aggregate
    so the answer model hand-counted a raw list and got it wrong. A split plan (several
    structured entries, one per subject) is left alone: each entry is a deliberate part."""
    if recent_messages(conversation_context):
        return plan
    structured = [
        e for e in plan.entries if e.capability_name == STRUCTURED_CAPABILITY_NAME and not e.rejected
    ]
    if len(structured) != 1 or structured[0].arguments.get("query") == message:
        return plan
    new_entries = []
    for entry in plan.entries:
        if entry is structured[0]:
            entry = PlanEntry(
                capability_name=entry.capability_name,
                arguments={**entry.arguments, "query": message},
                rejected=entry.rejected, rejection_reason=entry.rejection_reason,
            )
        new_entries.append(entry)
    return RetrievalPlan(entries=new_entries, truncated=plan.truncated)


def _structured_queries(plan) -> list[str]:
    """The `query` of every executed structured entry, for the entity block's header."""
    if plan is None:
        return []
    return [
        str(e.arguments.get("query", "")) for e in plan.entries
        if e.capability_name == STRUCTURED_CAPABILITY_NAME and not e.rejected and e.arguments.get("query")
    ]


async def _repair_plan_scopes(plan: RetrievalPlan, session_factory, schema: str) -> RetrievalPlan:
    """Maps every planner-supplied `scope.document_ids` entry onto real document ids.

    The planner is never shown document ids — the conversation it reads names files — so
    when it scopes a follow-up ("compare the first two") it writes filenames:
    `{"document_ids": ["Resume - Hannah.pdf"]}`. Passed through, that matched no document
    and semantic retrieval came back empty for both people. Each reference is accepted as
    an id or an exact filename; one that matches nothing is dropped, and an entry left
    with no valid reference loses its scope (searching the tenant beats searching nothing).
    Scopes written by entity resolution already hold ids and come through unchanged."""
    refs: set[str] = set()
    for entry in plan.entries:
        scope = entry.arguments.get("scope") if not entry.rejected else None
        if isinstance(scope, dict) and scope.get("type") == "document" and isinstance(scope.get("document_ids"), list):
            refs.update(str(ref) for ref in scope["document_ids"])
    if not refs:
        return plan

    try:
        async with session_factory() as session:
            result = await session.execute(
                text(f"SELECT id, filename FROM {schema}.documents WHERE id = ANY(:refs) OR filename = ANY(:refs)"),
                {"refs": sorted(refs)},
            )
            rows = result.fetchall()
    except Exception as e:
        logger.warning("plan_scope_repair_failed", extra={"error_class": type(e).__name__})
        return plan

    ids_by_ref: dict[str, set[str]] = {}
    for row in rows:
        ids_by_ref.setdefault(str(row.id), set()).add(str(row.id))
        ids_by_ref.setdefault(row.filename, set()).add(str(row.id))

    new_entries = []
    for entry in plan.entries:
        scope = entry.arguments.get("scope")
        if entry.rejected or not (isinstance(scope, dict) and scope.get("type") == "document"
                                  and isinstance(scope.get("document_ids"), list)):
            new_entries.append(entry)
            continue
        resolved = sorted({i for ref in scope["document_ids"] for i in ids_by_ref.get(str(ref), ())})
        args = dict(entry.arguments)
        if resolved:
            args["scope"] = {"type": "document", "document_ids": resolved}
        else:
            args.pop("scope", None)
        new_entries.append(PlanEntry(
            capability_name=entry.capability_name, arguments=args,
            rejected=entry.rejected, rejection_reason=entry.rejection_reason,
        ))
    return RetrievalPlan(entries=new_entries, truncated=plan.truncated)


async def _names_known_subject(state: ChatState) -> bool:
    """Whether the message names a person the tenant's own extracted data knows — the
    same deterministic, LLM-free lookup `entity_resolution_node` runs. Best-effort: any
    failure (or no session, as in unit tests) answers False, leaving the decline as it was."""
    session = state.get("session")
    if session is None:
        return False
    try:
        result = await entity_resolver.resolve_entity(
            state["message"], session, state["schema"], state["tenant_id"],
            requesting_user=state.get("requesting_user"),
            conversation_id=state.get("conversation_id"),
        )
    except Exception as e:
        logger.info("guardrail_subject_lookup_failed", extra={"error_class": type(e).__name__})
        return False
    return result.outcome in (entity_resolver.UNIQUE, entity_resolver.AMBIGUOUS, entity_resolver.OVER_CAP)


def build_nodes(orchestrator) -> dict:
    """Returns a dict of node-name -> async callable, each closing over the given
    RAGOrchestrator instance so its attributes (retriever, sql_generator, guardrails,
    llm_client, tool_registry) are read fresh at call time — required because tests
    construct RAGOrchestrator via __new__ and hand-assign these attributes directly."""

    @_traced("guardrail")
    async def guardrail_node(state: ChatState) -> dict:
        message = state["message"]
        tenant_id = state["tenant_id"]
        conversation_context = state.get("conversation_context")

        blocked_reason = orchestrator.guardrails.check_blocked_question_type(message, tenant_id)
        if blocked_reason:
            reply = DECLINE_MESSAGES.get(blocked_reason, "I'm sorry, I cannot answer that type of question.")
            return {"blocked_reason": blocked_reason, "reply": reply, "sources": []}

        attachment_filenames = await _conversation_attachment_filenames(
            state.get("session"), state["schema"], state.get("conversation_id"),
        )
        tabular_sources = await _tabular_sources_for_guardrail(tenant_id)
        is_in_domain = await orchestrator.guardrails.classify_domain(
            message, conversation_context, orchestrator.llm_client, orchestrator.llm_model,
            attachment_filenames, tabular_sources=tabular_sources,
        )
        if not is_in_domain and await _names_known_subject(state):
            # The classifier sees only the text, and "Tell me about Zanith" reads as a
            # general-knowledge request when you don't know Zanith is a candidate in this
            # tenant's documents. The tenant's own data does know, so a message naming one
            # of its subjects is admitted. Consulted only on the decline path, so an
            # admitted turn pays nothing for it.
            logger.info("guardrail: classifier declined a message naming a known subject; admitting")
            is_in_domain = True
        if not is_in_domain:
            return {
                "blocked_reason": DOMAIN_DECLINE_REASON,
                "reply": DECLINE_MESSAGES[DOMAIN_DECLINE_REASON],
                "sources": [],
            }

        return {"blocked_reason": None}

    @_traced("orchestrator")
    async def orchestrator_node(state: ChatState) -> dict:
        """Makes the single planning LLM call and stores the resulting plan in state.
        On a planner exception or an all-rejected plan, substitutes the degraded
        fallback plan (both capabilities on the raw query) so the plan itself is
        already visible in state before retrieval_execution_node runs.

        Also resolves this turn's tool registry (design.md Decision 5):
        `external_database` is added, with a contract-derived description, only
        when `resolve_external_capability` says this tenant is executable right
        now. `orchestrator.tool_registry` itself is never reassigned — a tenant
        without a connection gets byte-identical planner input, every turn."""
        message = state["message"]
        tenant_id = state["tenant_id"]
        session = state["session"]
        conversation_context = state.get("conversation_context")

        registry = orchestrator.tool_registry
        system_prompt_addendum = None
        try:
            # Capability resolution reads only control-plane tables
            # (`public.tenant_data_source_connections`, `public.external_pg_contracts`)
            # — Design D10, so it gets its own platform session, never `session`,
            # which for a `tenant_owned` tenant is their own store where no
            # `public.*` table exists. Its own session also means a failure here
            # cannot leave `session`'s transaction aborted and take every
            # downstream node's unrelated query down with it.
            platform_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
            async with platform_factory() as platform_session:
                capability = await resolve_external_capability(platform_session, tenant_id)
        except Exception as e:
            logger.warning(
                "external_capability_resolution_failed",
                extra={"error_class": type(e).__name__},
            )
            capability = {"executable": False}

        try:
            # Uploaded tabular files (ADR-018): the same D10 rule — control-plane
            # tables, read on their own platform session. A failure leaves the
            # tool unregistered and the turn continues with the other tools.
            platform_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
            async with platform_factory() as platform_session:
                tabular_capability = await resolve_tabular_capability(platform_session, tenant_id)
        except Exception as e:
            logger.warning(
                "tabular_capability_resolution_failed",
                extra={"error_class": type(e).__name__},
            )
            tabular_capability = {"executable": False}

        extra_tools = []
        addenda = []
        if capability.get("executable"):
            extra_tools.append(ExternalDatabaseTool(
                description=render_external_tool_description(capability["contract"]),
            ))
            addenda.append(EXTERNAL_TOOL_ADDENDUM)
        if tabular_capability.get("executable"):
            extra_tools.append(TabularFilesTool(
                description=render_tabular_tool_description(
                    tabular_capability["files"], settings.tabular_description_token_budget,
                ),
            ))
            addenda.append(TABULAR_TOOL_ADDENDUM)
        if extra_tools:
            turn_registry = ToolRegistry()
            for tool in orchestrator.tool_registry.list():
                turn_registry.register(tool)
            for tool in extra_tools:
                turn_registry.register(tool)
            registry = turn_registry
            system_prompt_addendum = "\n\n".join(addenda)

        try:
            plan = await plan_retrieval(
                message, conversation_context, orchestrator.llm_client, orchestrator.llm_model,
                registry, system_prompt_addendum,
            )
        except Exception as e:
            logger.warning(
                "orchestrator_planning_failed",
                extra={"outcome": "degraded_fallback_plan", "error_class": type(e).__name__},
            )
            return {
                "retrieval_plan": build_fallback_plan(message, registry),
                "tool_registry": registry,
                "orchestration_degraded": True,
                "orchestration_stop_reason": STOP_PLANNER_ERROR,
            }

        if not plan.entries or all(e.rejected for e in plan.entries):
            logger.info("orchestrator: planner produced no usable entries, using degraded fallback plan")
            return {
                "retrieval_plan": build_fallback_plan(message, registry),
                "tool_registry": registry,
                "orchestration_degraded": True,
                "orchestration_stop_reason": STOP_EMPTY_PLAN,
            }

        plan = _pin_structured_query_to_question(plan, message, conversation_context)
        return {
            "retrieval_plan": plan, "tool_registry": registry,
            "orchestration_degraded": False, "orchestration_stop_reason": None,
        }

    @_traced("entity_resolution")
    async def entity_resolution_node(state: ChatState) -> dict:
        """Resolves person-entity references before retrieval runs. Either rewrites
        `retrieval_plan` with a resolved document scope (unique match, inherited
        binding, or a just-completed selection) or returns a terminal clarification
        reply that short-circuits the graph to END. See design.md Decision 1 and
        Decision 8 for the resolution/binding rules implemented here."""
        message = state["message"]
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        session = state["session"]
        conversation_id = state.get("conversation_id")
        plan = state["retrieval_plan"]

        if not conversation_id:
            return {"entity_resolution_outcome": None, "resolved_document_ids": []}

        conv = await conv_state.read_state(session, schema, conversation_id)

        if conv.has_pending_clarification:
            idx = await entity_resolver.interpret_selection(
                message, conv.pending_candidates, orchestrator.llm_client, orchestrator.llm_model,
            )
            if idx is not None:
                selected = conv.pending_candidates[idx]
                original_message = conv.pending_original_message
                await conv_state.set_binding(session, schema, conversation_id, selected.document_id, selected.name)
                await conv_state.clear_pending(session, schema, conversation_id)
                rewritten = _rewrite_plan_for_resolution(plan, [selected.document_id], query_override=original_message)
                logger.info(
                    "entity_resolution outcome=selected tenant_id=%s document_id=%s",
                    tenant_id, selected.document_id,
                )
                return {
                    "retrieval_plan": rewritten,
                    "message": original_message,
                    "original_message": original_message,
                    "entity_resolution_outcome": "unique",
                    "resolved_document_ids": [selected.document_id],
                }

            if conv.pending_reask_count < conv_state.MAX_REASKS:
                await conv_state.increment_reask(session, schema, conversation_id, conv.pending_reask_count)
                reply = entity_resolver.render_clarification(conv.pending_mention, conv.pending_candidates)
                logger.info("entity_resolution outcome=reask tenant_id=%s", tenant_id)
                return {
                    "reply": reply, "sources": [],
                    "entity_resolution_outcome": "ambiguous",
                    "resolved_document_ids": [],
                    "pending_clarification": PendingClarification(
                        mention=conv.pending_mention, candidates=_candidates_to_schema(conv.pending_candidates),
                    ).model_dump(),
                }

            await conv_state.clear_pending(session, schema, conversation_id)
            logger.info("entity_resolution outcome=abandoned tenant_id=%s", tenant_id)
            return {"entity_resolution_outcome": "unresolved", "resolved_document_ids": []}

        # A resolved scope only ever rewrites document-scoped entries (see
        # `_rewrite_plan_for_resolution`). A plan with none — e.g. `tabular_files`
        # alone — gains nothing from resolution, and an n-gram of the question
        # ("in" in "total closed revenue in EMEA?") matching a stored value would
        # otherwise end the turn on a clarification about unrelated documents.
        if not any(
            not entry.rejected and entry.capability_name in (SEMANTIC_CAPABILITY_NAME, STRUCTURED_CAPABILITY_NAME)
            for entry in plan.entries
        ):
            return {"entity_resolution_outcome": None, "resolved_document_ids": []}

        result = await entity_resolver.resolve_entity(
            message, session, schema, tenant_id,
            requesting_user=state.get("requesting_user"),
            conversation_id=state.get("conversation_id"),
        )

        if result.outcome == entity_resolver.UNIQUE:
            document_ids = result.resolved_document_ids
            await conv_state.set_binding(session, schema, conversation_id, document_ids, result.resolved_entity_value)
            rewritten = _rewrite_plan_for_resolution(
                plan, document_ids, query_override=None, mention_documents=result.mention_documents,
            )
            return {
                "retrieval_plan": rewritten,
                "entity_resolution_outcome": "unique",
                "resolved_document_ids": document_ids,
                # A per-subject entry naming nobody resolution matched was left unscoped
                # on purpose; retrieval must not then filter its rows back out.
                "resolution_left_entries_unscoped": any(
                    ids is None for ids in _per_entry_documents(plan, result.mention_documents).values()
                ),
            }

        if result.outcome == entity_resolver.AMBIGUOUS:
            if conv.has_binding and any(c.document_id == conv.resolved_document_id for c in result.candidates) and (
                canonicalize(result.mention) == canonicalize(conv.resolved_entity_value or "")
            ):
                bound_ids = conv.resolved_document_ids
                rewritten = _rewrite_plan_for_resolution(plan, bound_ids, query_override=None)
                return {
                    "retrieval_plan": rewritten,
                    "entity_resolution_outcome": "unique",
                    "resolved_document_ids": bound_ids,
                }

            await conv_state.store_pending_clarification(session, schema, conversation_id, message, result.mention, result.candidates)
            reply = entity_resolver.render_clarification(result.mention, result.candidates)
            return {
                "reply": reply, "sources": [],
                "entity_resolution_outcome": "ambiguous",
                "resolved_document_ids": [],
                "pending_clarification": PendingClarification(
                    mention=result.mention, candidates=_candidates_to_schema(result.candidates),
                ).model_dump(),
            }

        if result.outcome == entity_resolver.OVER_CAP:
            reply = entity_resolver.render_narrowing_message(result.mention)
            return {
                "reply": reply, "sources": [],
                "entity_resolution_outcome": "over_cap",
                "resolved_document_ids": [],
            }

        # UNRESOLVED: no mention of its own in this message.
        if conv.has_binding:
            if _has_anaphoric_reference(message):
                bound_ids = conv.resolved_document_ids
                rewritten = _rewrite_plan_for_resolution(plan, bound_ids, query_override=None)
                return {
                    "retrieval_plan": rewritten,
                    "entity_resolution_outcome": "unique",
                    "resolved_document_ids": bound_ids,
                }
            await conv_state.clear_binding(session, schema, conversation_id)

        return {"entity_resolution_outcome": "unresolved", "resolved_document_ids": []}

    @_traced("retrieval_execution", count_key="chunks")
    async def retrieval_execution_node(state: ChatState) -> dict:
        plan = state["retrieval_plan"]
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        jwt_token = state.get("jwt_token")
        already_degraded = state.get("orchestration_degraded", False)
        resolved_document_ids = state.get("resolved_document_ids") or []
        conversation_context = state.get("conversation_context")
        registry = state.get("tool_registry") or orchestrator.tool_registry
        # Read from graph state, which carries it from the authenticated request — not
        # from the plan, the message, or any tool argument (ADR-014).
        conversation_id = state.get("conversation_id")

        # Routed through EngineResolver (ADR-017): retrieval and generated SQL both run
        # against wherever this tenant's data plane resolves.
        engine = await get_resolver().resolve(tenant_id)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        deadline = time.monotonic() + settings.retrieval_deadline_seconds

        @asynccontextmanager
        async def context_factory():
            async with session_factory() as session:
                yield ToolContext(
                    tenant_id=tenant_id, schema=schema, session=session,
                    retriever=orchestrator.retriever, jwt_token=jwt_token,
                    max_top_k=settings.retrieval_top_k, sql_search=orchestrator._sql_source,
                    external_search=orchestrator._external_source,
                    tabular_search=orchestrator._tabular_source,
                    deadline=deadline, conversation_context=conversation_context,
                    conversation_id=conversation_id,
                    # From authenticated request state via graph state, exactly as
                    # `conversation_id` above. Nothing a tool is handed can widen it.
                    requesting_user=state.get("requesting_user"),
                )

        plan = await _repair_plan_scopes(plan, session_factory, schema)
        budget = OrchestrationBudget(max_invocations=settings.orchestrator_max_invocations, deadline=deadline)
        result = await execute_plan(
            plan, registry, context_factory, budget,
            recovery_query=state.get("message"),
        )

        sql_results = result.sql_results
        # Skipped when resolution deliberately left a per-subject entry unscoped (it named
        # someone resolution could not match): its rows fall outside the resolved set by
        # design, and filtering them here would undo that.
        if resolved_document_ids and sql_results and not state.get("resolution_left_entries_unscoped"):
            # Secondary check only. Enforcement is the bound `document_id = ANY(:ids)`
            # predicate applied to the validated statement, so a limit-truncated result
            # can no longer be filtered down to nothing here. Every resolved document is
            # retained — the set is the answer for a multi-subject question, not a
            # single document with the rest treated as noise.
            resolved_set = set(resolved_document_ids)
            sql_results = [
                row for row in sql_results
                if not isinstance(row, dict) or row.get("document_id") is None or row.get("document_id") in resolved_set
            ]

        # The planner's own degradation happened in orchestrator_node, before this node
        # ran, so it is carried forward onto the status rather than recomputed here.
        status = result.status
        if already_degraded:
            status.planning_degraded = True
            status.stop_reason = state.get("orchestration_stop_reason") or status.stop_reason

        return {
            "chunks": result.chunks,
            "sql_results": sql_results,
            "sql_completeness": result.sql_completeness,
            "external_results": result.external_results,
            "external_relations": result.external_relations,
            "external_truncated": result.external_truncated,
            "external_failure_reason": result.external_failure_reason,
            "tabular_results": result.tabular_results,
            "tabular_files": result.tabular_files,
            "tabular_columns": result.tabular_columns,
            "tabular_truncated": result.tabular_truncated,
            "tabular_failure_reason": result.tabular_failure_reason,
            "retrieval_status": status,
            "plan_trace": [asdict(t) for t in result.plan_trace],
            "orchestration_degraded": status.planning_degraded,
            "orchestration_stop_reason": status.stop_reason,
        }

    @_traced("prompt_assembly")
    async def prompt_assembly_node(state: ChatState) -> dict:
        """Runs before `source_assembly` (design Decision 7) and returns what it
        admitted, so citations are derived from the evidence rather than guessed at a
        second time. Document-name resolution moved here because this stage already
        needs names for its chunk labels."""
        message = state["message"]
        sql_results = state.get("sql_results")
        chunks = state.get("chunks") or []
        conversation_context = state.get("conversation_context")
        schema = state["schema"]
        session = state["session"]

        name_sources = [
            Source(source_type="document_chunk", document_id=c.document_id) for c in chunks
        ]
        document_names = await orchestrator._resolve_document_names(
            name_sources, session, schema, state.get("requesting_user")
        )

        llm_messages, admitted = ContextAssembler().assemble(
            message, sql_results, chunks, document_names, conversation_context,
            retrieval_status=state.get("retrieval_status"),
            sql_completeness=state.get("sql_completeness"),
            external_results=state.get("external_results"),
            external_relations=state.get("external_relations"),
            external_truncated=state.get("external_truncated", False),
            external_failure_reason=state.get("external_failure_reason"),
            tabular_results=state.get("tabular_results"),
            tabular_files=state.get("tabular_files"),
            tabular_columns=state.get("tabular_columns"),
            tabular_truncated=state.get("tabular_truncated", False),
            tabular_failure_reason=state.get("tabular_failure_reason"),
            return_evidence=True,
            structured_queries=_structured_queries(state.get("retrieval_plan")),
        )
        return {
            "prompt_messages": llm_messages,
            "document_names": document_names,
            "admitted_evidence": admitted,
        }

    @_traced("source_assembly", count_key="sources")
    async def source_assembly_node(state: ChatState) -> dict:
        """Builds citations from `admitted_evidence` alone. It no longer slices chunks
        independently or re-serialises `sql_results` — a citation for evidence the
        prompt never contained is a claim about an answer that was never written from
        it."""
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        session = state["session"]
        admitted = state.get("admitted_evidence")
        document_names = state.get("document_names") or {}

        sources: list[Source] = []
        if admitted is not None and admitted.structured_admitted and admitted.rows:
            import json
            sources.append(Source(
                source_type="sql",
                value=json.dumps(admitted.rows, default=str),
                relevance_score=1.0,
            ))
        if admitted is not None and admitted.external_relations:
            import json
            # Relation names only — external row values are never serialized into
            # a persisted source (ADR-015, ADR-016).
            sources.append(Source(
                source_type="external_postgresql",
                value=json.dumps({"relations": admitted.external_relations}),
                relevance_score=1.0,
            ))

        if admitted is not None and admitted.tabular_files:
            # File, version, sheet, relation and column names only — never a row
            # value or a filter parameter value (ADR-015, tabular-file-chat spec).
            columns = list(admitted.tabular_columns)
            for ref in admitted.tabular_files:
                sources.append(Source(
                    source_type="tabular_file",
                    file_name=ref.get("display_name"),
                    file_version=ref.get("version"),
                    sheet=ref.get("sheet"),
                    relation=ref.get("relation"),
                    columns=columns,
                    relevance_score=1.0,
                ))

        admitted_chunks = admitted.chunks if admitted is not None else []
        sources.extend(
            Source(
                source_type="document_chunk",
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                chunk_text=c.chunk_text,
                relevance_score=c.similarity_score,
                page_number=c.page_number,
            )
            for c in admitted_chunks[: settings.citation_max_chunks]
        )

        sources = await orchestrator._enrich_citations(
            sources, session, schema, tenant_id, document_names=document_names,
        )
        return {"sources": sources}

    def _chart_eligible(state: ChatState) -> bool:
        """A turn may be offered the chart tool only when it has structured rows to
        draw from and is headed for an ordinary answer. Blocked and out-of-domain
        turns short-circuit before generation, so the remaining exclusion is a
        clarification request, which asserts nothing about tenant data."""
        return bool(state.get("sql_results")) and not state.get("pending_clarification")

    async def _propose_chart(state: ChatState, llm_messages: list) -> tuple[dict | None, list]:
        """Stage A. Asks the model whether these rows are worth drawing, offering it
        `render_chart`. Returns the validated chart and the messages stage B should
        send — extended with the tool exchange when a chart was produced, unchanged
        otherwise.

        Emits nothing to the token sink: the user sees no output until stage B, so the
        guardrail's "no token before the reply is trusted" rule is untouched. Any
        failure here degrades to a plain text answer rather than failing the turn.

        Stage B is still instructed to write a full text answer (figures included),
        not a caption, so the chart and the answer are both complete on their own."""
        try:
            async with measure_llm_call("chart_decision", get_tenant_id()) as call:
                response = await orchestrator.llm_client.chat.completions.create(
                    model=orchestrator.llm_model,
                    messages=llm_messages,
                    temperature=0.3,
                    max_tokens=1000,
                    tools=[RENDER_CHART_SCHEMA],
                    tool_choice="auto",
                    langsmith_extra=langsmith_extra(),
                )
                call.usage(response)
        except Exception:
            logger.warning("chart decision call failed; answering without a chart", exc_info=True)
            return None, llm_messages

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return None, llm_messages

        tool_call = tool_calls[0]
        chart = parse_chart_tool_call(tool_call, state.get("sql_results"))
        if chart is None:
            return None, llm_messages

        # The chart is rendered by the client above whatever stage B writes, but the
        # reply must still stand on its own as a full answer to the question — the
        # chart is a visual aid, not a replacement for stating the actual figures.
        extended = llm_messages + [
            message.model_dump(exclude_none=True),
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": (
                    "Chart rendered and shown to the user above your answer. Still write "
                    "a complete answer to the question in your reply, including the key "
                    "figures and any notable comparisons or standouts from the data — do "
                    "not just describe the chart or say it was created."
                ),
            },
        ]
        return chart.model_dump(), extended

    @_traced("generation")
    async def generation_node(state: ChatState) -> dict:
        """Streams content deltas to `state["token_sink"]` when present, per
        design.md Decision 2. Per Decision 3, streaming is entered only when sources
        are already non-empty — `enforce_sources` only ever discards a reply when
        sources are empty, so gating the streaming branch on that same condition
        guarantees a user is never shown text the guardrail then replaces.

        For chart-eligible turns this runs in two stages (design.md Decision 1): a
        non-streaming call that offers `render_chart`, then the ordinary generation
        call below. A turn that is not eligible, or whose model declines to chart,
        reaches that call exactly as it did before charts existed."""
        llm_messages = state["prompt_messages"]
        sources = state.get("sources") or []
        token_sink: asyncio.Queue | None = state.get("token_sink")

        chart = None
        if _chart_eligible(state):
            chart, llm_messages = await _propose_chart(state, llm_messages)

        if token_sink is not None and sources:
            # Ahead of the first delta, so the client can render the shape while the
            # commentary is still arriving. Safe to send this early precisely because
            # this branch requires non-empty sources, and `enforce_sources` only ever
            # replaces a reply when sources are empty — nothing below can retract it.
            if chart is not None:
                await token_sink.put(ChartFrame(chart))

            # The measured span covers the whole stream, not just the call that opens it:
            # a streamed answer's latency is the time until the last delta, which is what
            # the user actually waits for. No usage block arrives on a stream unless it is
            # explicitly requested, so this records latency and outcome and no tokens
            # rather than guessing at a count.
            async with measure_llm_call("answer_generation", get_tenant_id()):
                stream = await orchestrator.llm_client.chat.completions.create(
                    model=orchestrator.llm_model,
                    messages=llm_messages,
                    temperature=0.3,
                    max_tokens=1000,
                    stream=True,
                    langsmith_extra=langsmith_extra(),
                )
                deltas = []
                async for chunk in stream:
                # Some chunks carry no choices at all — e.g. Azure OpenAI's
                # trailing content-filter/usage chunk — rather than a choice with
                # an empty delta. Guard the index, not just the delta content.
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        deltas.append(delta)
                        await token_sink.put(delta)
            reply = "".join(deltas)
        else:
            async with measure_llm_call("answer_generation", get_tenant_id()) as call:
                response = await orchestrator.llm_client.chat.completions.create(
                    model=orchestrator.llm_model,
                    messages=llm_messages,
                    temperature=0.3,
                    max_tokens=1000,
                    langsmith_extra=langsmith_extra(),
                )
                call.usage(response)
            reply = response.choices[0].message.content

        reply, sources = orchestrator.guardrails.enforce_sources(
            reply, sources, state.get("retrieval_status"),
        )
        if reply in (FALLBACK_REPLY, INCOMPLETE_RETRIEVAL_REPLY):
            # The chart is drawn from the evidence the guardrail just judged too thin
            # to support a sentence, so it cannot stand next to the fallback either.
            chart = None
        # Composition, measured after the guardrail has had its say: the citation count
        # that matters is the one on the answer the user receives, not the one the model
        # proposed. A hedged reply is one the guardrail replaced with a fallback, which is
        # a different product outcome from an answer that happened to be short.
        record_answer(
            confidence=state.get("confidence"),
            citations=len(sources),
            hedged=reply in (FALLBACK_REPLY, INCOMPLETE_RETRIEVAL_REPLY),
        )
        return {"reply": reply, "sources": sources, "chart": chart}

    return {
        "guardrail": guardrail_node,
        "orchestrator": orchestrator_node,
        "entity_resolution": entity_resolution_node,
        "retrieval_execution": retrieval_execution_node,
        "source_assembly": source_assembly_node,
        "prompt_assembly": prompt_assembly_node,
        "generation": generation_node,
    }
