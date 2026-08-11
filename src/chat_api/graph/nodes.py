import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import wraps

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.extraction_service.services.entity_normalizer import canonicalize
from src.shared.config import settings
from src.shared.database import get_engine
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
from src.shared.retrieval.tools.base import ToolContext
from src.chat_api.api.v1.schemas import CandidateEntity, PendingClarification, Source
from src.chat_api.graph.state import ChatState
from src.chat_api.services import conversation_entity_state as conv_state
from src.chat_api.services import entity_resolver
from src.chat_api.services.context_assembler import ContextAssembler

logger = logging.getLogger(__name__)

DOMAIN_DECLINE_REASON = "out_of_domain"

DECLINE_MESSAGES = {
    "cross_tenant": "I can only answer questions about your tenant's data. Cross-tenant queries are not supported.",
    "pii": "I cannot access or search for personally identifiable information.",
    DOMAIN_DECLINE_REASON: (
        "I can only answer questions about your tenant's documents and the entities "
        "extracted from them. I can't help with that."
    ),
}


def _traced(name: str, count_key: str | None = None):
    def decorator(fn):
        @wraps(fn)
        async def wrapper(state: ChatState) -> dict:
            start = time.monotonic()
            result = await fn(state)
            elapsed_ms = (time.monotonic() - start) * 1000
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


def _rewrite_plan_for_resolution(plan, document_id: str, query_override: str | None):
    """Returns a new RetrievalPlan with every `semantic_retrieval` entry's `scope`
    overridden to the resolved document, and every `structured_retrieval` entry's
    `query` argument extended with an explicit document constraint. When
    `query_override` is given (resuming after a selection), both capabilities'
    `query` argument is replaced with it so retrieval answers the original request
    rather than the selection utterance."""
    new_entries = []
    for entry in plan.entries:
        args = dict(entry.arguments)
        if entry.capability_name == SEMANTIC_CAPABILITY_NAME:
            if query_override is not None:
                args["query"] = query_override
            args["scope"] = {"type": "document", "document_ids": [document_id]}
        elif entry.capability_name == STRUCTURED_CAPABILITY_NAME:
            base_query = query_override if query_override is not None else args.get("query", "")
            args["query"] = f"{base_query} (restrict results to document_id = '{document_id}')"
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

        is_in_domain = await orchestrator.guardrails.classify_domain(
            message, conversation_context, orchestrator.llm_client, orchestrator.llm_model,
        )
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
        already visible in state before retrieval_execution_node runs."""
        message = state["message"]
        conversation_context = state.get("conversation_context")
        registry = orchestrator.tool_registry

        try:
            plan = await plan_retrieval(message, conversation_context, orchestrator.llm_client, orchestrator.llm_model, registry)
        except Exception as e:
            logger.warning("orchestrator: planning call failed, using degraded fallback plan: %s", e)
            return {
                "retrieval_plan": build_fallback_plan(message, registry),
                "orchestration_degraded": True,
                "orchestration_stop_reason": STOP_PLANNER_ERROR,
            }

        if not plan.entries or all(e.rejected for e in plan.entries):
            logger.info("orchestrator: planner produced no usable entries, using degraded fallback plan")
            return {
                "retrieval_plan": build_fallback_plan(message, registry),
                "orchestration_degraded": True,
                "orchestration_stop_reason": STOP_EMPTY_PLAN,
            }

        return {"retrieval_plan": plan, "orchestration_degraded": False, "orchestration_stop_reason": None}

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
                rewritten = _rewrite_plan_for_resolution(plan, selected.document_id, query_override=original_message)
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

        result = await entity_resolver.resolve_entity(message, session, schema, tenant_id)

        if result.outcome == entity_resolver.UNIQUE:
            await conv_state.set_binding(session, schema, conversation_id, result.resolved_document_id, result.resolved_entity_value)
            rewritten = _rewrite_plan_for_resolution(plan, result.resolved_document_id, query_override=None)
            return {
                "retrieval_plan": rewritten,
                "entity_resolution_outcome": "unique",
                "resolved_document_ids": [result.resolved_document_id],
            }

        if result.outcome == entity_resolver.AMBIGUOUS:
            if conv.has_binding and any(c.document_id == conv.resolved_document_id for c in result.candidates) and (
                canonicalize(result.mention) == canonicalize(conv.resolved_entity_value or "")
            ):
                rewritten = _rewrite_plan_for_resolution(plan, conv.resolved_document_id, query_override=None)
                return {
                    "retrieval_plan": rewritten,
                    "entity_resolution_outcome": "unique",
                    "resolved_document_ids": [conv.resolved_document_id],
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
                rewritten = _rewrite_plan_for_resolution(plan, conv.resolved_document_id, query_override=None)
                return {
                    "retrieval_plan": rewritten,
                    "entity_resolution_outcome": "unique",
                    "resolved_document_ids": [conv.resolved_document_id],
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

        session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        deadline = time.monotonic() + settings.retrieval_deadline_seconds

        @asynccontextmanager
        async def context_factory():
            async with session_factory() as session:
                yield ToolContext(
                    tenant_id=tenant_id, schema=schema, session=session,
                    retriever=orchestrator.retriever, jwt_token=jwt_token,
                    max_top_k=settings.retrieval_top_k, sql_search=orchestrator._sql_source,
                    deadline=deadline,
                )

        budget = OrchestrationBudget(max_invocations=settings.orchestrator_max_invocations, deadline=deadline)
        result = await execute_plan(plan, orchestrator.tool_registry, context_factory, budget)

        sql_results = result.sql_results
        if resolved_document_ids and sql_results:
            resolved_set = set(resolved_document_ids)
            sql_results = [
                row for row in sql_results
                if not isinstance(row, dict) or row.get("document_id") is None or row.get("document_id") in resolved_set
            ]

        return {
            "chunks": result.chunks,
            "sql_results": sql_results,
            "retrieval_error": result.retrieval_error,
            "sql_error": result.sql_error,
            "plan_trace": [asdict(t) for t in result.plan_trace],
            "orchestration_degraded": already_degraded or result.orchestration_degraded,
            "orchestration_stop_reason": (
                state.get("orchestration_stop_reason") if already_degraded else result.orchestration_stop_reason
            ),
        }

    @_traced("source_assembly", count_key="sources")
    async def source_assembly_node(state: ChatState) -> dict:
        sql_results = state.get("sql_results")
        chunks = state.get("chunks") or []
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        session = state["session"]

        sql_source = None
        if sql_results:
            import json
            sql_source = Source(
                source_type="sql",
                value=json.dumps(sql_results[:5], default=str),
                relevance_score=1.0,
            )

        vector_sources = [
            Source(
                source_type="document_chunk",
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                chunk_text=c.chunk_text,
                relevance_score=c.similarity_score,
                page_number=c.page_number,
            )
            for c in chunks
        ]

        sources = []
        if sql_source:
            sources.append(sql_source)
        sources.extend(vector_sources[:3])

        document_names = await orchestrator._resolve_document_names(sources, session, schema)
        sources = await orchestrator._enrich_citations(sources, session, schema, tenant_id, document_names=document_names)
        return {"sources": sources, "document_names": document_names}

    @_traced("prompt_assembly")
    async def prompt_assembly_node(state: ChatState) -> dict:
        message = state["message"]
        sql_results = state.get("sql_results")
        chunks = state.get("chunks") or []
        document_names = state.get("document_names") or {}
        conversation_context = state.get("conversation_context")

        llm_messages = ContextAssembler().assemble(
            message, sql_results, chunks, document_names, conversation_context,
        )
        return {"prompt_messages": llm_messages}

    @_traced("generation")
    async def generation_node(state: ChatState) -> dict:
        """Streams content deltas to `state["token_sink"]` when present, per
        design.md Decision 2. Per Decision 3, streaming is entered only when sources
        are already non-empty — `enforce_sources` only ever discards a reply when
        sources are empty, so gating the streaming branch on that same condition
        guarantees a user is never shown text the guardrail then replaces."""
        llm_messages = state["prompt_messages"]
        sources = state.get("sources") or []
        token_sink: asyncio.Queue | None = state.get("token_sink")

        if token_sink is not None and sources:
            stream = await orchestrator.llm_client.chat.completions.create(
                model=orchestrator.llm_model,
                messages=llm_messages,
                temperature=0.3,
                max_tokens=1000,
                stream=True,
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
            response = await orchestrator.llm_client.chat.completions.create(
                model=orchestrator.llm_model,
                messages=llm_messages,
                temperature=0.3,
                max_tokens=1000,
            )
            reply = response.choices[0].message.content

        reply, sources = orchestrator.guardrails.enforce_sources(reply, sources)
        return {"reply": reply, "sources": sources}

    return {
        "guardrail": guardrail_node,
        "orchestrator": orchestrator_node,
        "entity_resolution": entity_resolution_node,
        "retrieval_execution": retrieval_execution_node,
        "source_assembly": source_assembly_node,
        "prompt_assembly": prompt_assembly_node,
        "generation": generation_node,
    }
