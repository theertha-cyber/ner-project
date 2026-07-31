import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import wraps

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.database import get_engine
from src.shared.retrieval.orchestrator import (
    STOP_EMPTY_PLAN,
    STOP_PLANNER_ERROR,
    OrchestrationBudget,
    build_fallback_plan,
    execute_plan,
    plan_retrieval,
)
from src.shared.retrieval.tools.base import ToolContext
from src.chat_api.api.v1.schemas import Source
from src.chat_api.graph.state import ChatState
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

    @_traced("retrieval_execution", count_key="chunks")
    async def retrieval_execution_node(state: ChatState) -> dict:
        plan = state["retrieval_plan"]
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        jwt_token = state.get("jwt_token")
        already_degraded = state.get("orchestration_degraded", False)

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

        return {
            "chunks": result.chunks,
            "sql_results": result.sql_results,
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
        llm_messages = state["prompt_messages"]

        response = await orchestrator.llm_client.chat.completions.create(
            model=orchestrator.llm_model,
            messages=llm_messages,
            temperature=0.3,
            max_tokens=1000,
        )

        reply = response.choices[0].message.content
        sources = state.get("sources") or []
        reply, sources = orchestrator.guardrails.enforce_sources(reply, sources)
        return {"reply": reply, "sources": sources}

    return {
        "guardrail": guardrail_node,
        "orchestrator": orchestrator_node,
        "retrieval_execution": retrieval_execution_node,
        "source_assembly": source_assembly_node,
        "prompt_assembly": prompt_assembly_node,
        "generation": generation_node,
    }
