import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from src.shared.config import settings

logger = logging.getLogger(__name__)


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
            self.model = settings.embedding_model

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
