from src.shared.retrieval.tools.base import ToolContext, ToolResult, run_tool


class SearchEntitiesTool:
    """Answers a natural-language question against extracted entity data.

    Delegates SQL generation, validation, and execution to `context.sql_search` — a
    callable the caller supplies (e.g. the chat API's SQLGenerator.generate_and_execute)
    — so this module has no dependency on that caller's package, and the tool is
    reusable by any caller that wires up an equivalent, validated entity-search
    callable."""

    name = "search_entities"
    description = (
        "Answer a natural-language question about extracted structured entities "
        "(e.g. counts, aggregates, lookups over extraction results)."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural-language question."},
        },
        "required": ["query"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        async def executor(args: dict, context: ToolContext) -> tuple[list[dict], bool]:
            if context.sql_search is None:
                raise RuntimeError("ToolContext has no sql_search configured")
            rows = await context.sql_search(args["query"], context.session, context.schema, None)
            return (rows or []), False

        return await run_tool(self.name, self.args_schema, args, context, executor)


search_entities = SearchEntitiesTool()
