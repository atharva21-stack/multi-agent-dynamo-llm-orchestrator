"""Central orchestrator for agent-inference-stack.

Coordinates the multi-agent pipeline:
1. Planning → 2. Research/Execution (parallel where possible) → 3. Validation
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any

import structlog

from src.orchestration.executor import TaskExecutor
from src.orchestration.models import ExecutionRequest, RequestState
from src.orchestration.scheduler import DependencyResolver

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Central coordinator for the multi-agent pipeline.

    Manages request lifecycle from submission to completion,
    coordinating all agents and maintaining state.

    Example:
        orchestrator = Orchestrator(settings=settings)
        await orchestrator.initialize()
        result = await orchestrator.process_request("Research top SaaS companies")
    """

    def __init__(self, settings=None) -> None:
        self._settings = settings
        self._executor = TaskExecutor(settings=settings)
        self._scheduler = DependencyResolver()
        self._requests: dict[str, ExecutionRequest] = {}
        self._metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "latencies_ms": [],
        }
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the orchestrator and its dependencies."""
        logger.info("orchestrator_initializing")
        self._initialized = True
        logger.info("orchestrator_ready")

    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator."""
        logger.info("orchestrator_shutting_down")
        self._initialized = False

    async def submit_request(
        self,
        user_request: str,
        context: dict[str, Any] | None = None,
        priority: int = 1,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Submit a request for async processing.

        Returns immediately with a request_id for status polling.
        Processing happens in background.
        """
        req = ExecutionRequest(
            user_request=user_request,
            context=context or {},
            priority=priority,
        )
        self._requests[req.request_id] = req

        # Start processing in background
        timeout = timeout_seconds or (
            self._settings.request_timeout_seconds if self._settings else 300
        )
        asyncio.create_task(
            self._process_with_timeout(req, timeout)
        )

        return {
            "request_id": req.request_id,
            "estimated_tokens": None,
            "estimated_cost_usd": None,
        }

    async def process_request(self, user_request: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Process a request synchronously (awaits completion).

        Args:
            user_request: The user's request string.
            context: Optional additional context.

        Returns:
            Completed execution result.
        """
        req = ExecutionRequest(user_request=user_request, context=context or {})
        self._requests[req.request_id] = req
        await self._execute_pipeline(req)
        return self._format_result(req)

    async def get_request_state(self, request_id: str) -> dict[str, Any]:
        """Get the current state of a request.

        Raises:
            KeyError: If request_id is not found.
        """
        if request_id not in self._requests:
            raise KeyError(f"Request {request_id} not found")
        req = self._requests[request_id]
        return self._format_result(req)

    async def get_metrics(self) -> dict[str, Any]:
        """Return aggregated system metrics."""
        latencies = self._metrics["latencies_ms"]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        sorted_latencies = sorted(latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p99_idx = int(len(sorted_latencies) * 0.99)

        return {
            "total_requests": self._metrics["total_requests"],
            "successful_requests": self._metrics["successful_requests"],
            "failed_requests": self._metrics["failed_requests"],
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": sorted_latencies[p95_idx] if sorted_latencies else 0.0,
            "p99_latency_ms": sorted_latencies[p99_idx] if sorted_latencies else 0.0,
            "total_tokens": self._metrics["total_tokens"],
            "total_cost_usd": round(self._metrics["total_cost_usd"], 6),
            "agent_metrics": [],
        }

    async def _process_with_timeout(self, req: ExecutionRequest, timeout: int) -> None:
        """Execute pipeline with timeout."""
        try:
            await asyncio.wait_for(self._execute_pipeline(req), timeout=timeout)
        except asyncio.TimeoutError:
            req.status = RequestState.FAILED
            req.error = f"Request timed out after {timeout} seconds"
            req.completed_at = datetime.utcnow()
            logger.error("request_timeout", request_id=req.request_id, timeout=timeout)

    async def _execute_pipeline(self, req: ExecutionRequest) -> None:
        """Execute the full multi-agent pipeline.

        Pipeline:
        1. Planning Agent: Generate execution plan
        2. Execute tasks in DAG order (parallel where possible)
        3. Validation Agent: Validate output quality
        """
        start_time = time.perf_counter()
        log = logger.bind(request_id=req.request_id)
        self._metrics["total_requests"] += 1

        try:
            # === PHASE 1: PLANNING ===
            req.status = RequestState.PLANNING
            log.info("pipeline_planning")

            from src.agents.planning_agent import PlanningAgent
            from src.agents.base import AgentConfig

            planner = PlanningAgent(AgentConfig(name="planning", model="claude-sonnet-4-6"))
            planning_result = await planner.execute({
                "user_request": req.user_request,
                "context": req.context,
            })

            req.execution_plan = planning_result
            req.total_tokens += planner.tokens_used
            req.total_cost_usd += planner.cost_usd

            from src.agents.models import ExecutionPlan
            plan = ExecutionPlan(**{k: v for k, v in planning_result.items() if k != "_meta"})
            log.info("planning_complete", task_count=len(plan.tasks))

            # === PHASE 2: EXECUTION ===
            req.status = RequestState.EXECUTING
            log.info("pipeline_executing")

            waves = self._scheduler.topological_sort(plan.tasks)
            aggregated_context: dict[str, Any] = {
                "user_request": req.user_request,
                **req.context,
            }

            for wave_idx, wave in enumerate(waves):
                log.info("executing_wave", wave=wave_idx + 1, tasks=len(wave))

                # Execute tasks in wave in parallel
                task_coros = [
                    self._executor.execute_task(task, aggregated_context)
                    for task in wave
                ]
                records = await asyncio.gather(*task_coros, return_exceptions=True)

                for task, record in zip(wave, records):
                    if isinstance(record, Exception):
                        log.error("wave_task_error", task_id=task.id, error=str(record))
                        continue
                    req.agent_records.append(record)
                    req.total_tokens += record.tokens_used
                    req.total_cost_usd += record.cost_usd

                    # Accumulate context for downstream tasks
                    if record.output:
                        aggregated_context[f"{task.agent_type.value}_results"] = record.output
                        aggregated_context[task.id] = record.output

            req.result = aggregated_context

            # === PHASE 3: VALIDATION ===
            req.status = RequestState.VALIDATING
            log.info("pipeline_validating")

            from src.agents.validation_agent import ValidationAgent
            validator = ValidationAgent()
            validation_result = await validator.execute({
                "original_request": req.user_request,
                "execution_output": aggregated_context,
            })
            req.validation_result = validation_result
            req.total_tokens += validator.tokens_used
            req.total_cost_usd += validator.cost_usd

            req.status = RequestState.COMPLETED
            req.completed_at = datetime.utcnow()
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._metrics["successful_requests"] += 1
            self._metrics["total_tokens"] += req.total_tokens
            self._metrics["total_cost_usd"] += req.total_cost_usd
            self._metrics["latencies_ms"].append(duration_ms)

            log.info(
                "pipeline_completed",
                duration_ms=round(duration_ms, 2),
                tokens=req.total_tokens,
                cost_usd=round(req.total_cost_usd, 6),
                validation_score=validation_result.get("score"),
            )

        except Exception as e:
            req.status = RequestState.FAILED
            req.error = str(e)
            req.completed_at = datetime.utcnow()
            self._metrics["failed_requests"] += 1
            log.error("pipeline_failed", error=str(e), exc_info=True)

    def _format_result(self, req: ExecutionRequest) -> dict[str, Any]:
        """Format execution request as a status response dict."""
        return {
            "request_id": req.request_id,
            "status": req.status.value,
            "user_request": req.user_request,
            "result": req.result,
            "agent_results": [r.model_dump() for r in req.agent_records],
            "validation_result": req.validation_result,
            "total_tokens": req.total_tokens,
            "total_cost_usd": req.total_cost_usd,
            "duration_ms": req.duration_ms,
            "error": req.error,
            "created_at": req.created_at,
            "completed_at": req.completed_at,
        }
