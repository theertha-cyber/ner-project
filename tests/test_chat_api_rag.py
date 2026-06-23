import pytest
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.api.v1.schemas import Source

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


@pytest.mark.skip(reason="Requires OpenAI API key and live DB")
class TestEmbeddingService:
    def setup_method(self):
        self.embedder = EmbeddingService()

    async def test_embed_query_returns_vector(self):
        vector = await self.embedder.embed("How many organizations?")
        assert isinstance(vector, list)
        assert len(vector) == 1536  # text-embedding-3-small dimension

    async def test_embed_batch_returns_vectors(self):
        vectors = await self.embedder.embed_batch(["Hello", "World"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 1536


@pytest.mark.skip(reason="Requires live model-serving")
class TestNERClient:
    pass


class TestGuardrailEnforcement:
    def test_source_citation_structure(self):
        source = Source(
            source_type="sql",
            value="[{'entity_type': 'ORG', 'count': 5}]",
            relevance_score=1.0,
        )
        assert source.source_type == "sql"
        assert source.relevance_score == 1.0

    def test_chat_response_sources(self):
        from src.chat_api.api.v1.schemas import ChatResponse
        response = ChatResponse(
            reply="Test reply",
            sources=[Source(source_type="sql", value="test", relevance_score=0.9)],
            conversation_id="conv-123",
        )
        assert len(response.sources) == 1
        assert response.disclaimer is not None
        assert "AI-generated" in response.disclaimer
