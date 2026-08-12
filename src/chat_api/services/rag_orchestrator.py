import asyncio
import json
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.shared.conversation_history import render_history
from src.shared.retrieval import DenseRetriever, SparseRetriever, HybridRetriever, RerankingRetriever, CrossEncoderReranker
from src.shared.retrieval.tools import build_default_registry
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.sql_generator import SQLGenerator
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.state import ChatState

logger = logging.getLogger(__name__)

# Sentinel pushed onto a streaming turn's token sink once the graph run has fully
# resolved (successfully or with an exception) — see design.md Decision 2 and
# Decision 9. The endpoint's drain loop breaks on this and then awaits the graph
# task itself to observe its result or exception, rather than relying on the sink
# alone to signal completion.
STREAM_DONE = object()


class RAGOrchestrator:
    def __init__(self):
        self.sql_generator = SQLGenerator()
        self.embedding_service = EmbeddingService()
        base_retriever = HybridRetriever(DenseRetriever(self.embedding_service), SparseRetriever())
        self.retriever = RerankingRetriever(base_retriever, CrossEncoderReranker())
        self.guardrails = GuardrailService()
        self.tool_registry = build_default_registry()
        if settings.azure_openai_endpoint:
            self.llm_client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.llm_model = settings.azure_openai_chat_deployment
        else:
            self.llm_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.llm_model = "gpt-4o"

    async def execute(self, message: str, session: AsyncSession, schema: str, tenant_id: str,
                      jwt_token: str | None = None, conversation_context: list[dict] | None = None) -> tuple[str, list[Source | Citation]]:
        result = await self._run_graph(message, session, schema, tenant_id, jwt_token, conversation_context)
        return result["reply"], result.get("sources", [])

    async def execute_with_clarification(
        self, message: str, session: AsyncSession, schema: str, tenant_id: str,
        jwt_token: str | None = None, conversation_context: list[dict] | None = None,
        conversation_id: str | None = None,
    ) -> tuple[str, list[Source | Citation], dict | None, str, str | None]:
        """Same as `execute`, but additionally surfaces `pending_clarification`,
        `answer_kind`, and `model_version`, and requires `conversation_id` so entity
        resolution can read and persist its per-conversation state. Used by
        `src/chat_api/api/v1/chat.py`; the widget endpoint keeps calling `execute`,
        whose signature is unchanged."""
        result = await self._run_graph(message, session, schema, tenant_id, jwt_token, conversation_context, conversation_id)
        sources = result.get("sources", [])
        return (
            result["reply"],
            sources,
            result.get("pending_clarification"),
            self._classify_answer_kind(result),
            self._extract_model_version(sources),
        )

    async def execute_with_clarification_stream(
        self, message: str, session: AsyncSession, schema: str, tenant_id: str,
        token_sink: asyncio.Queue, jwt_token: str | None = None,
        conversation_context: list[dict] | None = None, conversation_id: str | None = None,
    ) -> tuple[str, list[Source | Citation], dict | None, str, str | None]:
        """Same as `execute_with_clarification`, but threads `token_sink` into the
        graph's initial state (design.md Decision 2) so `generation_node` can stream
        content deltas onto it as they arrive. Returns the identical 5-tuple once the
        graph reaches its terminal state, so callers reuse the same response-assembly
        code regardless of whether the turn streamed any tokens. `STREAM_DONE` is
        pushed onto `token_sink` in a `finally` so the caller's drain loop always
        terminates, even when the graph run raises."""
        try:
            result = await self._run_graph(
                message, session, schema, tenant_id, jwt_token, conversation_context, conversation_id,
                token_sink=token_sink,
            )
        finally:
            await token_sink.put(STREAM_DONE)

        sources = result.get("sources", [])
        return (
            result["reply"],
            sources,
            result.get("pending_clarification"),
            self._classify_answer_kind(result),
            self._extract_model_version(sources),
        )

    @staticmethod
    def _classify_answer_kind(result: dict) -> str:
        """Derives the persisted `answer_kind` from the terminal graph state, per
        design.md Decision 5: reuses the classification the graph already computed
        (blocked_reason, pending_clarification, entity_resolution_outcome) rather
        than re-deriving it from message content."""
        if result.get("pending_clarification"):
            return "clarification"
        if result.get("entity_resolution_outcome") == "over_cap":
            return "clarification"
        blocked_reason = result.get("blocked_reason")
        if blocked_reason == "out_of_domain":
            return "out_of_domain"
        if blocked_reason:
            return "guardrail_blocked"
        return "answer"

    @staticmethod
    def _extract_model_version(sources: list[Source | Citation]) -> str | None:
        """Per design.md Decision 6: reuses the `model_version` identifier already
        returned by model-serving inference (InferResponse.model_version) when a
        turn's sources include an NER-inference-derived source. `None` when no such
        source is present (the turn was answered without an NER inference call)."""
        for s in sources:
            model_version = getattr(s, "model_version", None)
            if model_version:
                return model_version
        return None

    async def _run_graph(self, message: str, session: AsyncSession, schema: str, tenant_id: str,
                         jwt_token: str | None = None, conversation_context: list[dict] | None = None,
                         conversation_id: str | None = None, token_sink: asyncio.Queue | None = None) -> dict:
        if getattr(self, "_graph", None) is None:
            self._graph = build_chat_graph(self)

        state: ChatState = {
            "message": message,
            "tenant_id": tenant_id,
            "schema": schema,
            "jwt_token": jwt_token,
            "conversation_context": conversation_context,
            "conversation_id": conversation_id,
            "session": session,
            "token_sink": token_sink,
        }
        return await self._graph.ainvoke(state)

    async def _sql_source(self, message: str, session: AsyncSession, schema: str,
                          conversation_context: list[dict] | None,
                          attempt_sink: list | None = None,
                          deadline: float | None = None) -> list[dict] | None:
        """`schema` comes from the caller's authenticated request context and is passed
        straight through — the recovery loop never re-derives it. Raises
        `SQLGenerationFailed` when every attempt failed; the tool layer turns that into
        a `ToolResult` error rather than an empty result."""
        conv_text = render_history(conversation_context)
        return await self.sql_generator.generate_and_execute(
            message, session, schema, conv_text,
            attempt_sink=attempt_sink, deadline=deadline,
        )

    async def _resolve_document_names(self, sources: list[Source], session: AsyncSession, schema: str) -> dict[str, str]:
        doc_ids = {s.document_id for s in sources if s.document_id}
        doc_map: dict[str, str] = {}
        if doc_ids:
            try:
                result = await session.execute(
                    text(f"SELECT id, filename FROM {schema}.documents WHERE id = ANY(:ids)"),
                    {"ids": list(doc_ids)},
                )
                for row in result.fetchall():
                    doc_map[row[0]] = row[1]
            except Exception as e:
                logger.warning("Citation enrichment: document name resolution failed: %s", e)
        return doc_map

    async def _enrich_citations(self, sources: list[Source], session: AsyncSession, schema: str, tenant_id: str,
                                document_names: dict[str, str] | None = None) -> list[Source | Citation]:
        if not sources:
            return []

        doc_map = document_names if document_names is not None else await self._resolve_document_names(sources, session, schema)

        conll_types = {s.entity_type for s in sources if s.entity_type and s.source_type == "ner"}
        conll_to_name: dict[str, str] = {}
        if conll_types:
            try:
                result = await session.execute(
                    text("SELECT name, base_label_mapping FROM public.entity_definitions WHERE tenant_id = :tid"),
                    {"tid": tenant_id},
                )
                for row in result.fetchall():
                    mapping = row[1]
                    if isinstance(mapping, str):
                        import json
                        mapping = json.loads(mapping)
                    if isinstance(mapping, dict):
                        for conll_label in conll_types:
                            if conll_label in mapping:
                                conll_to_name[conll_label] = row[0]
            except Exception as e:
                logger.warning("Citation enrichment: entity type name resolution failed: %s", e)

        enriched: list[Source | Citation] = []
        for s in sources:
            doc_name = doc_map.get(s.document_id) if s.document_id else None
            entity_type_name = conll_to_name.get(s.entity_type) if s.entity_type and s.source_type == "ner" else None
            context = s.chunk_text if s.source_type == "document_chunk" else None
            enriched.append(Citation(
                document_name=doc_name,
                document_id=s.document_id,
                entity_type=entity_type_name or s.entity_type,
                entity_value=s.value,
                confidence=s.confidence,
                relevance_score=s.relevance_score,
                context_snippet=context,
                page_number=s.page_number,
                source_type=s.source_type,
                model_version=s.model_version,
            ))
        return enriched
