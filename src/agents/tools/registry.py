"""Tool registry for execution agent."""
from __future__ import annotations

from src.agents.tools.base_tool import BaseTool


class ToolRegistry:
    """Registry for execution tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.metadata.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_metadata(self) -> list[dict]:
        return [t.metadata.model_dump() for t in self._tools.values()]
