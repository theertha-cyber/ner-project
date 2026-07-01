import json
import logging
import asyncio
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.chat_api.api.v1.schemas import Source, Citation
from src.chat_api.services.sql_generator import SQLGenerator
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.services.ner_client import NERClient
from src.chat_api.services.guardrails import GuardrailService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful chatbot for a multi-tenant Named Entity Recognition (NER) platform.
You have access to the tenant's extracted entity data, document context, and live NER analysis.
Always answer based on the provided context data. Do not make up information.
When citing sources, reference the specific document or entity source.
If you cannot find relevant information, say so clearly.
Never reveal data from other tenants.
Format your response naturally and conversationally."""


class RAGOrchestrator:
    def __init__(self):
        self.sql_generator = SQLGenerator()
        self.embedding_service = EmbeddingService()
        self.ner_client = NERClient()
        self.guardrails = GuardrailService()
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
        blocked_reason = self.guardrails.check_blocked_question_type(message, tenant_id)
        if blocked_reason:
            decline_messages = {
                "classification": "I can only answer questions about extracted entities and document content. I cannot perform classification tasks.",
                "content_generation": "I can only answer questions about extracted entities and document content. I cannot generate content.",
                "summarization": "I can only answer questions about extracted entities and document content. I cannot summarize documents.",
                "cross_tenant": "I can only answer questions about your tenant's data. Cross-tenant queries are not supported.",
                "pii": "I cannot access or search for personally identifiable information.",
            }
            reply = decline_messages.get(blocked_reason, "I'm sorry, I cannot answer that type of question.")
            return reply, []

        complexity = self.guardrails.assess_complexity(message)
        if complexity > 3:
            return "That question requires multiple lookups. Please simplify and ask one thing at a time.", []

        sql_task = self._sql_source(message, session, schema, conversation_context)
        vector_task = self._vector_source(message, session, schema)

        sql_results, vector_results = await asyncio.gather(sql_task, vector_task, return_exceptions=True)

        sql_source = None
        if isinstance(sql_results, list) and sql_results:
            sql_source = Source(
                source_type="sql",
                value=json.dumps(sql_results[:5], default=str),
                relevance_score=1.0,
            )
        elif isinstance(sql_results, Exception):
            logger.warning("SQL source failed: %s", sql_results)

        vector_sources = []
        chunks_for_ner = []
        if isinstance(vector_results, list):
            for v in vector_results:
                vector_sources.append(Source(
                    source_type="document_chunk",
                    document_id=v["document_id"],
                    chunk_index=v["chunk_index"],
                    chunk_text=v["chunk_text"],
                    relevance_score=v["similarity_score"],
                ))
                chunks_for_ner.append(v["chunk_text"])

        ner_sources = []
        if chunks_for_ner:
            for chunk_text in chunks_for_ner[:3]:
                entities = await self.ner_client.infer(chunk_text, tenant_id, jwt_token)
                if entities:
                    for ent in entities:
                        ner_sources.append(Source(
                            source_type="ner",
                            entity_type=ent.get("entity_type"),
                            value=ent.get("value"),
                            confidence=ent.get("confidence"),
                            document_id=vector_sources[chunks_for_ner.index(chunk_text)] if chunks_for_ner.index(chunk_text) < len(vector_sources) else None,
                        ))

        sources = []
        if sql_source:
            sources.append(sql_source)
        sources.extend(vector_sources[:3])
        sources.extend(ner_sources[:5])

        sources = await self._enrich_citations(sources, session, schema)

        context_parts = []
        if sql_results:
            context_parts.append(f"Entity data: {json.dumps(sql_results[:10], default=str)}")
        if vector_results:
            for v in vector_results[:3]:
                context_parts.append(f"Document context (from {v['document_id']}): {v['chunk_text'][:500]}")
        if ner_sources:
            context_parts.append(f"NER entities: {json.dumps([{'type': s.entity_type, 'value': s.value, 'confidence': s.confidence} for s in ner_sources[:5]])}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant data found."

        conv_history = ""
        if conversation_context:
            for msg in conversation_context[-5:]:
                conv_history += f"{msg['role']}: {msg['content']}\n"

        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if conv_history:
            llm_messages.append({"role": "system", "content": f"Conversation history:\n{conv_history}"})
        llm_messages.append({"role": "user", "content": f"Context data:\n{context_str}\n\nQuestion: {message}"})

        response = await self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=llm_messages,
            temperature=0.3,
            max_tokens=1000,
        )

        reply = response.choices[0].message.content
        reply, sources = self.guardrails.enforce_sources(reply, sources)
        return reply, sources

    async def _sql_source(self, message: str, session: AsyncSession, schema: str,
                          conversation_context: list[dict] | None) -> list[dict] | None:
        conv_text = None
        if conversation_context:
            conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_context[-3:])
        return await self.sql_generator.generate_and_execute(message, session, schema, conv_text)

    async def _vector_source(self, message: str, session: AsyncSession, schema: str) -> list[dict]:
        try:
            return await self.embedding_service.similarity_search(message, session, schema)
        except Exception as e:
            logger.warning("Vector search failed: %s", str(e))
            return []

    async def _enrich_citations(self, sources: list[Source], session: AsyncSession, schema: str) -> list[Source | Citation]:
        if not sources:
            return []

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

        enriched: list[Source | Citation] = []
        for s in sources:
            doc_name = doc_map.get(s.document_id) if s.document_id else None
            context = s.chunk_text if s.source_type == "document_chunk" else None
            enriched.append(Citation(
                document_name=doc_name,
                document_id=s.document_id,
                entity_type=s.entity_type,
                entity_value=s.value,
                confidence=s.confidence,
                context_snippet=context,
                source_type=s.source_type,
            ))
        return enriched
