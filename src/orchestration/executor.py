"""Task executor - routes tasks to agents and handles errors."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog

from src.agents.models import Task, TaskStatus
from src.orchestration.models import AgentExecutionRecord

logger = structlog.get_logger(__name__)


class TaskExecutor:
    """Executes individual tasks by routing them to the appropriate agent."""

    def __init__(self, settings=None) -> None:
        self._settings = settings

    async def execute_task(
        self,
        task: Task,
        context: dict[str, Any],
        agent_configs: dict[str, Any] | None = None,
    ) -> AgentExecutionRecord:
        """Execute a single task using the appropriate agent.

        Args:
            task: The task to execute.
            context: Aggregated context from previous tasks.
            agent_configs: Optional per-agent configuration overrides.

        Returns:
            AgentExecutionRecord with execution results.
        """
        record = AgentExecutionRecord(
            agent_type=task.agent_type.value,
            task_id=task.id,
            started_at=datetime.utcnow(),
        )

        log = logger.bind(task_id=task.id, agent_type=task.agent_type.value)
        log.info("task_executing")

        try:
            from src.agents.base import AgentConfig
            from src.agents.agent_registry import get_registry

            registry = get_registry()

            # Build agent config
            config = AgentConfig(name=task.agent_type.value)
            agent = registry.get_agent(task.agent_type.value, config)

            # Build input based on agent type
            input_data = self._build_input(task, context)
            result = await agent.execute(input_data)

            record.status = "completed"
            record.output = result
            record.tokens_used = agent.tokens_used
            record.cost_usd = agent.cost_usd
            record.latency_ms = agent.latency_ms
            record.completed_at = datetime.utcnow()
            task.status = TaskStatus.COMPLETED
            task.result = result

            log.info(
                "task_completed",
                tokens=record.tokens_used,
                cost_usd=round(record.cost_usd, 6),
                latency_ms=round(record.latency_ms, 2),
            )

        except Exception as e:
            record.status = "failed"
            record.error = str(e)
            record.completed_at = datetime.utcnow()
            task.status = TaskStatus.FAILED
            task.error = str(e)
            log.error("task_failed", error=str(e))

        return record

    def _build_input(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """Build agent-specific input from task and aggregated context."""
        agent_type = task.agent_type.value
        base = {"context": context, **task.context}

        if agent_type == "planning":
            return {**base, "user_request": task.task}
        elif agent_type == "research":
            return {**base, "task": task.task}
        elif agent_type == "execution":
            return {**base, "task": task.task}
        elif agent_type == "validation":
            return {
                **base,
                "original_request": context.get("user_request", task.task),
                "execution_output": context.get("execution_results", {}),
            }
        return {**base, "task": task.task}
