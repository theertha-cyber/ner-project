"""Capability-gated tabular tool (tabular-file-chat spec): per-turn registration
in `orchestrator_node`, byte-identical planner input without ready files, safe
degradation and the kill switch. Capability resolution runs against the real
test database; only the planner LLM is scripted."""

import json
from types import SimpleNamespace

import pytest

from src.chat_api.graph import nodes as nodes_module
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.config import settings
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.tabular_tools import (
    TABULAR_CAPABILITY_NAME,
    TABULAR_TOOL_ADDENDUM,
    render_tabular_tool_description,
)
from src.shared.tabular_files import capability as capability_module
from tests.tabular_support import (  # noqa: F401
    SALES_CONTRACT,
    make_file,
    session_factory,
    tenants,
)

pytestmark = [pytest.mark.verification]


class RecordingPlanner:
    """Scripted planner that records every request it receives, so planner
    input can be compared byte for byte."""

    def __init__(self):
        self.requests: list[str] = []

        async def create(**kwargs):
            self.requests.append(json.dumps(
                {k: kwargs[k] for k in ("model", "messages", "tools", "tool_choice", "temperature") if k in kwargs},
                sort_keys=True, default=str,
            ))
            message = SimpleNamespace(content=None, tool_calls=[])
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


@pytest.fixture
def orchestrator(monkeypatch):
    async def no_external(session, tenant_id):
        return {"executable": False, "reason": "not_active_connection"}

    monkeypatch.setattr(nodes_module, "resolve_external_capability", no_external)
    monkeypatch.setattr(settings, "tabular_files_enabled", True)
    o = RAGOrchestrator.__new__(RAGOrchestrator)
    o.llm_client = RecordingPlanner()
    o.llm_model = "gpt-4o"
    o.tool_registry = build_default_registry()
    return o


async def _plan(orchestrator, tenant_id):
    state = {"message": "total closed revenue in EMEA?", "tenant_id": tenant_id,
             "schema": f"tenant_{tenant_id}", "session": object(), "conversation_context": None}
    result = await build_nodes(orchestrator)["orchestrator"](state)
    return result["tool_registry"], orchestrator.llm_client.requests[-1]


async def test_tenant_with_a_ready_file_gets_the_tool(orchestrator, tenants, session_factory):
    """Scenario: Tenant with a ready file gets the tool."""
    tenant_id = await tenants()
    await make_file(session_factory, tenant_id)
    registry, request = await _plan(orchestrator, tenant_id)
    tool = registry.get(TABULAR_CAPABILITY_NAME)
    for fragment in ("sales_q3", "region (text)", "status (text)", "amount (bigint)"):
        assert fragment in tool.description
    assert TABULAR_CAPABILITY_NAME in {s["function"]["name"] for s in registry.export_schemas()}
    assert TABULAR_TOOL_ADDENDUM in request
    assert TABULAR_CAPABILITY_NAME not in {t.name for t in orchestrator.tool_registry.list()}


async def test_tenant_without_ready_files_sees_no_change(orchestrator, tenants, session_factory):
    """Scenario: Tenant without ready files sees no change (byte-identical)."""
    no_files, reviewing = await tenants(), await tenants()
    await make_file(session_factory, reviewing, status="needs_review")
    registry_a, request_a = await _plan(orchestrator, no_files)
    registry_b, request_b = await _plan(orchestrator, reviewing)
    assert request_a.replace(no_files, "T") == request_b.replace(reviewing, "T")
    assert request_a == request_b
    assert registry_b is orchestrator.tool_registry


async def test_resolution_failure_degrades_safely(orchestrator, tenants, session_factory, monkeypatch):
    """Scenario: Resolution failure degrades safely."""
    tenant_id = await tenants()
    await make_file(session_factory, tenant_id)

    async def broken(session, tid):
        raise RuntimeError("control plane down")

    monkeypatch.setattr(nodes_module, "resolve_tabular_capability", broken)
    registry, _request = await _plan(orchestrator, tenant_id)
    assert TABULAR_CAPABILITY_NAME not in {t.name for t in registry.list()}
    assert {t.name for t in registry.list()} == {t.name for t in orchestrator.tool_registry.list()}


async def test_another_tenants_files_are_never_offered(orchestrator, tenants, session_factory):
    """Scenario: Another tenant's files are never offered."""
    tenant_a, tenant_b = await tenants(), await tenants()
    await make_file(session_factory, tenant_a)
    registry, request = await _plan(orchestrator, tenant_b)
    assert TABULAR_CAPABILITY_NAME not in {t.name for t in registry.list()}
    assert "sales_q3" not in request


async def test_kill_switch_removes_the_tool(orchestrator, tenants, session_factory, monkeypatch):
    """Scenario: Kill switch removes the tool — without reading any table."""
    with_file, without = await tenants(), await tenants()
    await make_file(session_factory, with_file)
    monkeypatch.setattr(settings, "tabular_files_enabled", False)

    async def must_not_read(session, tid):
        raise AssertionError("kill switch must short-circuit before any read")

    monkeypatch.setattr(capability_module, "ready_contracts", must_not_read)
    registry, request = await _plan(orchestrator, with_file)
    _registry, baseline = await _plan(orchestrator, without)
    assert TABULAR_CAPABILITY_NAME not in {t.name for t in registry.list()}
    assert request == baseline


def test_description_budget_lists_overflow_by_name():
    files = [{"contract": {**SALES_CONTRACT, "relation": f"file_{i}",
                           "columns": SALES_CONTRACT["columns"] * 5}} for i in range(20)]
    description = render_tabular_tool_description(files, token_budget=400)
    assert "table file_0" in description
    assert "table file_19" not in description
    assert "More uploaded files (columns omitted):" in description
    assert "file_19" in description
