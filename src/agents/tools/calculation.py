"""Math/computation tool."""
from __future__ import annotations

import math
from typing import Any

from src.agents.tools.base_tool import BaseTool, ToolMetadata, ToolParameter


class CalculationTool(BaseTool):
    """Evaluates safe mathematical expressions."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="calculate",
            description="Evaluate a mathematical expression",
            parameters=[
                ToolParameter(name="expression", description="Math expression to evaluate", type="str"),
            ],
            returns="dict with 'result' key",
        )

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        self.validate_params(params)
        expression = params["expression"]
        # Safe eval: only allow math operations
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
        allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
        try:
            result = eval(expression, {"__builtins__": {}}, allowed_names)  # noqa: S307
            return {"result": result, "expression": expression}
        except Exception as e:
            return {"error": str(e), "expression": expression}
