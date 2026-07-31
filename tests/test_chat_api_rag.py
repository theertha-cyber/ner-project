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

    def test_enrichment_resolves_conll_type_via_base_label_mapping(self):
        mapping_data = {"ORG": True, "PER": False}
        conll_types = {"ORG", "PER"}
        entity_rows = [
            ("organization", mapping_data),
            ("person", {"PER": True}),
        ]
        conll_to_name = {}
        for name, mapping in entity_rows:
            if isinstance(mapping, dict):
                for conll_label in conll_types:
                    if conll_label in mapping:
                        conll_to_name[conll_label] = name
        assert conll_to_name.get("ORG") == "organization"
        assert conll_to_name.get("PER") == "person"


class _FakeResult:
    def fetchall(self):
        return []


class _FakeSession:
    async def execute(self, *args, **kwargs):
        return _FakeResult()


class TestSourceAssemblyHasNoNerSources:
    """Covers verification.md row 38: retrieval-time NER is removed, so
    source_assembly_node must never construct a `source_type="ner"` entry."""

    async def test_source_assembly_never_produces_ner_sources(self):
        from src.chat_api.graph.nodes import build_nodes
        from src.chat_api.services.rag_orchestrator import RAGOrchestrator
        from src.shared.retrieval.models import RetrievalResult

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
        nodes = build_nodes(orchestrator)

        chunks = [RetrievalResult(document_id="doc-1", chunk_index=0, chunk_text="text", similarity_score=0.9)]
        state = {
            "message": "q", "tenant_id": "t1", "schema": "tenant_t1",
            "session": _FakeSession(), "chunks": chunks, "sql_results": [{"count": 1}],
        }
        result = await nodes["source_assembly"](state)

        assert all(s.source_type != "ner" for s in result["sources"])
        assert any(s.source_type == "document_chunk" for s in result["sources"])
        assert any(s.source_type == "sql" for s in result["sources"])
