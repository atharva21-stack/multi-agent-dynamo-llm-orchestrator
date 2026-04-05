"""Pydantic request/response schemas for the API.

All schemas use strict validation and include documentation
for the OpenAPI spec.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    """Request body for submitting a multi-agent processing job.

    Example:
        {
            "request": "Research the top 5 competitors of Salesforce",
            "context": {"industry": "CRM", "focus": "enterprise"},
            "priority": 1
        }
    """

    request: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="The user request to process",
        examples=["Research the top 5 competitors of Salesforce in the CRM market"],
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional context/metadata for the request",
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Request priority (1=low, 10=high)",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        le=100000,
        description="Optional token budget override",
    )
    timeout_seconds: int | None = Field(
        default=None,
        gt=0,
        le=600,
        description="Optional timeout override in seconds",
    )


class RequestStatus(str, Enum):
    """Status of a processing request."""

    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentResult(BaseModel):
    """Result from a single agent execution."""

    agent_type: str
    status: str
    output: dict[str, Any] | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


class ProcessResponse(BaseModel):
    """Response for a submitted processing request.

    Example:
        {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
            "message": "Request accepted for processing",
            "estimated_tokens": 5000,
            "estimated_cost_usd": 0.075
        }
    """

    request_id: str = Field(description="Unique request identifier")
    status: RequestStatus = Field(description="Current request status")
    message: str = Field(description="Human-readable status message")
    estimated_tokens: int | None = Field(default=None, description="Estimated total tokens")
    estimated_cost_usd: float | None = Field(default=None, description="Estimated cost in USD")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StatusResponse(BaseModel):
    """Response for request status query.

    Example:
        {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "completed",
            "result": {...},
            "agent_results": [...],
            "total_tokens": 4823,
            "total_cost_usd": 0.072,
            "duration_ms": 12500
        }
    """

    request_id: str
    status: RequestStatus
    user_request: str | None = None
    result: dict[str, Any] | None = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_ms: float | None = None
    error: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class AgentMetrics(BaseModel):
    """Metrics for a single agent type."""

    agent_type: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class MetricsResponse(BaseModel):
    """System-wide metrics response.

    Example:
        {
            "total_requests": 1523,
            "successful_requests": 1498,
            "failed_requests": 25,
            "avg_latency_ms": 8750.0,
            "total_tokens": 7650000,
            "total_cost_usd": 229.50,
            "agent_metrics": [...]
        }
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    agent_metrics: list[AgentMetrics] = Field(default_factory=list)
    uptime_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthStatus(str, Enum):
    """Service health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyHealth(BaseModel):
    """Health of a single dependency."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response.

    Example:
        {
            "status": "healthy",
            "version": "0.1.0",
            "dependencies": [
                {"name": "redis", "status": "healthy", "latency_ms": 1.2},
                {"name": "postgres", "status": "healthy", "latency_ms": 2.5}
            ]
        }
    """

    status: HealthStatus
    version: str = "0.1.0"
    environment: str = "development"
    dependencies: list[DependencyHealth] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
