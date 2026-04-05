"""Health check utilities."""
from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def check_redis(redis_client) -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        start = time.perf_counter()
        await redis_client.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        return {"name": "redis", "status": "healthy", "latency_ms": round(latency_ms, 2)}
    except Exception as e:
        return {"name": "redis", "status": "unhealthy", "error": str(e)}


async def check_postgres(postgres_client) -> dict[str, Any]:
    """Check PostgreSQL connectivity."""
    try:
        start = time.perf_counter()
        await postgres_client.execute("SELECT 1")
        latency_ms = (time.perf_counter() - start) * 1000
        return {"name": "postgres", "status": "healthy", "latency_ms": round(latency_ms, 2)}
    except Exception as e:
        return {"name": "postgres", "status": "unhealthy", "error": str(e)}


async def check_vllm(vllm_engine) -> dict[str, Any]:
    """Check vLLM engine status."""
    try:
        if not vllm_engine._initialized:
            return {"name": "vllm", "status": "not_initialized"}
        mode = "api_fallback" if vllm_engine._use_api_fallback else "vllm_server"
        return {"name": "vllm", "status": "healthy", "mode": mode}
    except Exception as e:
        return {"name": "vllm", "status": "unhealthy", "error": str(e)}
