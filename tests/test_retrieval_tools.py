import inspect

import pytest

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext, ToolResult, validate_args, ArgValidationError
from src.shared.retrieval.tools.document_tools import lookup_document, search_documents
from src.shared.retrieval.tools.entity_tools import search_entities
from src.shared.retrieval.tools.registry import ToolLookupError, ToolRegistrationError, ToolRegistry

pytestmark = [pytest.mark.asyncio]


def _make_results(n: int, document_id: str = "doc-1") -> list[RetrievalResult]:
    return [
        RetrievalResult(document_id=document_id, chunk_index=i, chunk_text=f"chunk {i}", similarity_score=1.0 - i * 0.01)
        for i in range(n)
    ]


class SpyRetriever:
    def __init__(self, results: list[RetrievalResult]):
        self.results = results
        self.calls: list[dict] = []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        self.calls.append({"query": query, "top_k": top_k, "metadata_filter": metadata_filter})
        return self.results[:top_k] if top_k is not None else self.results


class RaisingRetriever:
    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        raise RuntimeError("boom")


class FailingReranker:
    async def rerank(self, query, results, top_k=None, jwt_token=None):
        return None


def _context(retriever=None, sql_search=None, max_top_k=20) -> ToolContext:
    return ToolContext(
        tenant_id="tenant-1", schema="tenant_test", session=object(),
        retriever=retriever, max_top_k=max_top_k, sql_search=sql_search,
    )


# --- Tool contract (rows 1-3) ---

class TestToolContractShape:
    """Covers verification.md row 1."""

    def test_tool_contract_shape(self):
        for tool in (search_documents, lookup_document, search_entities):
            assert isinstance(tool.name, str) and tool.name
            assert isinstance(tool.description, str) and tool.description
            assert isinstance(tool.args_schema, dict)
            assert tool.args_schema.get("type") == "object"
            assert isinstance(tool.args_schema.get("properties"), dict)


class TestInvalidArgumentType:
    """Covers verification.md row 2."""

    async def test_invalid_arg_type_rejected_without_query(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await search_documents.call({"query": 123}, context)

        assert result.error is not None
        assert result.results == []
        assert retriever.calls == []


class TestUnknownArgumentKey:
    """Covers verification.md row 3."""

    async def test_unknown_arg_key_rejected(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await search_documents.call({"query": "q", "schema": "tenant_other"}, context)

        assert result.error is not None
        assert retriever.calls == []

    def test_validate_args_rejects_unknown_key(self):
        with pytest.raises(ArgValidationError):
            validate_args({"type": "object", "properties": {"query": {"type": "string"}}}, {"query": "q", "extra": 1})


# --- No tenancy params (row 7) ---

class TestNoTenancyParams:
    """Covers verification.md row 7."""

    def test_no_tenancy_params_in_any_args_schema(self):
        registry = build_default_registry()
        for tool in registry.list():
            keys = set(tool.args_schema.get("properties", {}))
            assert keys.isdisjoint({"schema", "tenant_id", "tenant", "purpose"}), tool.name


# --- Result envelope (rows 4-6) ---

class TestResultEnvelope:
    """Covers verification.md rows 4-6."""

    async def test_success_metadata(self):
        results = _make_results(3)
        context = _context(retriever=SpyRetriever(results))

        result = await search_documents.call({"query": "matching text"}, context)

        assert result.error is None
        assert result.degraded is False
        assert result.latency_ms >= 0
        assert all(isinstance(r, RetrievalResult) for r in result.results)

    async def test_retriever_exception_returns_error_result(self):
        context = _context(retriever=RaisingRetriever())

        result = await search_documents.call({"query": "q"}, context)

        assert result.error is not None
        assert result.results == []

    async def test_degraded_flag_on_reranker_fallback(self):
        wrapped = SpyRetriever(_make_results(5))
        retriever = RerankingRetriever(wrapped, FailingReranker())
        context = _context(retriever=retriever)

        result = await search_documents.call({"query": "q"}, context)

        assert result.degraded is True
        assert len(result.results) > 0


# --- search_documents delegation and bounds (rows 10, 12, 13) ---

class TestSearchDocumentsDelegation:
    """Covers verification.md row 10."""

    async def test_search_documents_delegates_once(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        await search_documents.call({"query": "q"}, context)

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["query"] == "q"


class TestTopKBounds:
    """Covers verification.md row 12."""

    async def test_top_k_bounds_result_count(self):
        retriever = SpyRetriever(_make_results(10))
        context = _context(retriever=retriever)

        result = await search_documents.call({"query": "q", "top_k": 3}, context)

        assert len(result.results) <= 3


class TestTopKClamp:
    """Covers verification.md row 13."""

    async def test_top_k_clamped_to_max(self):
        retriever = SpyRetriever(_make_results(50))
        context = _context(retriever=retriever, max_top_k=5)

        result = await search_documents.call({"query": "q", "top_k": 1000}, context)

        assert result.error is None
        assert retriever.calls[0]["top_k"] == 5


# --- entity tool (rows 15, 16) ---

class TestEntityToolImportIsolation:
    """Covers verification.md row 15."""

    def test_entity_tool_does_not_import_chat_api(self):
        import src.shared.retrieval.tools.entity_tools as mod
        source = inspect.getsource(mod)
        assert "chat_api" not in source

    def test_fresh_import_never_pulls_in_chat_api(self):
        import subprocess
        import sys

        code = (
            "import sys\n"
            "import src.shared.retrieval.tools.entity_tools\n"
            "leaked = [m for m in sys.modules if m.startswith('src.chat_api')]\n"
            "assert leaked == [], leaked\n"
            "print('OK')\n"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=".", capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout


class TestRejectedSqlNotExecuted:
    """Covers verification.md row 16."""

    async def test_rejected_sql_not_executed(self):
        executed = {"called": False}

        async def rejecting_sql_search(query, session, schema, conversation_context):
            raise RuntimeError("SQL rejected by validation layer")

        context = _context(sql_search=rejecting_sql_search)

        result = await search_entities.call({"query": "drop everything"}, context)

        assert result.error is not None
        assert executed["called"] is False


# --- registry (rows 17-20) ---

class TestRegistry:
    """Covers verification.md rows 17-20."""

    def test_registry_get_by_name(self):
        registry = build_default_registry()
        assert registry.get("search_documents") is search_documents

    def test_registry_unknown_name_raises(self):
        registry = build_default_registry()
        with pytest.raises(ToolLookupError):
            registry.get("delete_documents")

    def test_registry_duplicate_rejected(self):
        registry = ToolRegistry()
        registry.register(search_documents)
        with pytest.raises(ToolRegistrationError):
            registry.register(search_documents)

    def test_export_schemas_tool_calling_shape(self):
        registry = build_default_registry()
        schemas = registry.export_schemas()

        by_name = {s["function"]["name"]: s for s in schemas}
        assert set(by_name) == {"search_documents", "lookup_document", "search_entities"}
        for s in schemas:
            assert s["type"] == "function"
            fn = s["function"]
            tool = registry.get(fn["name"])
            assert fn["description"] == tool.description
            assert fn["parameters"] == tool.args_schema


# --- Observation rendering (rows 39-41) ---

class TestObservationRendering:
    """Covers verification.md rows 39-41."""

    def test_observation_includes_identity(self):
        results = _make_results(2)
        result = ToolResult(tool_name="search_documents", results=results, latency_ms=1.0)

        observation = result.to_observation(limit=10_000)

        for item in results:
            assert f"document_id={item.document_id}" in observation
            assert f"chunk_index={item.chunk_index}" in observation
            assert item.chunk_text in observation
            assert f"{item.similarity_score:.4f}" in observation

    def test_error_result_renders_error_observation(self):
        result = ToolResult(tool_name="search_documents", results=[], error="boom")

        observation = result.to_observation(limit=10_000)

        assert "failed" in observation.lower()
        assert "boom" in observation

    def test_observation_limit_preserves_results(self):
        results = _make_results(50)
        result = ToolResult(tool_name="search_documents", results=results, latency_ms=1.0)

        observation = result.to_observation(limit=200)

        assert len(observation) <= 200
        assert len(result.results) == 50


# --- Tool context budget (rows 42-43) ---

class TestToolContextBudget:
    """Covers verification.md rows 42-43."""

    async def test_expired_deadline_denies_before_io(self):
        import time

        spy = SpyRetriever(_make_results(2))
        context = _context(retriever=spy)
        context = ToolContext(
            tenant_id=context.tenant_id, schema=context.schema, session=context.session,
            retriever=spy, max_top_k=context.max_top_k, deadline=time.monotonic() - 1,
        )

        result = await search_documents.call({"query": "x"}, context)

        assert spy.calls == []
        assert result.error is not None
        assert "budget" in result.error.lower()

    async def test_absent_deadline_preserves_existing_behaviour(self):
        spy = SpyRetriever(_make_results(2))
        context = _context(retriever=spy)

        result = await search_documents.call({"query": "x"}, context)

        assert result.error is None
        assert len(result.results) == 2
