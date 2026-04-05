"""API route definitions for agent-inference-stack.

Endpoints:
    POST /process         - Submit a new multi-agent processing request
    GET  /status/{id}     - Check the status of a request
    GET  /metrics         - System-wide metrics
    GET  /health          - Health check
"""
from __future__ import annotations

import time
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from src.api.schemas import (
    AgentMetrics,
    DependencyHealth,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    MetricsResponse,
    ProcessRequest,
    ProcessResponse,
    RequestStatus,
    StatusResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# Track startup time for uptime calculation
_start_time = time.time()


@router.post(
    "/process",
    response_model=ProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a multi-agent processing request",
    description="""
    Submits a user request for processing by the multi-agent pipeline.

    The pipeline:
    1. **Planning Agent** - Breaks request into structured tasks
    2. **Research Agent** - Gathers relevant information
    3. **Execution Agent** - Performs the actual work
    4. **Validation Agent** - Validates output quality

    Returns a request_id that can be used to poll /status/{request_id}.
    """,
    responses={
        202: {"description": "Request accepted for processing"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def process_request(
    request_body: ProcessRequest,
    request: Request,
) -> ProcessResponse:
    """Submit a request for multi-agent processing."""
    log = logger.bind(
        request_id=getattr(request.state, "request_id", "unknown"),
        request_preview=request_body.request[:100],
    )
    log.info("processing_request_received")

    orchestrator = request.app.state.orchestrator

    try:
        result = await orchestrator.submit_request(
            user_request=request_body.request,
            context=request_body.context,
            priority=request_body.priority,
            max_tokens=request_body.max_tokens,
            timeout_seconds=request_body.timeout_seconds,
        )
        log.info("processing_request_submitted", request_id=result["request_id"])
        return ProcessResponse(
            request_id=result["request_id"],
            status=RequestStatus.PENDING,
            message="Request accepted for processing",
            estimated_tokens=result.get("estimated_tokens"),
            estimated_cost_usd=result.get("estimated_cost_usd"),
        )
    except Exception as e:
        log.error("processing_request_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit request: {str(e)}",
        )


@router.get(
    "/status/{request_id}",
    response_model=StatusResponse,
    summary="Check processing request status",
    responses={
        200: {"description": "Request status retrieved"},
        404: {"model": ErrorResponse, "description": "Request not found"},
    },
)
async def get_status(request_id: str, request: Request) -> StatusResponse:
    """Check the status of a processing request."""
    orchestrator = request.app.state.orchestrator

    try:
        state = await orchestrator.get_request_state(request_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request {request_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve status: {str(e)}",
        )

    return StatusResponse(
        request_id=request_id,
        status=RequestStatus(state.get("status", "pending")),
        user_request=state.get("user_request"),
        result=state.get("result"),
        agent_results=state.get("agent_results", []),
        total_tokens=state.get("total_tokens", 0),
        total_cost_usd=state.get("total_cost_usd", 0.0),
        duration_ms=state.get("duration_ms"),
        error=state.get("error"),
        created_at=state.get("created_at"),
        completed_at=state.get("completed_at"),
    )


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="System-wide metrics",
    description="Returns Prometheus-style metrics for monitoring dashboards.",
)
async def get_metrics(request: Request) -> MetricsResponse:
    """Return system-wide performance metrics."""
    orchestrator = request.app.state.orchestrator

    try:
        metrics = await orchestrator.get_metrics()
    except Exception as e:
        logger.warning("metrics_fetch_failed", error=str(e))
        metrics = {}

    uptime = time.time() - _start_time

    return MetricsResponse(
        total_requests=metrics.get("total_requests", 0),
        successful_requests=metrics.get("successful_requests", 0),
        failed_requests=metrics.get("failed_requests", 0),
        avg_latency_ms=metrics.get("avg_latency_ms", 0.0),
        p95_latency_ms=metrics.get("p95_latency_ms", 0.0),
        p99_latency_ms=metrics.get("p99_latency_ms", 0.0),
        total_tokens=metrics.get("total_tokens", 0),
        total_cost_usd=metrics.get("total_cost_usd", 0.0),
        agent_metrics=metrics.get("agent_metrics", []),
        uptime_seconds=uptime,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the service and its dependencies.",
)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint for load balancer probes."""
    dependencies: list[DependencyHealth] = []
    overall_status = HealthStatus.HEALTHY

    # Check orchestrator
    try:
        orchestrator = request.app.state.orchestrator
        if orchestrator is None:
            raise RuntimeError("Not initialized")
        dependencies.append(DependencyHealth(name="orchestrator", status=HealthStatus.HEALTHY))
    except Exception as e:
        dependencies.append(
            DependencyHealth(name="orchestrator", status=HealthStatus.UNHEALTHY, error=str(e))
        )
        overall_status = HealthStatus.DEGRADED

    # Check Redis
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis:
            start = time.perf_counter()
            await redis.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            dependencies.append(
                DependencyHealth(
                    name="redis", status=HealthStatus.HEALTHY, latency_ms=round(latency_ms, 2)
                )
            )
        else:
            dependencies.append(
                DependencyHealth(name="redis", status=HealthStatus.DEGRADED, error="Not configured")
            )
    except Exception as e:
        dependencies.append(
            DependencyHealth(name="redis", status=HealthStatus.UNHEALTHY, error=str(e))
        )
        overall_status = HealthStatus.DEGRADED

    from src import __version__

    return HealthResponse(
        status=overall_status,
        version=__version__,
        environment=getattr(request.app.state, "environment", "unknown"),
        dependencies=dependencies,
    )
