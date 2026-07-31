import json
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.shared.retrieval import DenseRetriever, SparseRetriever, HybridRetriever, RerankingRetriever, CrossEncoderReranker
from src.shared.retrieval.tools import build_default_registry
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.sql_generator import SQLGenerator
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.services.guardrails import GuardrailService
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.state import ChatState

logger = logging.getLogger(__name__)


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
        if getattr(self, "_graph", None) is None:
            self._graph = build_chat_graph(self)

        state: ChatState = {
            "message": message,
            "tenant_id": tenant_id,
            "schema": schema,
            "jwt_token": jwt_token,
            "conversation_context": conversation_context,
            "session": session,
        }
        result = await self._graph.ainvoke(state)
        return result["reply"], result.get("sources", [])

    async def _sql_source(self, message: str, session: AsyncSession, schema: str,
                          conversation_context: list[dict] | None) -> list[dict] | None:
        conv_text = None
        if conversation_context:
            conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_context[-3:])
        return await self.sql_generator.generate_and_execute(message, session, schema, conv_text)

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
            ))
        return enriched
