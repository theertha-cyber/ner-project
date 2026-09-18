"""Verification for the `external_database` retrieval tool (retrieval-tools spec).

Maps to
`openspec/changes/external-postgresql-chat-sql-generation/verification.md`
Section 1 rows 27-29.

Runs entirely offline: `ToolContext.external_search` is a small fake that
returns scripted `ExternalAnswer`-shaped results, since the tool only ever
calls it and reads `.rows` / `.truncated` / `.relations` / `.reason` off
whatever it returns.
"""

import pytest

from src.chat_api.services.external_sql_generator import ExternalAnswer
from src.shared.retrieval.tools.base import ToolContext
from src.shared.retrieval.tools.external_tools import ExternalDatabaseTool
from src.shared.retrieval.tools.registry import ToolRegistry

pytestmark = [pytest.mark.verification]

SAMPLE_CONTRACT = {
    "canonical": {
        "relations": {
            "fisc_user_profile": {"columns": ["record_id"], "description": "User profiles"},
        },
    },
}


def _context(external_search) -> ToolContext:
    return ToolContext(
        tenant_id="tenant-a", schema="tenant_a", session=None,
        external_search=external_search,
    )


def test_args_schema_only_query():
    tool = ExternalDatabaseTool(description="desc")
    assert set(tool.args_schema["properties"]) == {"query"}


async def test_successful_call_returns_rows():
    async def fake_search(query, session, tenant_id, conversation_context, deadline):
        return ExternalAnswer(rows=[{"count": 1}, {"count": 2}], truncated=False,
                              relations=["fisc_user_profile"])

    tool = ExternalDatabaseTool(description="desc")
    result = await tool.call({"query": "how many unclaimed"}, _context(fake_search))

    assert result.error is None
    assert len(result.results) == 2
    assert result.result_completeness == {"returned": 2, "matched": None, "truncated": False}
    assert result.diagnostics == [{"relations": ["fisc_user_profile"]}]


async def test_drift_returns_finite_error():
    async def fake_search(query, session, tenant_id, conversation_context, deadline):
        return ExternalAnswer(reason="drift_mismatch")

    tool = ExternalDatabaseTool(description="desc")
    result = await tool.call({"query": "how many unclaimed"}, _context(fake_search))

    assert result.error == "drift_mismatch"
    assert result.results == []


def test_registry_accepts_external_database_tool():
    registry = ToolRegistry()
    tool = ExternalDatabaseTool(description="desc")
    registry.register(tool)  # raises on a forbidden-arg schema; args_schema is {query} only.
    assert registry.get("external_database") is tool
