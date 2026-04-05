"""Planning Agent for agent-inference-stack.

Breaks down user requests into structured execution plans with
task dependencies, agent assignments, and token estimates.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.agents.base import AgentConfig, BaseAgent
from src.agents.models import AgentType, ExecutionPlan, Task, TaskStatus
from src.agents.prompts.planning import PLANNING_PROMPT_TEMPLATE, PLANNING_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class PlanningAgent(BaseAgent):
    """Agent that decomposes user requests into structured execution plans.

    The planning agent:
    1. Receives a user request
    2. Uses an LLM to generate a structured task breakdown
    3. Parses and validates the JSON output
    4. Returns an ExecutionPlan with tasks, dependencies, and estimates

    Example:
        agent = PlanningAgent(AgentConfig(name="planning", model="claude-sonnet-4-6"))
        plan = await agent.execute({
            "user_request": "Research top 5 SaaS companies by ARR",
            "context": {}
        })
        # Returns ExecutionPlan with 3-4 tasks
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(name="planning", model="claude-sonnet-4-6", temperature=0.1)
        super().__init__(config)

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate an execution plan from the user request.

        Args:
            input_data: Dict with keys:
                - user_request (str): The user's request
                - context (dict): Optional additional context

        Returns:
            Dict containing the ExecutionPlan serialized to dict.
        """
        user_request = input_data.get("user_request", "")
        context = input_data.get("context", {})

        if not user_request:
            raise ValueError("user_request is required for PlanningAgent")

        self._log.info("planning_started", request_preview=user_request[:100])

        prompt = PLANNING_PROMPT_TEMPLATE.format(
            user_request=user_request,
            context=json.dumps(context) if context else "None",
        )

        raw_response = await self._call_llm(
            prompt=prompt,
            system_prompt=PLANNING_SYSTEM_PROMPT,
            temperature=0.1,
        )

        plan = self._parse_plan(raw_response)
        validated_plan = self._validate_plan(plan)

        self._log.info(
            "planning_completed",
            task_count=len(validated_plan.tasks),
            estimated_tokens=validated_plan.estimated_tokens,
        )

        return validated_plan.model_dump()

    def _parse_plan(self, raw_response: str) -> ExecutionPlan:
        """Extract and parse JSON from LLM response.

        Args:
            raw_response: Raw LLM text output (may contain markdown).

        Returns:
            Parsed ExecutionPlan.

        Raises:
            ValueError: If JSON cannot be parsed or schema is invalid.
        """
        # Strip markdown code blocks if present
        cleaned = re.sub(r"```(?:json)?\n?", "", raw_response).strip()

        # Find JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON found in planning response: {raw_response[:200]}")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in planning response: {e}") from e

        if "tasks" not in data:
            raise ValueError("Planning response missing 'tasks' field")

        tasks = []
        for raw_task in data["tasks"]:
            agent_type_str = raw_task.get("agent_type", "execution").lower()
            try:
                agent_type = AgentType(agent_type_str)
            except ValueError:
                agent_type = AgentType.EXECUTION

            tasks.append(
                Task(
                    id=str(raw_task.get("id", f"task_{len(tasks)+1}")),
                    task=str(raw_task.get("task", "")),
                    agent_type=agent_type,
                    dependencies=raw_task.get("dependencies", []),
                    priority=int(raw_task.get("priority", 1)),
                    context=raw_task.get("context", {}),
                )
            )

        return ExecutionPlan(
            tasks=tasks,
            estimated_tokens=int(data.get("estimated_tokens", len(tasks) * 1500)),
            rationale=str(data.get("rationale", "")),
        )

    def _validate_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Validate the execution plan for consistency.

        Checks:
        - All task IDs are unique
        - All dependencies reference existing task IDs
        - No circular dependencies (DAG validation)

        Args:
            plan: Plan to validate.

        Returns:
            Validated plan (same object if valid).

        Raises:
            ValueError: If any validation check fails.
        """
        if not plan.tasks:
            raise ValueError("Execution plan must have at least one task")

        task_ids = {task.id for task in plan.tasks}

        # Check uniqueness
        if len(task_ids) != len(plan.tasks):
            raise ValueError("Task IDs must be unique")

        # Check dependencies reference existing tasks
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise ValueError(
                        f"Task '{task.id}' has dependency '{dep}' which doesn't exist"
                    )

        # Check for circular dependencies using DFS
        self._check_no_cycles(plan.tasks)

        return plan

    def _check_no_cycles(self, tasks: list[Task]) -> None:
        """Verify the task dependency graph has no cycles.

        Args:
            tasks: List of tasks with dependencies.

        Raises:
            ValueError: If a circular dependency is detected.
        """
        adjacency: dict[str, list[str]] = {t.id: t.dependencies for t in tasks}
        visited: set[str] = set()
        path: set[str] = set()

        def dfs(node: str) -> None:
            if node in path:
                raise ValueError(f"Circular dependency detected involving task '{node}'")
            if node in visited:
                return
            path.add(node)
            for dep in adjacency.get(node, []):
                dfs(dep)
            path.discard(node)
            visited.add(node)

        for task_id in adjacency:
            dfs(task_id)
