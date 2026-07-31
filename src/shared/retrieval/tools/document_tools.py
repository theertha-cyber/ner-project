from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools.base import ArgValidationError, ToolContext, ToolResult, run_tool

SUPPORTED_SCOPE_TYPES = {"tenant", "document"}


def _clamp_top_k(requested: int | None, context: ToolContext) -> int | None:
    if requested is None:
        return None
    return min(requested, context.max_top_k)


def _scope_to_metadata_filter(scope: dict | None) -> dict | None:
    """Translates the capability's `scope` argument into the retriever's
    `metadata_filter`. Raises ArgValidationError for an unsupported scope type or
    a `document` scope missing its `document_ids`, so callers reject before ever
    issuing a query."""
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
    return {"document_ids": document_ids}


async def _retrieve(query: str, context: ToolContext, top_k: int | None, metadata_filter: dict | None) -> tuple[list[RetrievalResult], bool]:
    if context.retriever is None:
        raise RuntimeError("ToolContext has no retriever configured")

    degraded_sink: list = []
    if isinstance(context.retriever, RerankingRetriever):
        results = await context.retriever.retrieve(
            query, context.session, context.schema,
            top_k=top_k, metadata_filter=metadata_filter,
            jwt_token=context.jwt_token, degraded_sink=degraded_sink,
        )
    else:
        results = await context.retriever.retrieve(
            query, context.session, context.schema, top_k=top_k, metadata_filter=metadata_filter,
        )
    return results, bool(degraded_sink)


class SemanticRetrievalTool:
    """Single semantic retrieval capability. Search extent is controlled internally
    via `scope` rather than by exposing separate tools per scope (see
    redesign-retrieval-orchestration design Decision 2)."""

    name = "semantic_retrieval"
    description = (
        "Retrieve document content relevant to a natural-language query using semantic "
        "search. Returns ranked chunks with relevance scores. By default searches across "
        "the tenant's entire document corpus; pass `scope` to restrict the search to "
        "specific documents."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural-language search query."},
            "top_k": {"type": "integer", "description": "Maximum number of chunks to return."},
            "scope": {
                "type": "object",
                "description": (
                    "Search extent. Omit or use {'type': 'tenant'} to search the whole "
                    "tenant corpus. Use {'type': 'document', 'document_ids': [...]} to "
                    "restrict the search to specific, already-identified documents."
                ),
            },
        },
        "required": ["query"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        async def executor(args: dict, context: ToolContext) -> tuple[list[RetrievalResult], bool]:
            top_k = _clamp_top_k(args.get("top_k"), context)
            metadata_filter = _scope_to_metadata_filter(args.get("scope"))
            return await _retrieve(args["query"], context, top_k, metadata_filter)

        return await run_tool(self.name, self.args_schema, args, context, executor)


semantic_retrieval = SemanticRetrievalTool()
