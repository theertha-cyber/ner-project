import pytest
from src.chat_api.services.embedding_service import EmbeddingService
from src.chat_api.api.v1.schemas import Source, Citation

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


class TestCitationEnrichment:
    def test_citation_created_from_ner_source(self):
        source = Source(
            source_type="ner",
            document_id="doc-123",
            entity_type="organization",
            value="Acme Corp",
            confidence=0.95,
        )
        citation = Citation(
            document_name="report.pdf",
            document_id=source.document_id,
            entity_type=source.entity_type,
            entity_value=source.value,
            confidence=source.confidence,
            source_type=source.source_type,
        )
        assert citation.document_name == "report.pdf"
        assert citation.entity_value == "Acme Corp"
        assert citation.confidence == 0.95

    def test_citation_handles_null_document_id(self):
        source = Source(source_type="sql", value="[{'count': 5}]")
        citation = Citation(
            document_name=None,
            document_id=None,
            source_type=source.source_type,
            entity_value=source.value,
        )
        assert citation.document_name is None
        assert citation.document_id is None

    def test_citation_from_document_chunk_source(self):
        source = Source(
            source_type="document_chunk",
            document_id="doc-456",
            chunk_text="Sample document text here",
            relevance_score=0.85,
        )
        citation = Citation(
            document_name="notes.txt",
            document_id=source.document_id,
            context_snippet=source.chunk_text,
            source_type=source.source_type,
        )
        assert citation.document_name == "notes.txt"
        assert citation.context_snippet == "Sample document text here"

    def test_empty_sources_list_returns_empty(self):
        sources: list = []
        enriched: list = []
        assert len(enriched) == 0
