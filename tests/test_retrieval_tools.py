import inspect

import pytest

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import ToolContext, ToolResult, validate_args, ArgValidationError
from src.shared.retrieval.tools.document_tools import semantic_retrieval
from src.shared.retrieval.tools.entity_tools import structured_retrieval
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
        if metadata_filter and "document_ids" in metadata_filter:
            allowed = set(metadata_filter["document_ids"])
            filtered = [r for r in self.results if r.document_id in allowed]
            return filtered[:top_k] if top_k is not None else filtered
        if metadata_filter and "document_id" in metadata_filter:
            filtered = [r for r in self.results if r.document_id == metadata_filter["document_id"]]
            return filtered[:top_k] if top_k is not None else filtered
        return self.results[:top_k] if top_k is not None else self.results


class RaisingRetriever:
    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        raise RuntimeError("boom")


class FailingReranker:
    async def rerank(self, query, results, top_k=None, jwt_token=None):
        return None


def _context(retriever=None, sql_search=None, max_top_k=20, conversation_context=None) -> ToolContext:
    return ToolContext(
        tenant_id="tenant-1", schema="tenant_test", session=object(),
        retriever=retriever, max_top_k=max_top_k, sql_search=sql_search,
        conversation_context=conversation_context,
    )


# --- Tool contract shape ---

class TestToolContractShape:
    def test_tool_contract_shape(self):
        for tool in (semantic_retrieval, structured_retrieval):
            assert isinstance(tool.name, str) and tool.name
            assert isinstance(tool.description, str) and tool.description
            assert isinstance(tool.args_schema, dict)
            assert tool.args_schema.get("type") == "object"
            assert isinstance(tool.args_schema.get("properties"), dict)


class TestInvalidArgumentType:
    async def test_invalid_arg_type_rejected_without_query(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": 123}, context)

        assert result.error is not None
        assert result.results == []
        assert retriever.calls == []


class TestUnknownArgumentKey:
    async def test_unknown_arg_key_rejected(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q", "schema": "tenant_other"}, context)

        assert result.error is not None
        assert retriever.calls == []

    def test_validate_args_rejects_unknown_key(self):
        with pytest.raises(ArgValidationError):
            validate_args({"type": "object", "properties": {"query": {"type": "string"}}}, {"query": "q", "extra": 1})


class TestNoTenancyParams:
    def test_no_tenancy_params_in_any_args_schema(self):
        registry = build_default_registry()
        for tool in registry.list():
            keys = set(tool.args_schema.get("properties", {}))
            assert keys.isdisjoint({"schema", "tenant_id", "tenant", "purpose"}), tool.name


class TestResultEnvelope:
    async def test_success_metadata(self):
        results = _make_results(3)
        context = _context(retriever=SpyRetriever(results))

        result = await semantic_retrieval.call({"query": "matching text"}, context)

        assert result.error is None
        assert result.degraded is False
        assert result.latency_ms >= 0
        assert all(isinstance(r, RetrievalResult) for r in result.results)

    async def test_retriever_exception_returns_error_result(self):
        context = _context(retriever=RaisingRetriever())

        result = await semantic_retrieval.call({"query": "q"}, context)

        assert result.error is not None
        assert result.results == []

    async def test_degraded_flag_on_reranker_fallback(self):
        wrapped = SpyRetriever(_make_results(5))
        retriever = RerankingRetriever(wrapped, FailingReranker())
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q"}, context)

        assert result.degraded is True
        assert len(result.results) > 0


class TestSemanticRetrievalDelegation:
    async def test_semantic_retrieval_delegates_once(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        await semantic_retrieval.call({"query": "q"}, context)

        assert len(retriever.calls) == 1
        assert retriever.calls[0]["query"] == "q"


class TestTopKBounds:
    async def test_top_k_bounds_result_count(self):
        retriever = SpyRetriever(_make_results(10))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q", "top_k": 3}, context)

        assert len(result.results) <= 3


class TestTopKClamp:
    """Covers verification.md row 30."""

    async def test_top_k_clamped_to_max(self):
        retriever = SpyRetriever(_make_results(50))
        context = _context(retriever=retriever, max_top_k=5)

        result = await semantic_retrieval.call({"query": "q", "top_k": 1000}, context)

        assert result.error is None
        assert retriever.calls[0]["top_k"] == 5


# --- Scope (rows 26-29) ---

class TestDefaultTenantScope:
    """Covers verification.md row 26."""

    async def test_default_tenant_scope_no_filter(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q"}, context)

        assert result.error is None
        assert retriever.calls[0]["metadata_filter"] is None

    async def test_explicit_tenant_scope_no_filter(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q", "scope": {"type": "tenant"}}, context)

        assert result.error is None
        assert retriever.calls[0]["metadata_filter"] is None


class TestDocumentScope:
    """Covers verification.md row 27."""

    async def test_document_scope_restricts_results(self):
        results = _make_results(2, document_id="D1") + _make_results(2, document_id="D2")
        retriever = SpyRetriever(results)
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call(
            {"query": "q", "scope": {"type": "document", "document_ids": ["D1"]}}, context
        )

        assert result.error is None
        assert all(r.document_id == "D1" for r in result.results)
        assert retriever.calls[0]["metadata_filter"] == {"document_ids": ["D1"]}


class TestDocumentScopeMultiple:
    """Covers verification.md row 28 (non-integration slice)."""

    async def test_document_scope_accepts_multiple_documents(self):
        results = (
            _make_results(1, document_id="D1")
            + _make_results(1, document_id="D2")
            + _make_results(1, document_id="D3")
        )
        retriever = SpyRetriever(results)
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call(
            {"query": "q", "scope": {"type": "document", "document_ids": ["D1", "D2"]}}, context
        )

        assert result.error is None
        assert {r.document_id for r in result.results} <= {"D1", "D2"}


class TestUnknownScopeType:
    """Covers verification.md row 29."""

    async def test_unknown_scope_type_rejected(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q", "scope": {"type": "galaxy"}}, context)

        assert result.error is not None
        assert "galaxy" in result.error
        assert retriever.calls == []

    async def test_document_scope_without_document_ids_rejected(self):
        retriever = SpyRetriever(_make_results(3))
        context = _context(retriever=retriever)

        result = await semantic_retrieval.call({"query": "q", "scope": {"type": "document"}}, context)

        assert result.error is not None
        assert retriever.calls == []


# --- structured_retrieval (renamed from search_entities) ---

class TestEntityToolImportIsolation:
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
    async def test_rejected_sql_not_executed(self):
        executed = {"called": False}

        async def rejecting_sql_search(query, session, schema, conversation_context, **_kwargs):
            raise RuntimeError("SQL rejected by validation layer")

        context = _context(sql_search=rejecting_sql_search)

        result = await structured_retrieval.call({"query": "drop everything"}, context)

        assert result.error is not None
        assert executed["called"] is False


class TestConversationContextReachesSqlSearch:
    """A tool is invoked with its `arguments` alone — the planner's view of the
    conversation never travels with them. Anything the tool must resolve against
    earlier turns has to arrive through ToolContext, so a follow-up like "which of
    those candidates …" is answered against the set the user meant rather than
    against the whole tenant."""

    async def test_conversation_context_is_forwarded(self):
        seen = {}

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            seen["conversation_context"] = conversation_context
            return []

        history = [
            {"role": "user", "content": "fetch me the names of candidates who know python"},
            {"role": "assistant", "content": "Mahalakshmi S, Hannah, Harshith Akshayraj R.S"},
        ]
        context = _context(sql_search=sql_search, conversation_context=history)

        await structured_retrieval.call({"query": "which of the following suit an AI role"}, context)

        assert seen["conversation_context"] == history

    async def test_absent_conversation_context_is_forwarded_as_none(self):
        seen = {}

        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            seen["conversation_context"] = conversation_context
            return []

        await structured_retrieval.call({"query": "q"}, _context(sql_search=sql_search))

        assert seen["conversation_context"] is None


class TestCandidateDocumentIds:
    """Covers verification.md rows 38-40 (normalized-entity-store change)."""

    async def test_candidate_ids_are_distinct_document_ids_of_result_rows(self):
        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"document_id": "docA"}, {"document_id": "docA"}, {"document_id": "docB"}]

        context = _context(sql_search=sql_search)
        result = await structured_retrieval.call({"query": "q"}, context)

        assert result.candidate_document_ids == {"docA", "docB"}
        assert len(result.results) == 3

    async def test_no_document_id_column_yields_no_candidates(self):
        async def sql_search(query, session, schema, conversation_context, **_kwargs):
            return [{"entity_type": "ORG", "count": 3}]

        context = _context(sql_search=sql_search)
        result = await structured_retrieval.call({"query": "q"}, context)

        assert result.candidate_document_ids == set()

    async def test_failed_invocation_yields_no_candidates(self):
        async def rejecting_sql_search(query, session, schema, conversation_context, **_kwargs):
            raise RuntimeError("SQL rejected by validation layer")

        context = _context(sql_search=rejecting_sql_search)
        result = await structured_retrieval.call({"query": "q"}, context)

        assert result.error is not None
        assert result.candidate_document_ids == set()


# --- registry (rows 32-33) ---

class TestRegistry:
    """Covers verification.md rows 32-33."""

    def test_registry_get_by_name(self):
        registry = build_default_registry()
        assert registry.get("semantic_retrieval") is semantic_retrieval
        assert registry.get("structured_retrieval") is structured_retrieval

    def test_registry_unknown_name_raises(self):
        registry = build_default_registry()
        with pytest.raises(ToolLookupError):
            registry.get("delete_documents")

    def test_registry_duplicate_rejected(self):
        registry = ToolRegistry()
        registry.register(semantic_retrieval)
        with pytest.raises(ToolRegistrationError):
            registry.register(semantic_retrieval)

    def test_registry_exposes_two_capabilities(self):
        registry = build_default_registry()
        schemas = registry.export_schemas()

        by_name = {s["function"]["name"]: s for s in schemas}
        assert set(by_name) == {"semantic_retrieval", "structured_retrieval"}
        for s in schemas:
            assert s["type"] == "function"
            fn = s["function"]
            tool = registry.get(fn["name"])
            assert fn["description"] == tool.description
            assert fn["parameters"] == tool.args_schema

    def test_capability_descriptions_state_intent_not_implementation(self):
        registry = build_default_registry()
        for tool in registry.list():
            description = tool.description.lower()
            for implementation_term in ("pgvector", "sql", "postgres", "index", "embedding"):
                assert implementation_term not in description, (tool.name, implementation_term)


# --- Observation rendering ---

class TestObservationRendering:
    def test_observation_includes_identity(self):
        results = _make_results(2)
        result = ToolResult(tool_name="semantic_retrieval", results=results, latency_ms=1.0)

        observation = result.to_observation(limit=10_000)

        for item in results:
            assert f"document_id={item.document_id}" in observation
            assert f"chunk_index={item.chunk_index}" in observation
            assert item.chunk_text in observation
            assert f"{item.similarity_score:.4f}" in observation

    def test_error_result_renders_error_observation(self):
        result = ToolResult(tool_name="semantic_retrieval", results=[], error="boom")

        observation = result.to_observation(limit=10_000)

        assert "failed" in observation.lower()
        assert "boom" in observation

    def test_observation_limit_preserves_results(self):
        results = _make_results(50)
        result = ToolResult(tool_name="semantic_retrieval", results=results, latency_ms=1.0)

        observation = result.to_observation(limit=200)

        assert len(observation) <= 200
        assert len(result.results) == 50


# --- Tool context budget ---

class TestToolContextBudget:
    async def test_expired_deadline_denies_before_io(self):
        import time

        spy = SpyRetriever(_make_results(2))
        context = _context(retriever=spy)
        context = ToolContext(
            tenant_id=context.tenant_id, schema=context.schema, session=context.session,
            retriever=spy, max_top_k=context.max_top_k, deadline=time.monotonic() - 1,
        )

        result = await semantic_retrieval.call({"query": "x"}, context)

        assert spy.calls == []
        assert result.error is not None
        assert "budget" in result.error.lower()

    async def test_absent_deadline_preserves_existing_behaviour(self):
        spy = SpyRetriever(_make_results(2))
        context = _context(retriever=spy)

        result = await semantic_retrieval.call({"query": "x"}, context)

        assert result.error is None
        assert len(result.results) == 2
