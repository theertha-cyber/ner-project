from src.shared.retrieval.tools.base import ArgValidationError, RetrievalTool, ToolContext, ToolResult
from src.shared.retrieval.tools.document_tools import lookup_document, search_documents
from src.shared.retrieval.tools.entity_tools import search_entities
from src.shared.retrieval.tools.registry import ToolLookupError, ToolRegistrationError, ToolRegistry

__all__ = [
    "ArgValidationError", "RetrievalTool", "ToolContext", "ToolResult",
    "search_documents", "lookup_document", "search_entities",
    "ToolRegistry", "ToolLookupError", "ToolRegistrationError",
]


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(search_documents)
    registry.register(lookup_document)
    registry.register(search_entities)
    return registry
