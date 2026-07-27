import json
import logging
import time
from functools import wraps

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.database import get_engine
from src.shared.retrieval import RerankingRetriever
from src.chat_api.api.v1.schemas import Source
from src.chat_api.graph.state import ChatState
from src.chat_api.services.context_assembler import ContextAssembler

logger = logging.getLogger(__name__)

DECLINE_MESSAGES = {
    "classification": "I can only answer questions about extracted entities and document content. I cannot perform classification tasks.",
    "content_generation": "I can only answer questions about extracted entities and document content. I cannot generate content.",
    "summarization": "I can only answer questions about extracted entities and document content. I cannot summarize documents.",
    "cross_tenant": "I can only answer questions about your tenant's data. Cross-tenant queries are not supported.",
    "pii": "I cannot access or search for personally identifiable information.",
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
    RAGOrchestrator instance so its attributes (retriever, sql_generator, ner_client,
    guardrails, llm_client) are read fresh at call time — required because tests
    construct RAGOrchestrator via __new__ and hand-assign these attributes directly."""

    @_traced("guardrail")
    async def guardrail_node(state: ChatState) -> dict:
        message = state["message"]
        tenant_id = state["tenant_id"]

        blocked_reason = orchestrator.guardrails.check_blocked_question_type(message, tenant_id)
        if blocked_reason:
            reply = DECLINE_MESSAGES.get(blocked_reason, "I'm sorry, I cannot answer that type of question.")
            return {"blocked_reason": blocked_reason, "reply": reply, "sources": []}

        complexity = orchestrator.guardrails.assess_complexity(message)
        if complexity > 3:
            return {
                "complexity": complexity,
                "reply": "That question requires multiple lookups. Please simplify and ask one thing at a time.",
                "sources": [],
            }

        return {"blocked_reason": None, "complexity": complexity}

    @_traced("sql_retrieval", count_key="sql_results")
    async def sql_retrieval_node(state: ChatState) -> dict:
        message = state["message"]
        schema = state["schema"]
        conversation_context = state.get("conversation_context")

        session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with session_factory() as session:
            try:
                results = await orchestrator._sql_source(message, session, schema, conversation_context)
                return {"sql_results": results, "sql_error": None}
            except Exception as e:
                logger.warning("SQL source failed: %s", e)
                return {"sql_results": None, "sql_error": str(e)}

    @_traced("retrieval", count_key="chunks")
    async def retrieval_node(state: ChatState) -> dict:
        message = state["message"]
        schema = state["schema"]
        jwt_token = state.get("jwt_token")

        session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with session_factory() as session:
            try:
                retriever = orchestrator.retriever
                if isinstance(retriever, RerankingRetriever):
                    chunks = await retriever.retrieve(
                        message, session, schema, top_k=settings.retrieval_top_k, jwt_token=jwt_token,
                    )
                else:
                    chunks = await retriever.retrieve(message, session, schema, top_k=settings.retrieval_top_k)
                return {"chunks": chunks, "retrieval_error": None}
            except Exception as e:
                logger.warning("Vector search failed: %s", str(e))
                return {"chunks": [], "retrieval_error": str(e)}

    @_traced("ner_enrichment", count_key="ner_entities")
    async def ner_enrichment_node(state: ChatState) -> dict:
        chunks = state.get("chunks") or []
        tenant_id = state["tenant_id"]
        jwt_token = state.get("jwt_token")

        ner_entities: list[dict] = []
        for idx, chunk in enumerate(chunks[:3]):
            entities = await orchestrator.ner_client.infer(chunk.chunk_text, tenant_id, jwt_token)
            if entities:
                for ent in entities:
                    ner_entities.append({
                        "entity_type": ent.get("entity_type"),
                        "value": ent.get("value"),
                        "confidence": ent.get("confidence"),
                        "chunk_index": idx,
                    })
        return {"ner_entities": ner_entities}

    @_traced("source_assembly", count_key="sources")
    async def source_assembly_node(state: ChatState) -> dict:
        sql_results = state.get("sql_results")
        chunks = state.get("chunks") or []
        ner_entities = state.get("ner_entities") or []
        tenant_id = state["tenant_id"]
        schema = state["schema"]
        session = state["session"]

        sql_source = None
        if sql_results:
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

        ner_sources = [
            Source(
                source_type="ner",
                entity_type=e["entity_type"],
                value=e["value"],
                confidence=e["confidence"],
                document_id=chunks[e["chunk_index"]].document_id if e["chunk_index"] < len(chunks) else None,
            )
            for e in ner_entities
        ]

        sources = []
        if sql_source:
            sources.append(sql_source)
        sources.extend(vector_sources[:3])
        sources.extend(ner_sources[:5])

        document_names = await orchestrator._resolve_document_names(sources, session, schema)
        sources = await orchestrator._enrich_citations(sources, session, schema, tenant_id, document_names=document_names)
        return {"sources": sources, "document_names": document_names}

    @_traced("prompt_assembly")
    async def prompt_assembly_node(state: ChatState) -> dict:
        message = state["message"]
        sql_results = state.get("sql_results")
        chunks = state.get("chunks") or []
        ner_entities = state.get("ner_entities") or []
        document_names = state.get("document_names") or {}
        conversation_context = state.get("conversation_context")

        llm_messages = ContextAssembler().assemble(
            message, sql_results, chunks, ner_entities, document_names, conversation_context,
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
        "sql_retrieval": sql_retrieval_node,
        "retrieval": retrieval_node,
        "ner_enrichment": ner_enrichment_node,
        "source_assembly": source_assembly_node,
        "prompt_assembly": prompt_assembly_node,
        "generation": generation_node,
    }
