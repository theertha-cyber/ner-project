from __future__ import annotations

from src.shared.retrieval.tools.base import RetrievalTool, assert_no_tenancy_params


class ToolLookupError(KeyError):
    pass


class ToolRegistrationError(ValueError):
    pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RetrievalTool] = {}

    def register(self, tool: RetrievalTool) -> None:
        assert_no_tenancy_params(tool.args_schema, tool.name)
        if tool.name in self._tools:
            raise ToolRegistrationError(f"a tool named '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RetrievalTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolLookupError(f"no tool registered with name '{name}'") from None

    def list(self) -> list[RetrievalTool]:
        return list(self._tools.values())

    def export_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_schema,
                },
            }
            for tool in self._tools.values()
        ]
