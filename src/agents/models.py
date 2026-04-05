"""Shared agent data models."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentType(str, Enum):
    PLANNING = "planning"
    RESEARCH = "research"
    EXECUTION = "execution"
    VALIDATION = "validation"


class Task(BaseModel):
    """A single task in the execution plan."""

    id: str = Field(description="Unique task identifier, e.g. 'task_1'")
    task: str = Field(description="Description of what this task should accomplish")
    agent_type: AgentType = Field(description="Which agent type should execute this task")
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of task IDs that must complete before this task",
    )
    priority: int = Field(default=1, ge=1, le=10, description="Execution priority")
    context: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None


class ExecutionPlan(BaseModel):
    """Structured execution plan produced by the Planning Agent.

    Example:
        {
            "tasks": [
                {"id": "task_1", "task": "Research competitors", "agent_type": "research", "dependencies": []},
                {"id": "task_2", "task": "Synthesize findings", "agent_type": "execution", "dependencies": ["task_1"]}
            ],
            "estimated_tokens": 8000,
            "estimated_cost_usd": 0.12,
            "rationale": "Two-step plan: gather data then synthesize"
        }
    """

    tasks: list[Task] = Field(description="Ordered list of tasks to execute")
    estimated_tokens: int = Field(default=0, description="Estimated total tokens needed")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated total cost in USD")
    rationale: str = Field(default="", description="Planning agent's reasoning")
