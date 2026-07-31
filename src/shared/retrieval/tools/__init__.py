from src.shared.retrieval.tools.base import ArgValidationError, RetrievalTool, ToolContext, ToolResult
from src.shared.retrieval.tools.document_tools import semantic_retrieval
from src.shared.retrieval.tools.entity_tools import structured_retrieval
from src.shared.retrieval.tools.registry import ToolLookupError, ToolRegistrationError, ToolRegistry

__all__ = [
    "ArgValidationError", "RetrievalTool", "ToolContext", "ToolResult",
    "semantic_retrieval", "structured_retrieval",
    "ToolRegistry", "ToolLookupError", "ToolRegistrationError",
]


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(semantic_retrieval)
    registry.register(structured_retrieval)
    return registry
