import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 5


class EmbeddingService:
    def __init__(self):
        if settings.azure_openai_endpoint:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_embedding_deployment
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = EMBEDDING_MODEL

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [r.embedding for r in response.data]

    async def similarity_search(self, query: str, session: AsyncSession, schema: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        query_embedding = await self.embed(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await session.execute(
            text(f"""
                SELECT id, document_id, chunk_index, chunk_text,
                       1 - (embedding <=> :query_emb) AS similarity_score
                FROM {schema}.document_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_emb
                LIMIT :top_k
            """),
            {"query_emb": embedding_str, "top_k": top_k},
        )
        rows = result.fetchall()
        return [
            {
                "document_id": r.document_id,
                "chunk_index": r.chunk_index,
                "chunk_text": r.chunk_text,
                "similarity_score": float(r.similarity_score),
            }
            for r in rows
        ]
