"""Orchestration data models."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RequestState(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentExecutionRecord(BaseModel):
    """Record of a single agent execution."""
    agent_type: str
    task_id: str
    status: str = "pending"
    output: dict[str, Any] | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionRequest(BaseModel):
    """Full execution request lifecycle model."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_request: str
    context: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=1, le=10)
    status: RequestState = RequestState.PENDING
    execution_plan: dict[str, Any] | None = None
    agent_records: list[AgentExecutionRecord] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    validation_result: dict[str, Any] | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds() * 1000
        return None
