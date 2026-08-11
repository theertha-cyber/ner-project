from src.shared.retrieval.tools.base import ToolContext, ToolResult, run_tool


class StructuredRetrievalTool:
    """Answers a natural-language question against extracted structured entity data.

    Delegates SQL generation, validation, and execution to `context.sql_search` — a
    callable the caller supplies (e.g. the chat API's SQLGenerator.generate_and_execute)
    — so this module has no dependency on that caller's package, and the tool is
    reusable by any caller that wires up an equivalent, validated entity-search
    callable."""

    name = "structured_retrieval"
    description = (
        "Query the database of entities extracted from the tenant's documents — every "
        "fact an extraction model found, stored with its type (skill, tool, programming "
        "language, employer, email, degree, …), its value, and its source document. Use "
        "this whenever the question names or implies a category of fact about a subject "
        "or across subjects. Listing or enumerating the values of a type for one subject "
        "('list the tools in X's resume', 'what languages does Y know', 'every company Z "
        "worked at') is its most common use, alongside counting, filtering, comparing, "
        "ranking, and aggregating."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural-language question."},
        },
        "required": ["query"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        # Allocated per call and handed to sql_search so the recovery loop's per-attempt
        # trace survives even when the call ends by raising — `run_tool` turns that into
        # an error ToolResult, and a failure with no trace is not diagnosable.
        attempt_sink: list = []

        async def executor(args: dict, context: ToolContext) -> tuple[list[dict], bool]:
            if context.sql_search is None:
                raise RuntimeError("ToolContext has no sql_search configured")
            rows = await context.sql_search(
                args["query"], context.session, context.schema, None,
                attempt_sink=attempt_sink, deadline=context.deadline,
            )
            return (rows or []), False

        # A raised failure is deliberately not caught here: run_tool converts it into
        # ToolResult(error=…), which is what keeps a failed structured retrieval
        # distinguishable downstream from one that legitimately returned no rows.
        result = await run_tool(self.name, self.args_schema, args, context, executor)
        result.diagnostics = attempt_sink
        if not result.error:
            result.candidate_document_ids = {
                row["document_id"] for row in result.results
                if isinstance(row, dict) and row.get("document_id") is not None
            }
        return result


structured_retrieval = StructuredRetrievalTool()
