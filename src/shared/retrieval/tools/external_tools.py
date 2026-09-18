"""External database retrieval tool (retrieval-tools spec, ADR-016).

Answers a natural-language question against the authenticated tenant's
connected Azure Database for PostgreSQL, through contract-grounded SQL
generation and drift-gated execution (`ToolContext.external_search`). Its
`args_schema` declares only `query` — no connection, contract, tenant, or
schema identifier — because the tool resolves its capability server-side from
`ToolContext.tenant_id`. Every failure returns a `ToolResult` with a finite
`error` reason class; nothing here raises.
"""

from __future__ import annotations

from src.shared.retrieval.tools.base import ToolContext, ToolResult, run_tool

# Truncation bounds for the per-turn, contract-derived tool description
# (design.md Decision 5): one relation line, and the whole block.
MAX_RELATION_LINE_CHARS = 200
MAX_DESCRIPTION_CHARS = 2000

_PURPOSE_TEXT = (
    "Answer a natural-language question against this tenant's connected "
    "PostgreSQL database by generating and running one read-only SQL query. "
    "Use it for questions about the connected database's own records — not "
    "for questions about uploaded documents."
)


class _AnswerRejected(Exception):
    """Carries a finite outcome reason and nothing else; `str(e)` is the
    reason itself, so `run_tool`'s generic `error=str(e)` handling turns it
    into exactly the reason class the caller needs."""


def render_external_tool_description(contract: dict) -> str:
    """The tool's per-turn description: fixed purpose text plus one line per
    contract relation (name, and its description where present), each
    truncated, the whole block capped (design.md Decision 5)."""
    canonical = contract.get("canonical") or {}
    relations = canonical.get("relations") or {}
    lines = [_PURPOSE_TEXT, "Relations in this tenant's connected database:"]
    for name in sorted(relations):
        relation_def = relations[name] if isinstance(relations[name], dict) else {}
        description = relation_def.get("description")
        line = f"- {name} — {description}" if description else f"- {name}"
        if len(line) > MAX_RELATION_LINE_CHARS:
            line = line[: MAX_RELATION_LINE_CHARS - 1].rstrip() + "…"
        lines.append(line)
    rendered = "\n".join(lines)
    if len(rendered) > MAX_DESCRIPTION_CHARS:
        rendered = rendered[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"
    return rendered


class ExternalDatabaseTool:
    """One instance per turn, built with a description rendered from the
    authenticated tenant's own published contract (never a shared, static
    instance across tenants)."""

    name = "external_database"
    args_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural-language question to answer against the connected database.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, description: str):
        self.description = description

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        captured: dict = {}

        async def executor(args: dict, context: ToolContext) -> tuple[list, bool]:
            if context.external_search is None:
                raise RuntimeError("ToolContext has no external_search configured")
            answer = await context.external_search(
                args["query"], context.session, context.tenant_id,
                context.conversation_context, context.deadline,
            )
            if answer.reason is not None:
                raise _AnswerRejected(answer.reason)
            captured["completeness"] = {
                "returned": len(answer.rows), "matched": None, "truncated": bool(answer.truncated),
            }
            captured["relations"] = list(answer.relations)
            return list(answer.rows), False

        result = await run_tool(self.name, self.args_schema, args, context, executor)
        if result.error is None:
            result.result_completeness = captured.get("completeness")
            result.diagnostics = [{"relations": captured.get("relations", [])}]
        return result
