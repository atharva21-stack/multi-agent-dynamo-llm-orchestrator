"""Base class for all execution tools."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Descriptor for a tool parameter."""
    name: str
    description: str
    type: str
    required: bool = True


class ToolMetadata(BaseModel):
    """Metadata describing a tool."""
    name: str
    description: str
    parameters: list[ToolParameter] = []
    returns: str = "dict"


class BaseTool(ABC):
    """Abstract base class for execution tools."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return tool metadata."""

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool with given parameters."""

    def validate_params(self, params: dict[str, Any]) -> None:
        """Validate required parameters are present."""
        for p in self.metadata.parameters:
            if p.required and p.name not in params:
                raise ValueError(f"Missing required parameter '{p.name}' for tool '{self.metadata.name}'")
