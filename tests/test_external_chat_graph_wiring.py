"""Verification for chat graph wiring of the `external_database` capability
(design.md Decisions 5 and 6; ADR-015, ADR-016).

Maps to
`openspec/changes/external-postgresql-chat-sql-generation/verification.md`
Section 1 rows 23, 25, 26, 30-33, and Risk 5 in the Hallucination Risk Register.

Node-level, following the `build_nodes(orchestrator)` + hand-built
`RAGOrchestrator.__new__` pattern already used by
`tests/test_entity_resolution_graph.py`: only the module functions each test
actually exercises are faked; everything else runs for real.
"""

import json
from types import SimpleNamespace

import pytest

from src.chat_api.graph import nodes as nodes_module
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.context_assembler import ContextAssembler
from src.chat_api.services.external_postgres_chat import EXTERNAL_OUTCOME_MESSAGES
from src.chat_api.services.rag_orchestrator import RAGOrchestrator
from src.shared.retrieval.orchestrator import (
    EXTERNAL_CAPABILITY_NAME,
    build_fallback_plan,
    plan_retrieval,
)
from src.shared.retrieval.tools import build_default_registry
from src.shared.retrieval.tools.registry import ToolRegistry

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class _SentinelSession:
    """Never dereferenced: every test here either avoids the DB entirely or
    monkeypatches the module function that would touch it."""


def _tool_call(name: str, arguments: str, call_id: str = "c1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


class ScriptedPlannerClient:
    """Records nothing beyond returning the scripted tool calls; adequate for
    orchestrator_node, which only reads `.choices[0].message.tool_calls`."""

    def __init__(self, tool_calls=()):
        self.tool_calls = list(tool_calls)

        async def create(**kwargs):
            message = SimpleNamespace(content=None, tool_calls=list(self.tool_calls))
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


@pytest.fixture
def orchestrator():
    o = RAGOrchestrator.__new__(RAGOrchestrator)
    o.llm_client = ScriptedPlannerClient()
    o.llm_model = "gpt-4o"
    o.tool_registry = build_default_registry()
    return o


@pytest.fixture
def nodes(orchestrator):
    return build_nodes(orchestrator)


def _base_state(orchestrator, tool_calls=()):
    orchestrator.llm_client = ScriptedPlannerClient(tool_calls)
    return {
        "message": "how many unclaimed users are there",
        "tenant_id": "tenant-a",
        "schema": "tenant_tenant_a",
        "session": _SentinelSession(),
        "conversation_context": None,
    }


EXECUTABLE_CONTRACT = {
    "version": 2,
    "canonical": {
        "relations": {
            "fisc_user_profile": {
                "columns": ["record_id", "claim_ind"],
                "description": "User profiles with claim/approver flags.",
            },
        },
        "joins": [],
    },
}


class TestPerTurnToolAvailability:
    """Rows 30-33."""

    async def test_tool_not_offered_without_capability(self, orchestrator, nodes, monkeypatch):
        async def fake_resolve(session, tenant_id):
            return {"executable": False, "reason": "not_active_connection"}

        monkeypatch.setattr(nodes_module, "resolve_external_capability", fake_resolve)

        state = _base_state(orchestrator)
        result = await nodes["orchestrator"](state)

        registry = result["tool_registry"]
        assert EXTERNAL_CAPABILITY_NAME not in {t.name for t in registry.list()}
        # Byte-identical fallback: the platform registry itself, never a copy.
        assert registry is orchestrator.tool_registry

    async def test_tool_offered_with_contract_relations_in_description(self, orchestrator, nodes, monkeypatch):
        async def fake_resolve(session, tenant_id):
            return {"executable": True, "connection_id": "conn-1", "contract": EXECUTABLE_CONTRACT}

        monkeypatch.setattr(nodes_module, "resolve_external_capability", fake_resolve)

        state = _base_state(orchestrator)
        result = await nodes["orchestrator"](state)

        registry = result["tool_registry"]
        names = {t.name for t in registry.list()}
        assert EXTERNAL_CAPABILITY_NAME in names
        tool = registry.get(EXTERNAL_CAPABILITY_NAME)
        assert "fisc_user_profile" in tool.description
        # The platform registry is never mutated or reassigned.
        assert EXTERNAL_CAPABILITY_NAME not in {t.name for t in orchestrator.tool_registry.list()}
        exported_names = {schema["function"]["name"] for schema in registry.export_schemas()}
        assert EXTERNAL_CAPABILITY_NAME in exported_names

    async def test_unoffered_external_entry_rejected(self):
        registry = build_default_registry()  # no external_database registered
        client = ScriptedPlannerClient([_tool_call(EXTERNAL_CAPABILITY_NAME, "{}")])

        plan = await plan_retrieval("q", None, client, "gpt-4o", registry)

        entry = plan.entries[0]
        assert entry.capability_name == EXTERNAL_CAPABILITY_NAME
        assert entry.rejected is True

    async def test_fallback_plan_excludes_external_tool(self, orchestrator, monkeypatch):
        async def fake_resolve(session, tenant_id):
            return {"executable": True, "connection_id": "conn-1", "contract": EXECUTABLE_CONTRACT}

        monkeypatch.setattr(nodes_module, "resolve_external_capability", fake_resolve)

        state = _base_state(orchestrator, tool_calls=())  # empty plan -> degraded fallback
        result = await (build_nodes(orchestrator)["orchestrator"])(state)

        plan = result["retrieval_plan"]
        assert result["orchestration_degraded"] is True
        assert all(e.capability_name != EXTERNAL_CAPABILITY_NAME for e in plan.entries)


class TestCapabilityResolutionErrorIsolation:
    """Risk 5."""

    async def test_capability_resolution_error_keeps_platform_chat(self, orchestrator, nodes, monkeypatch):
        async def fake_resolve(session, tenant_id):
            raise RuntimeError("boom")

        monkeypatch.setattr(nodes_module, "resolve_external_capability", fake_resolve)

        state = _base_state(orchestrator, tool_calls=())
        result = await nodes["orchestrator"](state)

        # No exception propagated, and the tenant still gets the platform registry.
        assert result["tool_registry"] is orchestrator.tool_registry
        assert "retrieval_plan" in result


class TestExternalEvidenceChannel:
    """Rows 23, 25, 26 — the citation and prompt never carry row values, and a
    finite failure reason always renders its fixed message."""

    async def test_external_citation_persists_relation_names_only(self, orchestrator, nodes):
        _messages, admitted = ContextAssembler().assemble(
            "how many unclaimed users", None, [], {}, None,
            external_results=[{"person_firstname": "Arjun"}],
            external_relations=["fisc_user_profile"],
            external_truncated=False,
            return_evidence=True,
        )
        state = {
            "tenant_id": "tenant-a", "schema": "tenant_tenant_a",
            "session": _SentinelSession(),
            "admitted_evidence": admitted, "document_names": {},
        }
        result = await nodes["source_assembly"](state)

        sources = result["sources"]
        external_sources = [s for s in sources if s.source_type == "external_postgresql"]
        assert len(external_sources) == 1
        # `_enrich_citations` turns every `Source` into a `Citation`, carrying the
        # JSON payload on `entity_value` (the same treatment the "sql" source gets).
        payload = json.loads(external_sources[0].entity_value)
        assert payload == {"relations": ["fisc_user_profile"]}
        for source in sources:
            rendered = json.dumps(source.model_dump(), default=str)
            assert "Arjun" not in rendered

    async def test_drift_outcome_yields_fixed_admin_message(self):
        messages, admitted = ContextAssembler().assemble(
            "how many unclaimed users", None, [], {}, None,
            external_failure_reason="drift_mismatch",
            return_evidence=True,
        )
        rendered = json.dumps(messages)
        assert EXTERNAL_OUTCOME_MESSAGES["drift_mismatch"] in rendered
        assert admitted.external_relations == []

    async def test_execution_failure_text_not_surfaced(self):
        messages, admitted = ContextAssembler().assemble(
            "how many unclaimed users", None, [], {}, None,
            external_failure_reason="execution_failed",
            return_evidence=True,
        )
        rendered = json.dumps(messages)
        assert EXTERNAL_OUTCOME_MESSAGES["execution_failed"] in rendered
        # No database error text of any kind reaches the prompt — only the fixed
        # message, because the caller never has raw error text to pass in.
        assert "UndefinedColumn" not in rendered
        assert "asyncpg" not in rendered
        assert admitted.external_relations == []


def test_registry_fallback_plan_excludes_external_tool_when_offered():
    """Row 33, at the `build_fallback_plan` unit rather than through the node."""
    registry = ToolRegistry()
    for tool in build_default_registry().list():
        registry.register(tool)
    from src.shared.retrieval.tools.external_tools import ExternalDatabaseTool
    registry.register(ExternalDatabaseTool(description="desc"))

    plan = build_fallback_plan("q", registry)

    assert all(e.capability_name != EXTERNAL_CAPABILITY_NAME for e in plan.entries)
