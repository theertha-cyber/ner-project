from src.shared.retrieval.tools.base import ArgValidationError, ToolContext, ToolResult, run_tool

SUPPORTED_SCOPE_TYPES = {"tenant", "document"}


def _scope_to_document_ids(scope: dict | None) -> list[str] | None:
    """Translates the capability's `scope` argument into the document identifiers the
    executed statement must be constrained to. Same shape `semantic_retrieval` uses, so
    a resolved turn scopes both capabilities with one value."""
    if scope is None:
        return None

    scope_type = scope.get("type")
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        raise ArgValidationError(f"unsupported scope type: {scope_type!r}")
    if scope_type == "tenant":
        return None

    document_ids = scope.get("document_ids")
    if not document_ids or not isinstance(document_ids, list):
        raise ArgValidationError("scope of type 'document' requires a non-empty 'document_ids' list")
    return [str(d) for d in document_ids]


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
            "scope": {
                "type": "object",
                "description": (
                    "Query extent. Omit or use {'type': 'tenant'} to query the whole "
                    "tenant's entities. Use {'type': 'document', 'document_ids': [...]} "
                    "to restrict the query to specific, already-identified documents."
                ),
            },
        },
        "required": ["query"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        # Allocated per call and handed to sql_search so the recovery loop's per-attempt
        # trace survives even when the call ends by raising — `run_tool` turns that into
        # an error ToolResult, and a failure with no trace is not diagnosable.
        attempt_sink: list = []
        # Filled by the successful attempt with returned/matched/truncated, so prompt
        # assembly can tell a complete answer from the first page of a longer one.
        completeness_sink: dict = {}

        async def executor(args: dict, context: ToolContext) -> tuple[list[dict], bool]:
            if context.sql_search is None:
                raise RuntimeError("ToolContext has no sql_search configured")
            # Forward the conversation, don't drop it: a follow-up query ("which of
            # those candidates …") reaches this tool as a `query` string alone, and
            # SQL generated without the earlier turns silently searches the whole
            # tenant instead of the set the user was actually asking about.
            # The document scope travels as a value, not as prose appended to the
            # question: asking a second model to honour "restrict results to
            # document_id = '…'" made enforcement depend on its compliance, and the
            # post-execution filter that backstopped it ran after the row limit.
            rows = await context.sql_search(
                args["query"], context.session, context.schema, context.conversation_context,
                attempt_sink=attempt_sink, deadline=context.deadline,
                document_ids=_scope_to_document_ids(args.get("scope")),
                completeness_sink=completeness_sink,
            )
            return (rows or []), False

        # A raised failure is deliberately not caught here: run_tool converts it into
        # ToolResult(error=…), which is what keeps a failed structured retrieval
        # distinguishable downstream from one that legitimately returned no rows.
        result = await run_tool(self.name, self.args_schema, args, context, executor)
        result.diagnostics = attempt_sink
        result.result_completeness = completeness_sink or None
        if not result.error:
            result.candidate_document_ids = {
                row["document_id"] for row in result.results
                if isinstance(row, dict) and row.get("document_id") is not None
            }
        return result


structured_retrieval = StructuredRetrievalTool()
