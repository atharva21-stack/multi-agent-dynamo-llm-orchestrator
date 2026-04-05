"""Prometheus metrics for agent-inference-stack."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

import structlog

logger = structlog.get_logger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client_not_installed_metrics_disabled")


class Metrics:
    """Prometheus metrics registry for agent-inference-stack.

    Example:
        metrics = Metrics()
        metrics.request_counter.labels(status="success").inc()
        with metrics.request_duration.labels(agent="planning").time():
            await agent.execute(...)
    """

    def __init__(self) -> None:
        if not _PROMETHEUS_AVAILABLE:
            self._mock_mode = True
            return
        self._mock_mode = False

        self.request_counter = Counter(
            "agent_request_total",
            "Total number of requests processed",
            ["status"],  # success, failure
        )
        self.request_duration = Histogram(
            "agent_request_duration_seconds",
            "Request processing duration in seconds",
            ["agent_type"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        )
        self.tokens_used = Counter(
            "agent_tokens_used_total",
            "Total tokens consumed",
            ["agent_type", "direction"],  # input, output
        )
        self.cost_usd = Counter(
            "agent_cost_usd_total",
            "Total cost in USD",
            ["agent_type"],
        )
        self.agent_success_rate = Gauge(
            "agent_success_rate",
            "Agent success rate (0-1)",
            ["agent_type"],
        )
        self.active_requests = Gauge(
            "agent_active_requests",
            "Currently active requests",
        )
        self.cache_hit_rate = Gauge(
            "agent_inference_cache_hit_rate",
            "Inference cache hit rate",
        )

    def start_server(self, port: int = 9090) -> None:
        """Start Prometheus HTTP metrics server."""
        if self._mock_mode:
            logger.warning("prometheus_not_available_skipping_server_start")
            return
        start_http_server(port)
        logger.info("prometheus_metrics_server_started", port=port)

    @contextmanager
    def track_request(self, agent_type: str) -> Generator[None, None, None]:
        """Context manager for tracking request timing."""
        if self._mock_mode:
            yield
            return
        self.active_requests.inc()
        start = time.perf_counter()
        try:
            yield
            self.request_counter.labels(status="success").inc()
        except Exception:
            self.request_counter.labels(status="failure").inc()
            raise
        finally:
            duration = time.perf_counter() - start
            self.request_duration.labels(agent_type=agent_type).observe(duration)
            self.active_requests.dec()

    def record_tokens(self, agent_type: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for an agent execution."""
        if self._mock_mode:
            return
        self.tokens_used.labels(agent_type=agent_type, direction="input").inc(input_tokens)
        self.tokens_used.labels(agent_type=agent_type, direction="output").inc(output_tokens)

    def record_cost(self, agent_type: str, cost_usd: float) -> None:
        """Record cost for an agent execution."""
        if self._mock_mode:
            return
        self.cost_usd.labels(agent_type=agent_type).inc(cost_usd)


# Global singleton
_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    """Get the global metrics singleton."""
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics
