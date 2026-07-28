from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever
from src.shared.retrieval.tools.base import ToolContext, ToolResult, run_tool


def _clamp_top_k(requested: int | None, context: ToolContext) -> int | None:
    if requested is None:
        return None
    return min(requested, context.max_top_k)


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


class SearchDocumentsTool:
    name = "search_documents"
    description = (
        "Search the tenant's document chunks for content relevant to a natural-language "
        "query. Returns ranked chunks with relevance scores."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural-language search query."},
            "top_k": {"type": "integer", "description": "Maximum number of chunks to return."},
        },
        "required": ["query"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        async def executor(args: dict, context: ToolContext) -> tuple[list[RetrievalResult], bool]:
            top_k = _clamp_top_k(args.get("top_k"), context)
            return await _retrieve(args["query"], context, top_k, metadata_filter=None)

        return await run_tool(self.name, self.args_schema, args, context, executor)


class LookupDocumentTool:
    name = "lookup_document"
    description = (
        "Search within a single, already-identified document for content relevant to a "
        "natural-language query. Use for follow-up questions scoped to one document."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural-language search query."},
            "document_id": {"type": "string", "description": "The document to restrict the search to."},
            "top_k": {"type": "integer", "description": "Maximum number of chunks to return."},
        },
        "required": ["query", "document_id"],
    }

    async def call(self, args: dict, context: ToolContext) -> ToolResult:
        async def executor(args: dict, context: ToolContext) -> tuple[list[RetrievalResult], bool]:
            top_k = _clamp_top_k(args.get("top_k"), context)
            metadata_filter = {"document_id": args["document_id"]}
            return await _retrieve(args["query"], context, top_k, metadata_filter=metadata_filter)

        return await run_tool(self.name, self.args_schema, args, context, executor)


search_documents = SearchDocumentsTool()
lookup_document = LookupDocumentTool()
