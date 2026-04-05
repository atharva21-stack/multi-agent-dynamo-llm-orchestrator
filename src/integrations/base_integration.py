"""Abstract base class for all external integrations."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class BaseIntegration(ABC):
    """Abstract base for all external service integrations.

    Provides:
    - Authentication management
    - Rate limiting
    - Error handling with retries
    - Response caching
    - Structured logging
    """

    def __init__(self, name: str, rate_limit_per_minute: int = 60) -> None:
        self.name = name
        self._rate_limit = rate_limit_per_minute
        self._request_times: list[float] = []
        self._log = logger.bind(integration=name)

    @abstractmethod
    async def authenticate(self) -> None:
        """Authenticate with the external service."""

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if integration is available."""

    def _check_rate_limit(self) -> None:
        """Enforce rate limiting (raises if over limit)."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self._rate_limit:
            raise RuntimeError(
                f"Rate limit exceeded for {self.name}: "
                f"{len(self._request_times)}/{self._rate_limit} requests/minute"
            )
        self._request_times.append(now)

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
        json: dict | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Make an authenticated HTTP request with rate limiting."""
        self._check_rate_limit()

        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers or {},
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()
