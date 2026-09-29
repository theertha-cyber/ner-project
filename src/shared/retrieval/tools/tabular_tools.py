"""Uploaded tabular files retrieval tool (retrieval-tools spec, ADR-018).

Answers a natural-language question from the authenticated tenant's published
uploaded files through contract-validated SQL and a locked DuckDB executor
(`ToolContext.tabular_search`). Its `args_schema` declares only `query` — no
tenant, file id or path — because the tool resolves the tenant's served files
server-side from `ToolContext.tenant_id`. Its result carries rows, the relation
and column names used and a truncation flag; never SQL. Every failure is a
`ToolResult` with a finite `error` outcome class; nothing here raises.
"""

from __future__ import annotations

from src.shared.retrieval.tools.base import ToolContext, ToolResult, run_tool

TABULAR_CAPABILITY_NAME = "tabular_files"

_PURPOSE_TEXT = (
    "Answer a quantitative question — totals, counts, averages, minimums and "
    "maximums, filters, rankings — exactly, from spreadsheets this tenant's "
    "administrators uploaded and published, by generating and running one "
    "read-only SQL query over one file. Use it whenever the question is about "
    "the data in one of the files named below."
)

# Appended to the planner's system prompt only on a turn where `tabular_files`
# is offered — omitted, the planner's input is unchanged.
TABULAR_TOOL_ADDENDUM = (
    "A further capability, `tabular_files`, is offered this turn: it answers "
    "questions over spreadsheets the tenant uploaded (the files are named in its "
    "description) by running a generated SQL query, so its sums, counts, averages "
    "and rankings are exact. Use it for any aggregate, filter or ranking question "
    "about those files' data rather than searching document passages for it. It "
    "cannot combine two files in one query."
)


def _count_tokens(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text) // 4)


def entry_text_for_file(contract: dict) -> str:
    """One file's context text, in the `entry_text_for_relation` shape with
    column types added: `table <relation> — <description>`, then one line per
    included column."""
    header = f"table {contract['relation']}"
    if contract.get("description"):
        header += f" — {contract['description']}"
    source = contract.get("source_file")
    if source:
        header += f" (file {source}" + (f", sheet {contract['sheet']}" if contract.get("sheet") else "") + ")"
    lines = [header, "columns:"]
    for column in contract.get("columns", []):
        line = f"  {column['name']} ({column['type']})"
        if column.get("description"):
            line += f" — {column['description']}"
        lines.append(line)
    return "\n".join(lines)


def render_tabular_tool_description(files: list[dict], token_budget: int) -> str:
    """Fixed purpose text plus each served file's entry, in upload order, until
    the token budget is reached; the remaining files are listed by relation
    name only."""
    parts = [_PURPOSE_TEXT, "Uploaded files available this turn:"]
    used = _count_tokens("\n\n".join(parts))
    overflow: list[str] = []
    for served in files:
        contract = served["contract"]
        if overflow:
            overflow.append(contract["relation"])
            continue
        entry = entry_text_for_file(contract)
        cost = _count_tokens(entry) + 2
        if used + cost > token_budget:
            overflow.append(contract["relation"])
            continue
        parts.append(entry)
        used += cost
    if overflow:
        parts.append("More uploaded files (columns omitted): " + ", ".join(overflow))
    return "\n\n".join(parts)


class TabularFilesTool:
    """One instance per turn, built with a description rendered from the
    authenticated tenant's own served contracts."""

    name = TABULAR_CAPABILITY_NAME
    args_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural-language question to answer from the uploaded files.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, description: str):
        self.description = description

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        captured: dict = {}

        async def executor(args: dict, context: ToolContext) -> tuple[list, bool]:
            if context.tabular_search is None:
                raise RuntimeError("ToolContext has no tabular_search configured")
            answer = await context.tabular_search(
                args["query"], context.tenant_id, context.conversation_context, context.deadline,
            )
            if answer.reason is not None:
                raise _AnswerRejected(answer.reason)
            captured["completeness"] = {
                "returned": len(answer.rows), "matched": None, "truncated": bool(answer.truncated),
            }
            captured["envelope"] = {
                "relations": list(answer.relations),
                "columns": list(answer.columns),
                "files": list(answer.files),
                "truncated": bool(answer.truncated),
            }
            return list(answer.rows), False

        result = await run_tool(self.name, self.args_schema, args, context, executor)
        if result.error is None:
            result.result_completeness = captured.get("completeness")
            result.diagnostics = [captured.get("envelope", {})]
        return result


class _AnswerRejected(Exception):
    """`str(e)` is the finite outcome class, which `run_tool` turns into
    `ToolResult.error` verbatim."""
