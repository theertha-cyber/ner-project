"""The `tabular_files` retrieval tool (retrieval-tools spec)."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from src.chat_api.graph import nodes as nodes_module
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.chat_api.services.tabular_cache import ParquetCache
from src.chat_api.services.tabular_sql_generator import TabularSQLGenerator
from src.shared.config import settings
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.base import FORBIDDEN_ARG_KEYS, ToolContext
from src.shared.retrieval.tools.tabular_tools import TABULAR_CAPABILITY_NAME, TabularFilesTool
from src.shared.tabular_files import store
from tests.tabular_support import (  # noqa: F401
    FakeObjectStore,
    ScriptedGeneratorClient,
    make_file,
    session_factory,
    tenants,
    write_parquet,
)

pytestmark = [pytest.mark.verification]

QUERY = {"sql": "SELECT region, SUM(amount) AS total FROM sales_q3 GROUP BY region ORDER BY region", "params": {}}


def test_tool_schema_exposes_no_tenancy_or_file_location_parameters():
    """Scenario: Tool schema exposes no tenancy or file-location parameters."""
    keys = set(TabularFilesTool("d").args_schema["properties"])
    assert keys == {"query"}
    assert not keys & ({"schema", "tenant_id", "tenant", "file_id", "path"} | FORBIDDEN_ARG_KEYS)


@pytest.fixture
async def two_tenants(tenants, session_factory, tmp_path, monkeypatch):
    """Tenants A and B, each with a ready `sales_q3` whose Parquet holds
    different rows, behind one object store and one cache."""
    monkeypatch.setattr(settings, "tabular_files_enabled", True)
    objects = FakeObjectStore()
    ids = {}
    for label, amount in (("A", 100), ("B", 999)):
        tenant_id = await tenants()
        path = write_parquet(tmp_path / f"{label}.parquet",
                             f"SELECT 'EMEA' AS region, 'closed' AS status, {amount}::BIGINT AS amount")
        file_id = await make_file(session_factory, tenant_id)
        async with session_factory() as session:
            key = (await session.execute(
                text(f"SELECT parquet_key FROM {store.VERSIONS_TABLE} WHERE file_id = :f"), {"f": file_id},
            )).scalar()
        objects.put_file(key, path)
        ids[label] = tenant_id
    cache = ParquetCache(root=str(tmp_path / "cache"), max_bytes=10**9, object_store_factory=lambda: objects)
    return ids, cache


def _context(tenant_id, generator):
    return ToolContext(tenant_id=tenant_id, schema=f"tenant_{tenant_id}", session=None,
                       tabular_search=generator.answer)


async def test_tool_reads_only_the_context_tenants_files(two_tenants):
    """Scenario: Tool reads only the context tenant's files."""
    ids, cache = two_tenants
    for label, expected in (("A", 100), ("B", 999)):
        generator = TabularSQLGenerator(cache=cache)
        generator.client = ScriptedGeneratorClient(QUERY)
        result = await TabularFilesTool("d").call({"query": "revenue by region"}, _context(ids[label], generator))
        assert result.error is None, result.error
        assert result.results == [{"region": "EMEA", "total": expected}]


async def test_tool_registered_only_when_a_file_is_ready(two_tenants, tenants, monkeypatch):
    """Scenario: Tool registered only when a file is ready."""
    ids, _cache = two_tenants

    async def no_external(session, tenant_id):
        return {"executable": False}

    monkeypatch.setattr(nodes_module, "resolve_external_capability", no_external)
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[]))])

    orchestrator.llm_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    orchestrator.llm_model = "gpt-4o"
    orchestrator.tool_registry = build_default_registry()
    node = build_nodes(orchestrator)["orchestrator"]

    ready = (await node({"message": "q", "tenant_id": ids["A"], "schema": "s", "session": None}))["tool_registry"]
    assert ready.get(TABULAR_CAPABILITY_NAME).name == TABULAR_CAPABILITY_NAME
    assert TABULAR_CAPABILITY_NAME in [s["function"]["name"] for s in ready.export_schemas()]

    empty_tenant = await tenants()
    empty = (await node({"message": "q", "tenant_id": empty_tenant, "schema": "s", "session": None}))["tool_registry"]
    assert TABULAR_CAPABILITY_NAME not in [t.name for t in empty.list()]


async def test_envelope_omits_sql_text(two_tenants):
    """Scenario: Envelope omits SQL text."""
    ids, cache = two_tenants
    generator = TabularSQLGenerator(cache=cache)
    generator.client = ScriptedGeneratorClient(QUERY)
    result = await TabularFilesTool("d").call({"query": "revenue by region"}, _context(ids["A"], generator))
    [envelope] = result.diagnostics
    assert envelope["relations"] == ["sales_q3"]
    assert envelope["columns"] == ["amount", "region"]
    assert envelope["truncated"] is False
    assert result.results == [{"region": "EMEA", "total": 100}]
    serialized = json.dumps({"results": result.results, "diagnostics": result.diagnostics,
                             "completeness": result.result_completeness, "error": result.error})
    assert "SELECT" not in serialized and "GROUP BY" not in serialized


async def test_failure_is_a_finite_outcome_class(two_tenants):
    ids, cache = two_tenants
    generator = TabularSQLGenerator(cache=cache)
    bad = {"sql": "DROP TABLE sales_q3", "params": {}}
    generator.client = ScriptedGeneratorClient(bad, bad, bad)
    result = await TabularFilesTool("d").call({"query": "x"}, _context(ids["A"], generator))
    assert result.error == "generation_exhausted"
    assert result.results == []


async def test_unknown_argument_is_refused():
    result = await TabularFilesTool("d").call({"query": "x", "tenant_id": "other"},
                                              ToolContext(tenant_id="t", schema="s", session=None))
    assert result.error and "unknown argument" in result.error
