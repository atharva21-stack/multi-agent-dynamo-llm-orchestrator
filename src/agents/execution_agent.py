"""Execution Agent for agent-inference-stack.

Executes tasks using available tools and LLM reasoning.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.agents.base import AgentConfig, BaseAgent
from src.agents.tools.calculation import CalculationTool
from src.agents.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)

EXECUTION_SYSTEM_PROMPT = """You are an Execution Agent that performs tasks using available tools.

Given a task and context, you should:
1. Analyze what needs to be done
2. Identify which tools (if any) are needed
3. Execute the task either directly or using tools
4. Return a structured result

Available tools will be listed in the prompt.

Output JSON:
{
  "result": "Main output/result of the task",
  "steps_taken": ["step 1", "step 2"],
  "tools_used": ["tool_name"],
  "confidence": "high|medium|low",
  "notes": "Any important notes"
}"""

EXECUTION_PROMPT_TEMPLATE = """Task: {task}

Context from previous tasks:
{context}

Available tools: {tools}

Execute this task and return structured JSON results."""


class ExecutionAgent(BaseAgent):
    """Agent that executes tasks using tools and LLM reasoning."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(name="execution", model="claude-sonnet-4-6", temperature=0.2)
        super().__init__(config)
        self._tool_registry = ToolRegistry()
        self._tool_registry.register(CalculationTool())

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a task and return structured results."""
        task = input_data.get("task", "")
        context = input_data.get("context", {})

        if not task:
            raise ValueError("task is required for ExecutionAgent")

        self._log.info("execution_started", task_preview=task[:100])

        tools_desc = json.dumps(self._tool_registry.get_all_metadata(), indent=2)

        prompt = EXECUTION_PROMPT_TEMPLATE.format(
            task=task,
            context=json.dumps(context, indent=2) if context else "{}",
            tools=tools_desc,
        )

        response = await self._call_llm(
            prompt=prompt,
            system_prompt=EXECUTION_SYSTEM_PROMPT,
        )

        result = self._parse_result(response)
        self._log.info("execution_completed", confidence=result.get("confidence"))
        return result

    def _parse_result(self, raw_response: str) -> dict[str, Any]:
        """Parse LLM response into structured result."""
        cleaned = re.sub(r"```(?:json)?\n?", "", raw_response).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {
            "result": raw_response[:2000],
            "steps_taken": [],
            "tools_used": [],
            "confidence": "medium",
            "notes": "Could not parse structured output",
        }
